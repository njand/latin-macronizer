import re
from html import escape

from . import postags
from .macronizer_token import Token
from .helpers import toascii, prefixeswithshortj


def match_casing(original, target):
    """Applies the capitalization style of original to target."""
    if not original or not target:
        return target
    if original.isupper():
        return target.upper()
    if original[0].isupper():
        return target[0].upper() + target[1:]
    return target


class Tokenization:
    def __init__(self, text):
        self.tokens = []

    def allwordforms(self):
        words = set()
        for token in self.tokens:
            if token.isword:
                words.add(toascii(token.text).lower())
        return words

    def show(self):
        for token in self.tokens[:500]:
            if token.isword:
                token.show()
            if token.endssentence:
                print()
        if len(self.tokens) > 500:
            print("... (truncated) ...")

    def addlemmas(self, wordlist):
        from .lemmas import lemma_frequency, word_lemma_freq, wordform_to_corpus_lemmas
        for token in self.tokens:
            wordform = toascii(token.text)
            best_lemma = "-"
            max_freq = -1
            if wordform in wordform_to_corpus_lemmas:
                for corpus_lemma in wordform_to_corpus_lemmas[wordform]:
                    if word_lemma_freq[(wordform, corpus_lemma)] > max_freq:
                        max_freq = word_lemma_freq[(wordform, corpus_lemma)]
                        best_lemma = corpus_lemma
            elif wordform.lower() in wordlist.formtolemmas:
                for lex_lemma in wordlist.formtolemmas[wordform.lower()]:
                    if lemma_frequency.get(lex_lemma, 0) > max_freq:
                        max_freq = lemma_frequency.get(lex_lemma, 0)
                        best_lemma = lex_lemma
            token.lemma = best_lemma

    def getaccents(self, wordlist):
        def levenshtein(s1, s2):
            if len(s1) < len(s2):
                return levenshtein(s2, s1)
            if len(s2) == 0:
                return len(s1)
            previous_row = range(len(s2) + 1)
            for i, c1 in enumerate(s1):
                current_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = previous_row[j + 1] + 1
                    deletions = current_row[j] + 1
                    substitutions = previous_row[j] + (c1 != c2)
                    current_row.append(min(insertions, deletions, substitutions))
                previous_row = current_row
            return previous_row[-1]

        from .macronized_endings import tag_to_endings
        from collections import defaultdict

        for token in self.tokens:
            if not token.isword:
                continue

            wordform = toascii(token.text)
            iscapital = wordform.istitle()
            wordform = wordform.lower()
            tag = token.tag
            lemma = token.lemma

            token.accented = []
            token.candidate_details = []

            if token.isenclitic:
                acc = "ve" if token.text.lower() == "ue" else token.text.lower()
                cased_acc = match_casing(token.text, acc)
                token.accented = [cased_acc]
                token.candidate_details = [(1.0, cased_acc)]

            elif token.text.lower() == "ne" and token.hasenclitic:
                cased_acc = match_casing(token.text, "ne")
                token.accented = ["ne"]
                token.candidate_details = [(1.0, cased_acc)]

            elif len(set(wordlist.formtoaccenteds[wordform])) == 1:
                acc = wordlist.formtoaccenteds[wordform][0]
                token.accented = [acc]
                clean_acc = postags.unicodeaccents(acc.replace("_^", "").replace("^", ""))
                cased_acc = match_casing(token.text, clean_acc)
                token.candidate_details = [(1.0, cased_acc)]

            elif wordform in wordlist.formtotaglemmaaccents:
                best_casedist = min(
                    (0 if iscapital == lexlemma.istitle() or (token.startssentence and iscapital) else 1)
                    for (_, lexlemma, _) in wordlist.formtotaglemmaaccents[wordform]
                )

                tag_to_forms = defaultdict(set)
                for (lextag, lexlemma, accented) in wordlist.formtotaglemmaaccents[wordform]:
                    casedist = 0 if iscapital == lexlemma.istitle() or (token.startssentence and iscapital) else 1
                    if casedist == best_casedist:
                        clean_acc = postags.unicodeaccents(accented.replace("_^", "").replace("^", ""))
                        cased_acc = match_casing(token.text, clean_acc)
                        tag_to_forms[lextag].add(cased_acc)

                form_probs = defaultdict(float)
                tag_probs = getattr(token, 'tag_probs', {token.tag: getattr(token, 'tag_confidence', 1.0)})

                for lextag, forms in tag_to_forms.items():
                    if not forms:
                        continue
                    tag_prob = tag_probs.get(lextag, 0.0)
                    split_prob = tag_prob / len(forms)
                    for f in forms:
                        form_probs[f] += split_prob

                all_forms = list(set(f for forms in tag_to_forms.values() for f in forms))
                if len(all_forms) == 1:
                    form_probs[all_forms[0]] = 1.0

                token.candidate_details = [(form_probs.get(f, 0.0), f) for f in all_forms]
                token.candidate_details.sort(key=lambda x: x[0], reverse=True)
                token.accented = [f for prob, f in token.candidate_details]

            else:
                cased_text = match_casing(token.text, postags.unicodeaccents(token.text))
                token.accented = [token.text]
                token.candidate_details = [(1.0, cased_text)]

                if any(i in token.text for i in "aeiouyAEIOUY"):
                    for accented_ending in tag_to_endings.get(tag, []):
                        plain_ending = accented_ending.replace("_", "").replace("^", "")
                        if wordform.endswith(plain_ending):
                            acc = wordform[:-len(plain_ending)] + accented_ending
                            token.accented = [acc]
                            clean_acc = postags.unicodeaccents(acc.replace("_^", "").replace("^", ""))
                            cased_acc = match_casing(token.text, clean_acc)
                            token.candidate_details = [(1.0, cased_acc)]
                            break
                    token.isunknown = True
                    
    def macronize(self, domacronize, alsomaius, performutov, performitoj):
        for token in self.tokens:
            token.macronize(domacronize, alsomaius, performutov, performitoj)

    def detokenize(self, markambiguous, confidence_threshold=0.8, output_format="inline"):
        import json
        import re
        from html import escape

        result = []
        json_tokens = []

        macron_chars = set("āēīōūȳĀĒĪŌŪȲ\u0304")

        def count_macrons(text):
            return sum(1 for char in text if char in macron_chars)

        for token in self.tokens:
            if not token.isword:
                macronized_text = escape(token.macronized) if (output_format == "html" and markambiguous) else token.macronized
                if output_format == "json":
                    json_tokens.append({"text": token.text, "macronized": token.macronized, "is_word": False})
                else:
                    result.append(macronized_text)
                continue

            unicodetext = postags.unicodeaccents(token.macronized)

            if not markambiguous:
                if output_format == "json":
                    json_tokens.append({
                        "text": token.text,
                        "macronized": unicodetext,
                        "is_word": True,
                        "is_ambiguous": False,
                        "confidence": getattr(token, 'tag_confidence', 1.0),
                        "candidates": [{"form": unicodetext, "probability": 1.0}]
                    })
                else:
                    result.append(unicodetext)
                continue

            # Read pre-computed candidate probabilities (form -> probability)
            cand_probs = getattr(token, 'candidate_details', {})
            # Sort by highest probability first (-prob), then fewest macrons first
            sorted_cands = sorted(cand_probs, key=lambda x: (-x[0], count_macrons(x[1])))
            sorted_candidates = [match_casing(token.text, form) for _prob, form in sorted_cands]
            top_prob = sorted_cands[0][0] if sorted_cands else 0.0

            # Threshold-based ambiguity resolution
            if top_prob >= confidence_threshold:
                # Keep top form, plus any exact ties for top form
                active_candidates = [match_casing(token.text, form) for prob, form in sorted_cands if prob == top_prob]
            else:
                # Low confidence: mark ambiguous across all candidates
                active_candidates = [match_casing(token.text, form) for _prob, form in sorted_cands]

            is_unknown = getattr(token, 'isunknown', False)
            is_ambiguous = len(active_candidates) > 1
            top_form = active_candidates[0] if active_candidates else unicodetext

            if output_format == "inline":
                if is_unknown:
                    result.append(f"[{top_form}]")
                elif is_ambiguous:
                    result.append(f"<{'|'.join(active_candidates)}>")
                else:
                    result.append(top_form)

            elif output_format == "html":
                formatted = re.sub(r"([āēīōūȳĀĒĪŌŪȲaeiouyAEIOUY])", "<span>\\1</span>", top_form)
                if is_unknown:
                    formatted = f'<span class="unknown">{formatted}</span>'
                elif is_ambiguous:
                    formatted = f'<span class="ambig">{formatted}</span>'
                else:
                    formatted = f'<span class="auto">{formatted}</span>'
                result.append(formatted)

            elif output_format == "json":
                json_tokens.append({
                    "text": token.text,
                    "macronized": top_form,
                    "is_word": True,
                    "is_ambiguous": is_ambiguous,
                    "is_unknown": is_unknown,
                    "confidence": getattr(token, 'tag_confidence', 0.0),
                    "candidates": [
                        {"form": match_casing(token.text, form), "probability": round(prob, 4)}
                        for prob, form in sorted_cands
                    ]
                })

        if output_format == "json":
            return json.dumps(json_tokens, ensure_ascii=False, indent=2)

        return "".join(result)
