import argparse
import asyncio
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Generator, List, Optional, Set, Tuple

from google import genai
from latin_macronizer import Macronizer
from pydantic import BaseModel, Field
from tqdm import tqdm

# =====================================================================
# Logging Setup
# =====================================================================

def setup_logger(log_file: Path = Path("pipeline_runtime.log")) -> logging.Logger:
    logger = logging.getLogger("MacronPipeline")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(console_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    return logger

logger = setup_logger()

# =====================================================================
# Configuration & Domain Models
# =====================================================================

@dataclass(frozen=True)
class ModelSpec:
    name: str
    rpm_limit: int
    rpd_limit: int
    target_rpm_pct: float = 0.95
    target_rpd_pct: float = 0.95

    @property
    def target_rpm(self) -> float:
        return self.rpm_limit * self.target_rpm_pct

    @property
    def target_rpd(self) -> int:
        return int(self.rpd_limit * self.target_rpd_pct)

    @property
    def min_interval(self) -> float:
        return 60.0 / self.target_rpm


AVAILABLE_MODELS = [
    ModelSpec(name="gemini-3.5-flash-lite", rpm_limit=15, rpd_limit=500),
    ModelSpec(name="gemini-3.1-flash-lite", rpm_limit=15, rpd_limit=500),
    ModelSpec(name="gemini-3.8-flash", rpm_limit=5, rpd_limit=20),
    ModelSpec(name="gemini-3.7-flash", rpm_limit=5, rpd_limit=20),
    ModelSpec(name="gemini-3.6-flash", rpm_limit=5, rpd_limit=20),
    ModelSpec(name="gemini-3.5-flash", rpm_limit=5, rpd_limit=20),
]


@dataclass
class PipelineConfig:
    raw_dir: Path = Path("lat_text_latin_library")
    macronized_dir: Path = Path("output_repo")
    logs_dir: Path = Path("data/logs")
    checkpoint_file: Path = Path("data/checkpoint.json")
    priority_file: Path = Path("data/priority.txt")
    priority_inputs_dir: Path = Path("data/priority_inputs")
    max_tokens_per_chunk: int = 1000
    max_slots_per_chunk: int = 30
    max_validation_attempts: int = 3
    max_api_retries: int = 4
    api_timeout_seconds: float = 60.0
    max_run_seconds: float = 19800.0  # 5.5 hours maximum run timer cap
    thinking_level: str = "high"
    raw_repo_url: str = "https://github.com/cltk/lat_text_latin_library.git"


class DailyQuotaExhaustedException(Exception):
    """Raised when 95% of daily requests across all configured models have been reached."""
    pass


@dataclass
class ModelUsageState:
    daily_requests: int = 0
    last_request_date: str = ""


@dataclass
class CheckpointState:
    model_usage: Dict[str, ModelUsageState] = field(default_factory=dict)
    file_progress: Dict[str, int] = field(default_factory=dict)
    completed_files: List[str] = field(default_factory=list)
    daily_bytes_processed: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "model_usage": {
                m: {"daily_requests": u.daily_requests, "last_request_date": u.last_request_date}
                for m, u in self.model_usage.items()
            },
            "file_progress": self.file_progress,
            "completed_files": self.completed_files,
            "daily_bytes_processed": self.daily_bytes_processed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CheckpointState":
        model_usage = {
            m: ModelUsageState(
                daily_requests=u.get("daily_requests", 0),
                last_request_date=u.get("last_request_date", ""),
            )
            for m, u in data.get("model_usage", {}).items()
        }
        return cls(
            model_usage=model_usage,
            file_progress=data.get("file_progress", {}),
            completed_files=data.get("completed_files", []),
            daily_bytes_processed=data.get("daily_bytes_processed", {}),
        )


@dataclass
class RunSessionStats:
    start_time: float = field(default_factory=time.time)
    files_processed_today: int = 0
    chunks_processed_today: int = 0
    slots_resolved_today: int = 0
    slots_unfilled_today: int = 0
    bytes_processed_today: int = 0
    api_calls_by_model: Dict[str, int] = field(default_factory=dict)
    priority_files_worked_on: Dict[str, str] = field(default_factory=dict)


@dataclass
class ChunkResolutionStats:
    total_slots: int
    resolved_slots: int = 0
    failed_attempts: int = 0


class MacronResolution(BaseModel):
    resolutions: List[str] = Field(
        description="Sequential list of resolved words replacing every <opt1|opt2> or [unknown] slot in order."
    )

# =====================================================================
# Audit Logging Service
# =====================================================================

class AuditLogger:
    """Manages structured JSON Lines logging for resolved and unfilled slots."""

    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.resolved_log = self.logs_dir / "slot_audit.jsonl"
        self.unfilled_log = self.logs_dir / "unfilled_slots.jsonl"

    def log_resolved_slot(
        self,
        rel_path: str,
        chunk_idx: int,
        attempt: int,
        model_used: str,
        slot_raw: str,
        filled_value: str,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file": rel_path,
            "chunk_index": chunk_idx,
            "attempt": attempt,
            "model_used": model_used,
            "slot_raw": slot_raw,
            "filled_value": filled_value,
        }
        with open(self.resolved_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def log_unfilled_slot(
        self,
        rel_path: str,
        chunk_idx: int,
        max_attempts: int,
        slot_raw: str,
        context_snippet: str,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file": rel_path,
            "chunk_index": chunk_idx,
            "max_attempts": max_attempts,
            "slot_raw": slot_raw,
            "context_snippet": context_snippet[:150],
        }
        with open(self.unfilled_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

# =====================================================================
# Services & Utilities
# =====================================================================

class TextEscaper:
    MASK_LANGLE = "\uE000"
    MASK_RANGLE = "\uE001"
    MASK_LBRACKET = "\uE002"
    MASK_RBRACKET = "\uE003"

    @classmethod
    def escape_raw_brackets(cls, text: str) -> str:
        text = re.sub(r"(?<!\\)\[", r"\[", text)         text = re.sub(r"(?<!\\)\]", r"\]", text)
        text = re.sub(r"(?<!\\)<", r"\<", text)
        text = re.sub(r"(?<!\\)>", r"\>", text)
        return text

    @classmethod
    def mask(cls, text: str) -> str:
        text = text.replace(r"\<", cls.MASK_LANGLE)
        text = text.replace(r"\>", cls.MASK_RANGLE)
        text = text.replace(r"\[", cls.MASK_LBRACKET)         text = text.replace(r"\]", cls.MASK_RBRACKET)
        return text

    @classmethod
    def unmask(cls, text: str) -> str:
        text = text.replace(cls.MASK_LANGLE, "<")
        text = text.replace(cls.MASK_RANGLE, ">")
        text = text.replace(cls.MASK_LBRACKET, "[")
        text = text.replace(cls.MASK_RBRACKET, "]")
        return text


class LatinPreprocessor:
    def __init__(
        self,
        confidence_threshold: float = 1.0,
        performutov: bool = True,
        performitoj: bool = True,
        alsomaius: bool = False,
    ):
        self.macronizer = Macronizer()
        self.confidence_threshold = confidence_threshold
        self.performutov = performutov
        self.performitoj = performitoj
        self.alsomaius = alsomaius

    def process_paragraph(self, paragraph: str) -> str:
        if not paragraph.strip():
            return paragraph
        
        normalized = unicodedata.normalize("NFC", paragraph)
        self.macronizer.settext(normalized)
        return self.macronizer.gettext(
            domacronize=True,
            alsomaius=self.alsomaius,
            performutov=self.performutov,
            performitoj=self.performitoj,
            markambigs=True,
            confidence_threshold=self.confidence_threshold,
            output_format="inline",
        )


class SlotValidator:
    SLOT_PATTERN = re.compile(r"<[^>]+>|\[[^\]]+\]")

    @classmethod
    def find_slots(cls, text: str) -> List[re.Match]:
        return list(cls.SLOT_PATTERN.finditer(text))

    @classmethod
    def count_slots(cls, text: str) -> int:
        return len(cls.SLOT_PATTERN.findall(text))

    @staticmethod
    def canonicalize_base(text: str) -> str:
        decomposed = unicodedata.normalize("NFD", text)
        stripped = "".join(c for c in decomposed if ord(c) != 0x0304)
        return stripped.lower().replace("j", "i").replace("v", "u")

    @classmethod
    def validate(cls, raw_slot: str, output_word: str) -> bool:
        if raw_slot.startswith("<") and raw_slot.endswith(">"):
            options = raw_slot[1:-1].split("|")
            return output_word in options
        elif raw_slot.startswith("[") and raw_slot.endswith("]"):
            base_word = raw_slot[1:-1]
            if output_word[0].isupper() != base_word[0].isupper():
                return False
            return cls.canonicalize_base(output_word) == cls.canonicalize_base(base_word)
        return False


class TextChunker:
    @staticmethod
    def estimate_tokens(text: str) -> int:
        return len(text) // 4 + 1


class MultiModelRateLimiter:
    """Dynamically rotates through configured Gemini models while enforcing 95% RPM/RPD limits."""

    def __init__(self, models: List[ModelSpec], state: CheckpointState, session_stats: RunSessionStats):
        self.models = models
        self.state = state
        self.session_stats = session_stats
        self.next_allowed_times: Dict[str, float] = {m.name: 0.0 for m in models}
        self._lock = asyncio.Lock()

    async def acquire_model(self) -> Tuple[ModelSpec, float]:
        async with self._lock:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            selected_model: Optional[ModelSpec] = None
            scheduled_time = 0.0
            now = time.monotonic()

            for spec in self.models:
                usage = self.state.model_usage.setdefault(spec.name, ModelUsageState())
                if usage.last_request_date != today_str:
                    usage.last_request_date = today_str
                    usage.daily_requests = 0

                if usage.daily_requests < spec.target_rpd:
                    selected_model = spec
                    slot_time = max(now, self.next_allowed_times[spec.name])
                    self.next_allowed_times[spec.name] = slot_time + spec.min_interval
                    usage.daily_requests += 1
                    self.session_stats.api_calls_by_model[spec.name] = (
                        self.session_stats.api_calls_by_model.get(spec.name, 0) + 1
                    )
                    scheduled_time = slot_time
                    break

            if selected_model is None:
                raise DailyQuotaExhaustedException(
                    "Reached 95% daily request quota across all available models. Pausing run until tomorrow."
                )

        sleep_duration = scheduled_time - now
        if sleep_duration > 0:
            await asyncio.sleep(sleep_duration)

        return selected_model, sleep_duration


class CheckpointManager:
    def __init__(self, checkpoint_file: Path):
        self.checkpoint_file = checkpoint_file

    def load(self) -> CheckpointState:
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    return CheckpointState.from_dict(json.load(f))
            except Exception as e:
                logger.warning(f"Could not load checkpoint ({e}). Starting fresh.")
        return CheckpointState()

    def save(self, state: CheckpointState) -> None:
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2)

# =====================================================================
# Gemini Resolution Engine
# =====================================================================

class MacronResolverEngine:
    SYSTEM_INSTRUCTION = (
        "You are an expert Latin philologist. Process Latin text containing two slot types:\n"
        "1. <option1|option2|...>: Select the exact correct macronized form from the options.\n"
        "2. [word]: Supply the proper macrons without altering base letters or casing, "
        "except using 'v' for consonantal /w/ and 'j' for consonantal /j/.\n\n"
        "Return a JSON object containing the exact resolved words in sequential left-to-right order."
    )

    def __init__(
        self,
        client: genai.Client,
        config: PipelineConfig,
        rate_limiter: MultiModelRateLimiter,
        audit_logger: AuditLogger,
    ):
        self.client = client
        self.config = config
        self.rate_limiter = rate_limiter
        self.audit_logger = audit_logger

    @staticmethod
    def _clean_json_text(raw_text: str) -> str:
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        return text.strip()

    async def _call_api_with_backoff(self, prompt: str) -> Tuple[str, any]:
        delay = 2.0
        for attempt in range(1, self.config.max_api_retries + 1):
            model_spec, _ = await self.rate_limiter.acquire_model()
            try:
                interaction = await self.client.aio.interactions.create(
                    model=model_spec.name,
                    input=prompt,
                    generation_config={"thinking_level": self.config.thinking_level},
                    response_format={
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": MacronResolution.model_json_schema(),
                    },
                    timeout=self.config.api_timeout_seconds,
                )
                return model_spec.name, interaction
            except DailyQuotaExhaustedException:
                raise
            except Exception as e:
                err_str = str(e)
                if "429" in err_str and "RESOURCE_EXHAUSTED" in err_str:
                    logger.warning(f"Model {model_spec.name} quota exhausted (429). Rotating model.")
                    continue

                is_transient = any(code in err_str for code in ["500", "502", "503", "504", "api_error"])
                if is_transient and attempt < self.config.max_api_retries:
                    logger.warning(
                        f"Transient error on {model_spec.name} ({e}). Retrying in {delay:.1f}s (Attempt {attempt}/{self.config.max_api_retries})..."
                    )
                    await asyncio.sleep(delay)
                    delay *= 2.0
                else:
                    raise e

        raise RuntimeError(f"Failed API interaction after {self.config.max_api_retries} retries.")

    async def resolve_chunk(
        self, text: str, rel_path: str, chunk_idx: int
    ) -> Tuple[str, ChunkResolutionStats]:
        stats = ChunkResolutionStats(total_slots=SlotValidator.count_slots(text))
        if stats.total_slots == 0:
            return text, stats

        current_text = text
        attempt = 0

        while attempt < self.config.max_validation_attempts:
            matches = SlotValidator.find_slots(current_text)
            if not matches:
                break

            attempt += 1
            full_prompt = f"{self.SYSTEM_INSTRUCTION}\n\nLatin Passage to Process:\n{current_text}"

            try:
                model_used, interaction = await self._call_api_with_backoff(full_prompt)
                json_payload = self._clean_json_text(interaction.output_text)
                parsed = MacronResolution.model_validate_json(json_payload)
                model_outputs = parsed.resolutions
            except DailyQuotaExhaustedException:
                raise
            except Exception as e:
                stats.failed_attempts += 1
                logger.error(f"{rel_path} Chunk {chunk_idx} - Resolution failed on attempt {attempt}: {e}")
                continue

            valid_replacements: List[Tuple[int, int, str, str]] = []
            expected_idx = 0
            out_idx = 0

            num_slots = len(matches)
            num_outputs = len(model_outputs)

            resolved_slot_indices: set[int] = set()
            consumed_output_indices: set[int] = set()

            while out_idx < num_outputs and expected_idx < num_slots:
                if out_idx in consumed_output_indices:
                    out_idx += 1
                    continue

                while expected_idx < num_slots and expected_idx in resolved_slot_indices:
                    expected_idx += 1

                if expected_idx >= num_slots:
                    break

                output_word = model_outputs[out_idx]
                expected_slot = matches[expected_idx]

                if SlotValidator.validate(expected_slot.group(0), output_word):
                    valid_replacements.append(
                        (expected_slot.start(), expected_slot.end(), output_word, expected_slot.group(0))
                    )
                    resolved_slot_indices.add(expected_idx)
                    consumed_output_indices.add(out_idx)
                    expected_idx += 1
                    out_idx += 1
                    continue

                matching_future_indices = [
                    k
                    for k in range(expected_idx + 1, num_slots)
                    if k not in resolved_slot_indices
                    and SlotValidator.validate(matches[k].group(0), output_word)
                ]

                if not matching_future_indices:
                    out_idx += 1
                    continue

                if len(matching_future_indices) == 1:
                    target_idx = matching_future_indices[0]
                    target_slot = matches[target_idx]
                    valid_replacements.append(
                        (target_slot.start(), target_slot.end(), output_word, target_slot.group(0))
                    )
                    resolved_slot_indices.add(target_idx)
                    consumed_output_indices.add(out_idx)
                    expected_idx = target_idx + 1
                    out_idx += 1
                    continue

                target_raw_slot = matches[matching_future_indices[0]].group(0)

                s_equiv = [
                    k
                    for k in range(expected_idx, num_slots)
                    if k not in resolved_slot_indices
                    and matches[k].group(0) == target_raw_slot
                ]

                o_equiv = [
                    m
                    for m in range(out_idx, num_outputs)
                    if m not in consumed_output_indices
                    and SlotValidator.validate(target_raw_slot, model_outputs[m])
                ]

                if len(o_equiv) == len(s_equiv):
                    for slot_k, out_m in zip(s_equiv, o_equiv):
                        slot_obj = matches[slot_k]
                        word_val = model_outputs[out_m]
                        valid_replacements.append(
                            (slot_obj.start(), slot_obj.end(), word_val, slot_obj.group(0))
                        )
                        resolved_slot_indices.add(slot_k)
                        consumed_output_indices.add(out_m)

                    expected_idx = max(s_equiv) + 1
                    out_idx += 1
                else:
                    out_idx += 1

            if valid_replacements:
                valid_replacements.sort(key=lambda x: x[0], reverse=True)
                for start, end, replacement, raw_slot in valid_replacements:
                    current_text = current_text[:start] + replacement + current_text[end:]
                    self.audit_logger.log_resolved_slot(
                        rel_path=rel_path,
                        chunk_idx=chunk_idx,
                        attempt=attempt,
                        model_used=model_used,
                        slot_raw=raw_slot,
                        filled_value=replacement,
                    )
                stats.resolved_slots += len(valid_replacements)

        remaining = SlotValidator.find_slots(current_text)
        if remaining:
            unmasked_context = TextEscaper.unmask(current_text)
            for m in remaining:
                raw_slot = m.group(0)
                self.audit_logger.log_unfilled_slot(
                    rel_path=rel_path,
                    chunk_idx=chunk_idx,
                    max_attempts=self.config.max_validation_attempts,
                    slot_raw=raw_slot,
                    context_snippet=unmasked_context,
                )
            logger.warning(
                f"{rel_path} Chunk {chunk_idx} - {len(remaining)} slots remained unfilled after {self.config.max_validation_attempts} attempts."
            )

        return current_text, stats

# =====================================================================
# Pipeline Orchestration
# =====================================================================

class MacronCorpusPipeline:
    """Orchestrates corpus-wide macronization, handling priority scheduling, resumption, logs, and rate limits."""

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self.checkpoint_manager = CheckpointManager(self.config.checkpoint_file)
        self.state = self.checkpoint_manager.load()
        self.session_stats = RunSessionStats()
        self.priority_set: Set[str] = set()
        
        self.rate_limiter = MultiModelRateLimiter(AVAILABLE_MODELS, self.state, self.session_stats)
        self.audit_logger = AuditLogger(self.config.logs_dir)
        self.preprocessor = LatinPreprocessor()
        self.client = genai.Client()
        self.resolver = MacronResolverEngine(
            self.client, self.config, self.rate_limiter, self.audit_logger
        )

    def _ensure_input_repo(self) -> None:
        if not self.config.raw_dir.exists():
            logger.info(f"Input repository not found at '{self.config.raw_dir}'. Cloning from {self.config.raw_repo_url}...")
            self.config.raw_dir.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", "--depth", "1", self.config.raw_repo_url, str(self.config.raw_dir)],
                check=True,
            )

    def _import_priority_input_files(self) -> List[str]:
        """Copies any files from priority_inputs_dir to lat_text_latin_library/custom/."""
        imported_rel_paths: List[str] = []
        if not self.config.priority_inputs_dir.exists():
            return imported_rel_paths

        custom_target_dir = self.config.raw_dir / "custom"
        custom_target_dir.mkdir(parents=True, exist_ok=True)

        for src_path in self.config.priority_inputs_dir.rglob("*.txt"):
            if src_path.is_file():
                dest_path = custom_target_dir / src_path.name
                shutil.copy2(src_path, dest_path)
                rel_p = str(dest_path.relative_to(self.config.raw_dir))
                imported_rel_paths.append(rel_p)
                logger.info(f"Imported custom priority file '{src_path.name}' to '{rel_p}'")
        return imported_rel_paths

    def _load_priority_set(self) -> Set[str]:
        """Loads priority paths from priority.txt and imported custom files."""
        priority_paths: Set[str] = set()

        # Load imported files
        priority_paths.update(self._import_priority_input_files())

        # Load list from priority.txt
        if self.config.priority_file.exists():
            with open(self.config.priority_file, "r", encoding="utf-8") as f:
                for line in f:
                    cleaned = line.strip().lstrip("/")
                    if cleaned and not cleaned.startswith("#"):
                        priority_paths.add(cleaned)

        return priority_paths

    def _is_priority_file(self, raw_file: Path) -> bool:
        rel_str = str(raw_file.relative_to(self.config.raw_dir))
        return rel_str in self.priority_set or raw_file.name in self.priority_set

    def _sort_files_by_priority(self, raw_files: List[Path]) -> List[Path]:
        def sort_key(p: Path) -> Tuple[int, str]:
            rel_str = str(p.relative_to(self.config.raw_dir))
            is_priority = 0 if self._is_priority_file(p) else 1
            return (is_priority, rel_str)

        return sorted(raw_files, key=sort_key)

    def generate_chunks(self, raw_text: str) -> Generator[str, None, None]:
        paragraphs = raw_text.split("\n")
        current_chunk: List[str] = []
        current_tokens = 0
        current_slots = 0

        for paragraph in paragraphs:
            escaped_p = TextEscaper.escape_raw_brackets(paragraph)
            masked_p = TextEscaper.mask(escaped_p)
            annotated_p = self.preprocessor.process_paragraph(masked_p)

            p_str = annotated_p.strip()
            if not p_str:
                if current_chunk:
                    current_chunk.append("")
                continue

            p_tokens = TextChunker.estimate_tokens(p_str)
            p_slots = SlotValidator.count_slots(p_str)

            if current_chunk and (
                current_tokens + p_tokens > self.config.max_tokens_per_chunk
                or current_slots + p_slots > self.config.max_slots_per_chunk
            ):
                yield "\n".join(current_chunk)
                current_chunk = [p_str]
                current_tokens = p_tokens
                current_slots = p_slots
            else:
                current_chunk.append(p_str)
                current_tokens += p_tokens
                current_slots += p_slots

        if current_chunk:
            yield "\n".join(current_chunk)

    def _push_in_script_checkpoint(self) -> None:
        """Executes git commit and push directly after processing a file."""
        try:
            # Commit and push runner repo state (data/ checkpoint & logs)
            subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False)
            subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False)
            subprocess.run(["git", "add", "data/"], check=False)
            subprocess.run(["git", "commit", "-m", "chore: update macronization checkpoint"], check=False)
            subprocess.run(["git", "push"], check=False)

            # Commit and push output repo processed texts
            if self.config.macronized_dir.exists():
                subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=self.config.macronized_dir, check=False)
                subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=self.config.macronized_dir, check=False)
                subprocess.run(["git", "add", "."], cwd=self.config.macronized_dir, check=False)
                subprocess.run(["git", "commit", "-m", "chore: automated corpus update"], cwd=self.config.macronized_dir, check=False)
                subprocess.run(["git", "push"], cwd=self.config.macronized_dir, check=False)
        except Exception as e:
            logger.warning(f"In-script git push encountered non-fatal error: {e}")

    async def _process_file(self, raw_file: Path) -> None:
        rel_path = str(raw_file.relative_to(self.config.raw_dir))
        out_file = self.config.macronized_dir / rel_path
        out_file.parent.mkdir(parents=True, exist_ok=True)

        is_priority = self._is_priority_file(raw_file)

        raw_text = raw_file.read_text(encoding="utf-8")
        chunks = list(self.generate_chunks(raw_text))
        total_chunks = len(chunks)

        last_chunk = self.state.file_progress.get(rel_path, -1)
        if last_chunk == -1 and not out_file.exists():
            out_file.write_text("", encoding="utf-8")

        if last_chunk >= 0:
            status_msg = f"INTERRUPTED PREVIOUSLY (resuming from chunk {last_chunk + 2}/{total_chunks}, {last_chunk + 1} chunks completed previously)"
        else:
            status_msg = f"FRESH START (0/{total_chunks} chunks completed)"

        logger.info(f"Processing file: {rel_path} | Total chunks: {total_chunks} | Status: {status_msg}")

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for current_idx, chunk_text in enumerate(chunks):
            if current_idx <= last_chunk:
                continue

            if is_priority:
                self.session_stats.priority_files_worked_on[rel_path] = f"In Progress (Chunk {current_idx + 1}/{total_chunks})"

            resolved_chunk, stats = await self.resolver.resolve_chunk(
                chunk_text, rel_path=rel_path, chunk_idx=current_idx + 1
            )
            unmasked_chunk = TextEscaper.unmask(resolved_chunk)

            with open(out_file, "a", encoding="utf-8") as f:
                f.write(unmasked_chunk + "\n\n")

            self.state.file_progress[rel_path] = current_idx

            chunk_bytes = len(chunk_text.encode("utf-8"))
            self.session_stats.bytes_processed_today += chunk_bytes
            self.state.daily_bytes_processed[today_str] = (
                self.state.daily_bytes_processed.get(today_str, 0) + chunk_bytes
            )

            self.checkpoint_manager.save(self.state)

            self.session_stats.chunks_processed_today += 1
            self.session_stats.slots_resolved_today += stats.resolved_slots
            self.session_stats.slots_unfilled_today += (stats.total_slots - stats.resolved_slots)

            tqdm.write(
                f"[{rel_path}] Chunk {current_idx + 1}/{total_chunks}: Resolved {stats.resolved_slots}/{stats.total_slots} slots."
            )

        self.state.completed_files.append(rel_path)
        self.checkpoint_manager.save(self.state)
        self.session_stats.files_processed_today += 1

        if is_priority:
            self.session_stats.priority_files_worked_on[rel_path] = "Completed"

        logger.info(f"Successfully finished file: {rel_path}")
        self._push_in_script_checkpoint()

    def _print_run_summary(self, all_raw_files: List[Path]) -> None:
        elapsed = time.time() - self.session_stats.start_time
        total_files = len(all_raw_files)

        # Corpus Volume (GB) Calculations
        total_bytes = sum(f.stat().st_size for f in all_raw_files)
        total_gb = total_bytes / (1024 ** 3)

        completed_bytes = sum(
            f.stat().st_size
            for f in all_raw_files
            if str(f.relative_to(self.config.raw_dir)) in self.state.completed_files
        )
        completed_gb = completed_bytes / (1024 ** 3)
        remaining_bytes = max(0, total_bytes - completed_bytes)
        remaining_gb = remaining_bytes / (1024 ** 3)

        total_completed_files = len(self.state.completed_files)
        file_pct = (total_completed_files / total_files * 100) if total_files > 0 else 100.0
        bytes_pct = (completed_bytes / total_bytes * 100) if total_bytes > 0 else 100.0

        # Multi-day Average Throughput Calculation
        daily_history = self.state.daily_bytes_processed
        active_days = [b for b in daily_history.values() if b > 0]
        
        if active_days:
            avg_bytes_per_day = sum(active_days) / len(active_days)
        else:
            avg_bytes_per_day = self.session_stats.bytes_processed_today

        avg_mb_per_day = avg_bytes_per_day / (1024 ** 2)
        est_days_left = (remaining_bytes / avg_bytes_per_day) if avg_bytes_per_day > 0 else 0.0

        # Priority Files Analysis
        priority_raw_files = [f for f in all_raw_files if self._is_priority_file(f)]
        total_p_files = len(priority_raw_files)
        completed_p_files = [
            f for f in priority_raw_files
            if str(f.relative_to(self.config.raw_dir)) in self.state.completed_files
        ]
        completed_p_count = len(completed_p_files)
        remaining_p_count = total_p_files - completed_p_count
        p_pct = (completed_p_count / total_p_files * 100) if total_p_files > 0 else 100.0

        processed_today_mb = self.session_stats.bytes_processed_today / (1024 ** 2)

        summary = f"""
======================================================================
                     DAILY RUN PROGRESS SUMMARY                       
======================================================================
  * Run Duration              : {elapsed / 60.0:.2f} minutes
  * Files Processed Today    : {self.session_stats.files_processed_today}
  * Chunks Processed Today   : {self.session_stats.chunks_processed_today}
  * Volume Processed Today   : {processed_today_mb:.2f} MB
  * Slots Resolved Today     : {self.session_stats.slots_resolved_today}
  * Slots Unfilled Today     : {self.session_stats.slots_unfilled_today}
  --------------------------------------------------------------------
  * Corpus Total Size         : {total_gb:.3f} GB ({total_files} files)
  * Total Volume Completed    : {completed_gb:.3f} GB ({total_completed_files}/{total_files} files - {bytes_pct:.2f}%)
  * Volume Remaining          : {remaining_gb:.3f} GB ({total_files - total_completed_files} files)
  * Multi-Day Avg Speed       : {avg_mb_per_day:.2f} MB/day (over {len(active_days)} active days)
  * Estimated Days Remaining  : {est_days_left:.1f} days
  --------------------------------------------------------------------
  * Priority Files Overview   : {completed_p_count} / {total_p_files} completed ({p_pct:.1f}%) | {remaining_p_count} remaining
"""
        if self.session_stats.priority_files_worked_on:
            summary += "  * Priority Files Worked On Today:\n"
            for p_file, status in self.session_stats.priority_files_worked_on.items():
                summary += f"    - {p_file}: {status}\n"
        else:
            summary += "  * Priority Files Worked On Today: None\n"

        summary += "  --------------------------------------------------------------------\n"
        summary += "  * API Calls Executed Today  :\n"
        for model, count in self.session_stats.api_calls_by_model.items():
            summary += f"    - {model}: {count} calls\n"

        summary += "======================================================================\n"

        logger.info(summary)
        print(summary)

        # Output to GitHub Step Summary if running in GitHub Actions
        gh_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if gh_summary_path:
            with open(gh_summary_path, "a", encoding="utf-8") as f:
                f.write("### 📊 Daily Macronization Progress Summary\n")
                f.write(f"- **Volume Processed Today**: {processed_today_mb:.2f} MB\n")
                f.write(f"- **Overall Progress**: {completed_gb:.3f} / {total_gb:.3f} GB ({bytes_pct:.1f}%)\n")
                f.write(f"- **Priority Files**: {completed_p_count}/{total_p_files} completed ({p_pct:.1f}%)\n")
                f.write(f"- **Multi-Day Processing Rate**: ~{avg_mb_per_day:.2f} MB/day\n")
                f.write(f"- **Estimated Days Remaining**: ~{est_days_left:.1f} days\n")

    async def run(self) -> None:
        self._ensure_input_repo()

        all_raw_files = [
            f for f in self.config.raw_dir.rglob("*.txt")
            if not any(part.startswith(".") for part in f.relative_to(self.config.raw_dir).parts)
        ]
        total_files = len(all_raw_files)
        logger.info(f"Found {total_files} total raw text files in corpus.")

        self.priority_set = self._load_priority_set()
        if self.priority_set:
            logger.info(f"Loaded {len(self.priority_set)} priority file rules.")

        sorted_files = self._sort_files_by_priority(all_raw_files)

        pending_files = [
            f for f in sorted_files
            if str(f.relative_to(self.config.raw_dir)) not in self.state.completed_files
        ]

        logger.info(f"{len(pending_files)} files remaining to process.")

        try:
            for raw_file in pending_files:
                elapsed = time.time() - self.session_stats.start_time
                if elapsed >= self.config.max_run_seconds:
                    logger.info(
                        f"Execution time limit reached ({elapsed:.1f}s >= {self.config.max_run_seconds:.1f}s). Stopping run gracefully."
                    )
                    break
                await self._process_file(raw_file)
            else:
                logger.info("Corpus processing complete! All files processed.")
        except DailyQuotaExhaustedException as e:
            logger.info(f"Stopping execution for today: {e}")
        finally:
            self.checkpoint_manager.save(self.state)
            self._print_run_summary(all_raw_files)


def setup_signal_handlers(pipeline_ref: List[Optional[MacronCorpusPipeline]]) -> None:
    def handle_exit(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.warning(f"Received exit signal {sig_name} ({signum}). Preserving checkpoint state...")
        if pipeline_ref[0]:
            pipeline_ref[0].checkpoint_manager.save(pipeline_ref[0].state)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily Latin Corpus Macronization Pipeline")
    parser.add_argument(
        "--priority-file",
        type=Path,
        default=Path("data/priority.txt"),
        help="Path to text file containing priority relative file paths.",
    )
    parser.add_argument(
        "--priority-inputs",
        type=Path,
        default=Path("data/priority_inputs"),
        help="Directory containing custom external text files to prioritize.",
    )
    parser.add_argument(
        "--max-run-seconds",
        type=float,
        default=19800.0,
        help="Maximum run execution duration in seconds before stopping gracefully (default: 5.5h / 19800s).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    config = PipelineConfig(
        priority_file=args.priority_file,
        priority_inputs_dir=args.priority_inputs,
        max_run_seconds=args.max_run_seconds,
    )
    pipeline_container: List[Optional[MacronCorpusPipeline]] = [None]
    setup_signal_handlers(pipeline_container)

    pipeline = MacronCorpusPipeline(config=config)
    pipeline_container[0] = pipeline
    asyncio.run(pipeline.run())
    