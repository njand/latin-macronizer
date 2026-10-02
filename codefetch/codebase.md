You are a senior developer. You produce optimized, maintainable code that follows best practices. 

Your task is to review the current codebase and fix the current issues.

Current Issue:
<issue>
Run python scripts/gemini.py
  File "/home/runner/work/latin-macronizer/latin-macronizer/scripts/gemini.py", line 231
    text = re.sub(r"(?<!\\)\[", r"\[", text)         text = re.sub(r"(?<!\\)\]", r"\]", text)
                                                     ^^^^
SyntaxError: invalid syntax
Error: Process completed with exit code 1.
</issue>

Rules:
- Keep your suggestions concise and focused. Avoid unnecessary explanations or fluff. 
- Your output should be a series of specific, actionable changes.

When approaching this task:
1. Carefully review the provided code.
2. Identify the area thats raising this issue or error and provide a fix.
3. Consider best practices for the specific programming language used.
4. If you need to gather more information, write a troubleshooting script to inspect underlying data or test specific methods using toy data. Do not proceed to the solutions phase until you have collected enough data to be 100% confident your solution will work.

For each suggested change, provide:
1. A short description of the change (one line maximum).
2. The modified code block.

Use the following format for your output:

[Short Description]
```[language]:[path/to/file]
[code block]
```

Begin fixing the codebase provide your solutions.

My current codebase:
<current_codebase>
<source_code>
macronize_corpus.yml
```
name: Daily Corpus Macronization

on:
  schedule:
    # Runs daily at 09:00 UTC
    - cron: '0 9 * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  process-corpus:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout runner repository
        uses: actions/checkout@v4

      - name: Checkout output repository
        uses: actions/checkout@v4
        with:
          repository: 'njand/lat_text_latin_library_macronized'
          token: ${{ secrets.OUTPUT_REPO_TOKEN }}
          path: 'output_repo'

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies from pyproject.toml
        run: |
          python -m pip install --upgrade pip
          pip install .

      - name: Run Macronization Pipeline
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          python scripts/gemini.py

      - name: Commit & Push Progress Checkpoints (Runner Repo)
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "Update macronization state checkpoint"
          file_pattern: "data/"

      - name: Commit & Push Processed Texts (Output Repo)
        run: |
          cd output_repo
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add .
          git status
          git diff-index --quiet HEAD || (git commit -m "Automated daily corpus update" && git push)
```

pyproject.toml
```
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "latin-macronizer"
version = "0.1.0"
description = "Mark long vowels in Latin text"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "google-genai>=2.20.0",
    "la-core-web-lg @ https://huggingface.co/latincy/la_core_web_lg/resolve/main/la_core_web_lg-3.9.6-py3-none-any.whl",
    "pydantic>=2.13.4",
    "spacy>=3.8.16",
]

[tool.uv.sources]
la-core-web-lg = { url = "https://huggingface.co/latincy/la_core_web_lg/resolve/main/la_core_web_lg-3.9.6-py3-none-any.whl" }
```

latin_macronizer/extractlexicon.py
```
#!/usr/bin/python
# -*- coding: utf-8 -*-

import postags
from collections import defaultdict
import xml.etree.ElementTree as ET
import pprint

pp = pprint.PrettyPrinter()

tag_to_accents = defaultdict(list)
with open('macrons.txt', 'r', encoding='utf-8') as macrons_file, \
     open('rftagger-lexicon.txt', 'w', encoding='utf-8') as lexicon_file:
    for line in macrons_file:
        [wordform, tag, lemma, accented] = line.split()
        accented = accented.replace('_^', '').replace('^', '')
        tag_to_accents[tag].append(postags.unicodeaccents(accented))
        if accented[0].isupper():
            wordform = wordform.title()
        tag = '.'.join(list(tag))
        lexicon_file.write("%s\t%s\t%s\n" % (wordform, tag, lemma))


with open('macronized_endings.py', 'w', encoding='utf-8') as endings_file:
    endings_file.write('tag_to_endings = {\n')
    for tag in sorted(tag_to_accents):
        ending_freqs = defaultdict(int)
        for accented in tag_to_accents[tag]:
            for i in range(1, min(len(accented)-3, 12)):
                ending = accented[-i:]
                ending_freqs[ending] += 1
        relevant_endings = []
        for ending in ending_freqs:
            ending_without_macrons = postags.removemacrons(ending)
            if ending[0] != ending_without_macrons[0] and ending_freqs[ending] > ending_freqs.get(ending_without_macrons, 1):
                relevant_endings.append(ending)
        cleaned_list = [str(postags.escape_macrons(ending)) for ending in sorted(relevant_endings, key=lambda x: (-len(x), x))]
        endings_file.write("  '%s': %s,\n" % (str(tag), cleaned_list))
    endings_file.write('}\n')


with open('ldt-corpus.txt', 'w', encoding='utf-8') as pos_corpus_file:
    xsegment = ''
    xsegmentbehind = ''
    for f in ['1999.02.0010',
              '2008.01.0002',
              '2007.01.0001',
              '1999.02.0060',
              'phi0448.phi001.perseus-lat1',
              'phi0620.phi001.perseus-lat1',
              'phi0959.phi006.perseus-lat1',
              'phi0690.phi003.perseus-lat1']:
        bank = ET.parse('treebank_data/v1.6/latin/data/%s.tb.xml' % f)
        for sentence in bank.getroot():
            for token in sentence.findall('word'):
                idnum = int(token.get('id', '_'))
                head = int(token.get('head', '_'))
                relation = token.get('relation', '_')
                form = token.get('form', '_')
                lemma = token.get('lemma', form)
                postag = token.get('postag', '_')
                if form != '|' and postag != '' and postag != '_':
                    if lemma == 'other' and relation == 'XSEG' and head == idnum + 1:
                        xsegment = form
                        continue
                    if (lemma == 'que1' or lemma == 'ne1') and relation == 'XSEG' and head == idnum + 1:
                        xsegmentbehind = form
                        continue
                    postag = '.'.join(list(postag))
                    lemma = lemma.replace('#', '').replace('1', '').replace(' ', '+')
                    word = xsegment + form + xsegmentbehind
                    pos_corpus_file.write('%s\t%s\t%s\n' % (word, postag, lemma))
                    xsegment = ''
                    xsegmentbehind = ''
            pos_corpus_file.write('.\tu.-.-.-.-.-.-.-.-\tPERIOD1\n')
            pos_corpus_file.write('\n')
    with open('corpus-supplement.txt', 'r', encoding='utf-8') as supplement:
        for line in supplement:
            pos_corpus_file.write(line)


lemma_frequency = defaultdict(int)
word_lemma_freq = defaultdict(int)
wordform_to_corpus_lemmas = defaultdict(list)
with open('ldt-corpus.txt', 'r', encoding='utf-8') as pos_corpus_file:
    for line in pos_corpus_file:
        if '\t' in line:
            [wordform, _, lemma] = line.strip().split('\t')
            wordform = str(wordform)
            lemma = str(lemma)
            lemma_frequency[lemma] += 1
            word_lemma_freq[(wordform, lemma)] += 1
            if lemma not in wordform_to_corpus_lemmas[wordform]:
                wordform_to_corpus_lemmas[wordform].append(lemma)
with open('lemmas.py', 'w', encoding='utf-8') as lemma_file:
    lemma_file.write('lemma_frequency = %s\n' % pp.pformat(dict(lemma_frequency)))
    lemma_file.write('word_lemma_freq = %s\n' % pp.pformat(dict(word_lemma_freq)))
    lemma_file.write('wordform_to_corpus_lemmas = %s\n' % pp.pformat(dict(wordform_to_corpus_lemmas)))
```

latin_macronizer/helpers.py
```


prefixeswithshortj = ("bij", "fidej", "Foroj", "foroj", "ju_rej", "multij", "praej", "quadrij",
                      "rej", "retroj", "se_mij", "sesquij", "u_nij", "introj")


def toascii(txt):
    for source, replacement in [("æ", "ae"), ("Æ", "Ae"), ("œ", "oe"), ("Œ", "Oe"),
                                ("ä", "a"), ("ë", "e"), ("ï", "i"), ("ö", "o"), ("ü", "u"), ("ÿ", "u")]:
        txt = txt.replace(source, replacement)
    return txt
```

latin_macronizer/latincy_mapper.py
```
def ud_label_to_ldt(label_str):
    """
    Translates a spaCy Universal Dependencies label string 
    into the 9-character LDT format.
    """
    tag = ['-'] * 9
    features = dict([f.split("=", 1) for f in label_str.split("|") if "=" in f])
    
    pos = features.get("POS")
    if pos == 'NOUN': tag[0] = 'n'
    elif pos == 'VERB': tag[0] = 'v'
    elif pos == 'ADJ': tag[0] = 'a'
    elif pos == 'ADV': tag[0] = 'd'
    elif pos in ['CCONJ', 'SCONJ']: tag[0] = 'c'
    elif pos == 'ADP': tag[0] = 'r'
    elif pos == 'PRON': tag[0] = 'p'
    elif pos == 'NUM': tag[0] = 'm'
    elif pos == 'INTJ': tag[0] = 'i'
    elif pos == 'PUNCT': tag[0] = 'u'
    elif pos == 'AUX': tag[0] = 'v'
    elif pos == 'PART': tag[0] = 'd'
    elif pos == 'DET': tag[0] = 'p'
    elif pos == 'PROPN': tag[0] = 'n'
    
    person = features.get("Person")
    if person: tag[1] = person[0]
        
    number = features.get("Number")
    if number == "Sing": tag[2] = 's'
    elif number == "Plur": tag[2] = 'p'
        
    tense = features.get("Tense")
    if tense == "Pres": tag[3] = 'p'
    elif tense == "Imp": tag[3] = 'i'
    elif tense == "Past": tag[3] = 'r'
    elif tense == "Pqp": tag[3] = 'l'
    elif tense == "Fut": tag[3] = 'f'
        
    mood = features.get("Mood")
    verbform = features.get("VerbForm")
    if mood == "Ind": tag[4] = 'i'
    elif mood == "Sub": tag[4] = 's'
    elif mood == "Imp": tag[4] = 'm'
    elif verbform == "Inf": tag[4] = 'n'
    elif verbform == "Part": tag[4] = 'p'
    elif verbform == "Ger": tag[4] = 'd'
    elif verbform == "Gdv": tag[4] = 'g'
    elif verbform == "Sup": tag[4] = 'u'
        
    voice = features.get("Voice")
    if voice == "Act": tag[5] = 'a'
    elif voice == "Pass": tag[5] = 'p'
        
    gender = features.get("Gender")
    if gender == "Masc": tag[6] = 'm'
    elif gender == "Fem": tag[6] = 'f'
    elif gender == "Neut": tag[6] = 'n'
        
    case = features.get("Case")
    if case == "Nom": tag[7] = 'n'
    elif case == "Gen": tag[7] = 'g'
    elif case == "Dat": tag[7] = 'd'
    elif case == "Acc": tag[7] = 'a'
    elif case == "Abl": tag[7] = 'b'
    elif case == "Voc": tag[7] = 'v'
    elif case == "Loc": tag[7] = 'l'
        
    degree = features.get("Degree")
    if degree == "Cmp": tag[8] = 'c'
    elif degree == "Sup": tag[8] = 's'
        
    return "".join(tag)

def spacy_to_ldt(token):
    """
    Translates spaCy Universal Dependencies (UPOS + UFeats) 
    into the 9-character LDT format required by macrons.txt.
    """
    tag = ['-'] * 9
    
    pos = token.pos_
    if pos == 'NOUN': tag[0] = 'n'
    elif pos == 'VERB': tag[0] = 'v'
    elif pos == 'ADJ': tag[0] = 'a'
    elif pos == 'ADV': tag[0] = 'd'
    elif pos in ['CCONJ', 'SCONJ']: tag[0] = 'c'
    elif pos == 'ADP': tag[0] = 'r'
    elif pos == 'PRON': tag[0] = 'p'
    elif pos == 'NUM': tag[0] = 'm'
    elif pos == 'INTJ': tag[0] = 'i'
    elif pos == 'PUNCT': tag[0] = 'u'
    elif pos == 'AUX': tag[0] = 'v'
    elif pos == 'PART': tag[0] = 'd'
    elif pos == 'DET': tag[0] = 'p'
    elif pos == 'PROPN': tag[0] = 'n'
    
    morph = token.morph
    
    person = morph.get("Person")
    if person: tag[1] = person[0]
        
    number = morph.get("Number")
    if number == ["Sing"]: tag[2] = 's'
    elif number == ["Plur"]: tag[2] = 'p'
        
    tense = morph.get("Tense")
    if tense == ["Pres"]: tag[3] = 'p'
    elif tense == ["Imp"]: tag[3] = 'i'
    elif tense == ["Past"]: tag[3] = 'r'
    elif tense == ["Pqp"]: tag[3] = 'l'
    elif tense == ["Fut"]: tag[3] = 'f'
        
    mood = morph.get("Mood")
    verbform = morph.get("VerbForm")
    if mood == ["Ind"]: tag[4] = 'i'
    elif mood == ["Sub"]: tag[4] = 's'
    elif mood == ["Imp"]: tag[4] = 'm'
    elif verbform == ["Inf"]: tag[4] = 'n'
    elif verbform == ["Part"]: tag[4] = 'p'
    elif verbform == ["Ger"]: tag[4] = 'd'
    elif verbform == ["Gdv"]: tag[4] = 'g'
    elif verbform == ["Sup"]: tag[4] = 'u'
        
    voice = morph.get("Voice")
    if voice == ["Act"]: tag[5] = 'a'
    elif voice == ["Pass"]: tag[5] = 'p'
        
    gender = morph.get("Gender")
    if gender == ["Masc"]: tag[6] = 'm'
    elif gender == ["Fem"]: tag[6] = 'f'
    elif gender == ["Neut"]: tag[6] = 'n'
        
    case = morph.get("Case")
    if case == ["Nom"]: tag[7] = 'n'
    elif case == ["Gen"]: tag[7] = 'g'
    elif case == ["Dat"]: tag[7] = 'd'
    elif case == ["Acc"]: tag[7] = 'a'
    elif case == ["Abl"]: tag[7] = 'b'
    elif case == ["Voc"]: tag[7] = 'v'
    elif case == ["Loc"]: tag[7] = 'l'
        
    degree = morph.get("Degree")
    if degree == ["Cmp"]: tag[8] = 'c'
    elif degree == ["Sup"]: tag[8] = 's'
        
    return "".join(tag)

def ldt_to_ud(ldt_tag):
    """
    Translates a 9-character LDT tag string into a Universal Dependencies (UD) feature string.
    """
    if not ldt_tag or len(ldt_tag) < 9:
        return ""
    
    pos_map = {'n': 'NOUN', 'v': 'VERB', 'a': 'ADJ', 'd': 'ADV', 'c': 'CCONJ', 
               'r': 'ADP', 'p': 'PRON', 'm': 'NUM', 'i': 'INTJ', 'u': 'PUNCT'}
    person_map = {'1': '1', '2': '2', '3': '3'}
    number_map = {'s': 'Sing', 'p': 'Plur'}
    tense_map = {'p': 'Pres', 'i': 'Imp', 'r': 'Past', 'l': 'Pqp', 'f': 'Fut'}
    mood_map = {'i': ('Mood', 'Ind'), 's': ('Mood', 'Sub'), 'm': ('Mood', 'Imp'), 
                'n': ('VerbForm', 'Inf'), 'p': ('VerbForm', 'Part'), 'd': ('VerbForm', 'Ger'), 
                'g': ('VerbForm', 'Gdv'), 'u': ('VerbForm', 'Sup')}
    voice_map = {'a': 'Act', 'p': 'Pass'}
    gender_map = {'m': 'Masc', 'f': 'Fem', 'n': 'Neut'}
    case_map = {'n': 'Nom', 'g': 'Gen', 'd': 'Dat', 'a': 'Acc', 'b': 'Abl', 'v': 'Voc', 'l': 'Loc'}
    degree_map = {'c': 'Cmp', 's': 'Sup'}

    features = []
    pos = pos_map.get(ldt_tag[0])
    if pos:
        features.append(f"POS={pos}")
    if ldt_tag[1] in person_map:
        features.append(f"Person={person_map[ldt_tag[1]]}")
    if ldt_tag[2] in number_map:
        features.append(f"Number={number_map[ldt_tag[2]]}")
    if ldt_tag[3] in tense_map:
        features.append(f"Tense={tense_map[ldt_tag[3]]}")
    if ldt_tag[4] in mood_map:
        k, v = mood_map[ldt_tag[4]]
        features.append(f"{k}={v}")
    if ldt_tag[5] in voice_map:
        features.append(f"Voice={voice_map[ldt_tag[5]]}")
    if ldt_tag[6] in gender_map:
        features.append(f"Gender={gender_map[ldt_tag[6]]}")
    if ldt_tag[7] in case_map:
        features.append(f"Case={case_map[ldt_tag[7]]}")
    if ldt_tag[8] in degree_map:
        features.append(f"Degree={degree_map[ldt_tag[8]]}")

    return "|".join(features)
```

latin_macronizer/macronizer.py
```
import spacy
from html import escape
import numpy as np
from collections import defaultdict


from .latincy_mapper import spacy_to_ldt, ldt_to_ud
from . import postags
from .wordlist import Wordlist
from .tokenization import Tokenization
from .macronizer_token import Token
from .helpers import toascii
from .scansion import scanverses

def touiorthography(txt):
    for source, replacement in [("v", "u"), ("U", "V"), ("j", "i"), ("J", "I")]:
        txt = txt.replace(source, replacement)
    return txt


class Macronizer:
    def __init__(self, db_path=None, latincy_model="la_core_web_lg"):
        self.wordlist = Wordlist(db_path)
        self.tokenization = Tokenization("")
        self.nlp = spacy.load(latincy_model)

        if not spacy.tokens.Token.has_extension("confidence"):
            spacy.tokens.Token.set_extension("confidence", default=1.0, force=True)

    def settext(self, text):
        self.tokenization = Tokenization("")
        doc = self.nlp(text)
        
        sentencehasended = True
        doc_internal_tokens = []

        for spacy_token in doc:
            internal_token = Token(spacy_token.text)
            doc_internal_tokens.append(internal_token)
            if internal_token.isword:
                internal_token.tag = spacy_to_ldt(spacy_token)
                
                if sentencehasended:
                    internal_token.startssentence = True
                sentencehasended = False
            elif spacy_token.is_punct and spacy_token.text in '.;:?!':
                internal_token.endssentence = True
                sentencehasended = True
                
            self.tokenization.tokens.append(internal_token)
            
            if spacy_token.whitespace_:
                space_token = Token(spacy_token.whitespace_)
                self.tokenization.tokens.append(space_token)

        self.wordlist.loadwords(self.tokenization.allwordforms())
        
        tag_probs_list, tag_ud_maps = self._extract_tag_probabilities(doc)
        for internal_token, tag_probs, tag_ud_map in zip(doc_internal_tokens, tag_probs_list, tag_ud_maps):
            if internal_token.isword:
                internal_token.tag_probs = tag_probs
                internal_token.tag_ud_map = tag_ud_map

        self.tokenization.addlemmas(self.wordlist)
        self.tokenization.getaccents(self.wordlist)
        self._update_token_confidences()
        
    def _update_token_confidences(self):
        KNOWN_ENCLITICS = {"que", "ne", "ve", "st"}
        for token in self.tokenization.tokens:
            if token.isword:
                if token.text.lower() in KNOWN_ENCLITICS:
                    token.isenclitic = True
                    token.enclitic = True
                    token.isunknown = False
                forms, confidence, candidates = self._compute_form_confidences(token)
                token.accented = forms
                token.tag_confidence = confidence
                token.candidates = candidates

    def _compute_form_confidences(self, token):
        wordform = token.text.lower()
        entries = self.wordlist.formtotaglemmaaccents.get(wordform, [])

        if not entries:
            if hasattr(token, 'accented') and token.accented:
                forms = list(dict.fromkeys(token.accented))
            else:
                forms = [postags.unicodeaccents(token.text)]
            candidates = [{"form": f, "probability": 1.0 / len(forms), "ud_tag": getattr(token, 'tag', '')} for f in forms]
            return forms, (1.0 if len(forms) == 1 else 1.0 / len(forms)), candidates

        tag_to_entries = defaultdict(list)
        form_morphtags = defaultdict(list)
        for morphtag, lemma, accented in entries:
            cleaned_accented = accented.replace('_^', '').replace('^', '')
            form = postags.unicodeaccents(cleaned_accented)
            if token.text[0].isupper():
                form = form.capitalize()
            else:
                form = form.lower()
            tag_to_entries[morphtag].append(form)
            form_morphtags[form].append(morphtag)

        tag_probs = getattr(token, 'tag_probs', {}) or {}
        form_raw_probs = defaultdict(float)
        all_forms = []

        for morphtag, form_list in tag_to_entries.items():
            tag_prob = tag_probs.get(morphtag, 0.0)
            unique_forms_in_tag = list(dict.fromkeys(form_list))
            k = len(unique_forms_in_tag)
            share = tag_prob / k if k > 0 else 0.0
            for form in unique_forms_in_tag:
                form_raw_probs[form] += share
                if form not in all_forms:
                    all_forms.append(form)

        total_raw_prob = sum(form_raw_probs.values())
        if total_raw_prob > 0:
            form_confidences = {f: form_raw_probs[f] / total_raw_prob for f in all_forms}
        else:
            uniform_prob = 1.0 / len(all_forms) if all_forms else 1.0
            form_confidences = {f: uniform_prob for f in all_forms}

        sorted_forms = sorted(all_forms, key=lambda f: form_confidences[f], reverse=True)
        top_confidence = form_confidences[sorted_forms[0]] if sorted_forms else 1.0

        tag_ud_map = getattr(token, 'tag_ud_map', {}) or {}
        candidates = []
        for form in sorted_forms:
            morphtags = form_morphtags.get(form, [])
            best_morphtag = max(morphtags, key=lambda m: tag_probs.get(m, 0.0)) if morphtags else None
            top_ud_tag = ""
            if best_morphtag:
                top_ud_tag = tag_ud_map.get(best_morphtag, ldt_to_ud(best_morphtag))
            candidates.append({
                "form": form,
                "probability": form_confidences[form],
                "ud_tag": top_ud_tag,
                "tag": top_ud_tag
            })

        return sorted_forms, top_confidence, candidates

    def scan(self, automatons):
        scanverses(self.tokenization.tokens, automatons)

    def gettext(
        self, 
        domacronize=True, 
        alsomaius=False, 
        performutov=False, 
        performitoj=False, 
        markambigs=False, 
        confidence_threshold=0.8,
        output_format="inline"
    ):
        self.tokenization.macronize(domacronize, alsomaius, performutov, performitoj)
        return self.tokenization.detokenize(
            markambigs, 
            confidence_threshold=confidence_threshold, 
            output_format=output_format
        )

    def macronize(
        self, 
        text, 
        domacronize=True, 
        alsomaius=False, 
        performutov=False, 
        performitoj=False, 
        markambigs=False, 
        confidence_threshold=0.8,
        output_format="inline"
    ):
        self.settext(text)
        return self.gettext(
            domacronize, alsomaius, performutov, performitoj, markambigs, confidence_threshold, output_format
        )

    def _extract_tag_probabilities(self, doc):
        """
        Passes a processed Doc through the model's tagging pipe to compute
        confidence scores for all morphological/POS predictions, mapped to LDT tags.
        """
        pipe_name = "morphologizer" if "morphologizer" in self.nlp.pipe_names else ("tagger" if "tagger" in self.nlp.pipe_names else None)
        if not pipe_name or len(doc) == 0:
            return [{}] * len(doc), [{}] * len(doc)

        try:
            from collections import defaultdict
            from .latincy_mapper import ud_label_to_ldt
            from .postags import tag_distance

            # Repopulate Tok2VecListener tensors for downstream components
            if "tok2vec" in self.nlp.pipe_names:
                self.nlp.get_pipe("tok2vec")(doc)

            pipe = self.nlp.get_pipe(pipe_name)
            raw_logits = pipe.model.predict([doc])

            def _to_numpy(obj):
                if hasattr(obj, "data"):
                    obj = obj.data
                if hasattr(obj, "detach"):
                    obj = obj.detach().cpu().numpy()
                if hasattr(obj, "get"):
                    obj = obj.get()
                return np.asarray(obj)

            if isinstance(raw_logits, (list, tuple)):
                if len(raw_logits) == 1:
                    logits = _to_numpy(raw_logits[0])
                else:
                    logits = np.vstack([_to_numpy(item) for item in raw_logits])
            else:
                logits = _to_numpy(raw_logits)

            if logits.ndim == 3 and logits.shape[0] == 1:
                logits = logits[0]

            if logits.ndim != 2 or logits.shape[0] != len(doc):
                return [{}] * len(doc), [{}] * len(doc)

            if np.all(logits >= 0) and np.allclose(np.sum(logits, axis=-1), 1.0, atol=1e-2):
                probs = logits
            else:
                shifted_logits = logits - np.max(logits, axis=-1, keepdims=True)
                exp_logits = np.exp(shifted_logits)
                probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)

            labels = pipe.labels
            label_to_ldt_map = {label: ud_label_to_ldt(label) for label in labels}

            token_probs = []
            token_ud_maps = []
            for token_idx, spacy_token in enumerate(doc):
                ldt_probs = defaultdict(float)
                ldt_top_ud = {}
                ldt_top_ud_prob = defaultdict(float)

                for class_idx, prob in enumerate(probs[token_idx]):
                    prob = float(prob)
                    if prob <= 0:
                        continue
                    ud_label = labels[class_idx]
                    ldt_tag = label_to_ldt_map[ud_label]
                    if prob > ldt_top_ud_prob[ldt_tag]:
                        ldt_top_ud_prob[ldt_tag] = prob
                        ldt_top_ud[ldt_tag] = ud_label

                wordform = spacy_token.text.lower()
                entries = self.wordlist.formtotaglemmaaccents.get(wordform, [])

                if not entries:
                    for class_idx, prob in enumerate(probs[token_idx]):
                        if prob > 0:
                            ldt_tag = label_to_ldt_map[labels[class_idx]]
                            ldt_probs[ldt_tag] += float(prob)
                else:
                    candidate_tags = list({entry[0] for entry in entries})

                    for class_idx, prob in enumerate(probs[token_idx]):
                        prob = float(prob)
                        if prob <= 0:
                            continue

                        model_tag = label_to_ldt_map[labels[class_idx]]

                        if model_tag in candidate_tags:
                            ldt_probs[model_tag] += prob
                        else:
                            distances = [tag_distance(model_tag, cand) for cand in candidate_tags]
                            min_dist = min(distances)
                            closest_tags = [cand for cand, dist in zip(candidate_tags, distances) if dist == min_dist]

                            share = prob / len(closest_tags)
                            for cand in closest_tags:
                                ldt_probs[cand] += share

                token_probs.append(dict(ldt_probs))
                token_ud_maps.append(ldt_top_ud)

            return token_probs, token_ud_maps

        except Exception:
            return [{}] * len(doc), [{}] * len(doc)

        
def evaluate(goldstandard, macronizedtext):
    vowelcount = 0
    lengthcorrect = 0
    outtext = []
    for (a, b) in zip(list(goldstandard), list(macronizedtext)):
        plaina = postags.removemacrons(a)
        plainb = postags.removemacrons(b)
        if touiorthography(toascii(plaina)) != touiorthography(toascii(plainb)):
            raise Exception("Error: Text mismatch.")
        if plaina in "AEIOUYaeiouy":
            vowelcount += 1
            if a == b:
                lengthcorrect += 1
        if toascii(touiorthography(a)) == toascii(touiorthography(b)):
            outtext.append(escape(b))
        else:
            outtext.append('<span class="wrong">%s</span>' % b)
    return lengthcorrect / float(vowelcount), "".join(outtext)
```

latin_macronizer/postags.py
```
#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2015 Johan Winge
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re

featMap = {}

PART_OF_SPEECH = "pos"
NOUN = "noun"
VERB = "verb"
ADJECTIVE = "adj"
ARTICLE = "article"
PARTICLE = "particle"
ADVERB = "adv"
ADVERBIAL = "adverbial"
CONJUNCTION = "conj"
PREPOSITION = "prep"
PRONOUN = "pron"
NUMERAL = "numeral"
INTERJECTION = "interj"
EXCLAMATION = "exclam"
PUNCTUATION = "punc"
featMap[PART_OF_SPEECH] = [NOUN, VERB, ADJECTIVE, ADVERB, ADVERBIAL, CONJUNCTION,
                           PREPOSITION, PRONOUN, NUMERAL, INTERJECTION, EXCLAMATION, PUNCTUATION]

PERSON = "person"
FIRST_PERSON = "1st"
SECOND_PERSON = "2nd"
THIRD_PERSON = "3rd"
featMap[PERSON] = [FIRST_PERSON, SECOND_PERSON, THIRD_PERSON]

NUMBER = "number"
SINGULAR = "sg"
PLURAL = "pl"
featMap[NUMBER] = [SINGULAR, PLURAL]

TENSE = "tense"
PRESENT = "pres"
IMPERFECT = "imperf"
PERFECT = "perf"
PLUPERFECT = "plup"
FUTURE_PERFECT = "futperf"
FUTURE = "fut"
featMap[TENSE] = [PRESENT, IMPERFECT, PERFECT, PLUPERFECT, FUTURE_PERFECT, FUTURE]

MOOD = "mood"
INDICATIVE = "ind"
SUBJUNCTIVE = "subj"
INFINITIVE = "inf"
IMPERATIVE = "imperat"
GERUNDIVE = "gerundive"
SUPINE = "supine"
GERUND = "gerund"
PARTICIPLE = "part"
featMap[MOOD] = [INDICATIVE, SUBJUNCTIVE, INFINITIVE, IMPERATIVE, GERUNDIVE,
                 SUPINE, GERUND, PARTICIPLE]

VOICE = "voice"
ACTIVE = "act"
PASSIVE = "pass"
featMap[VOICE] = [ACTIVE, PASSIVE]

GENDER = "gender"
MASCULINE = "masc"
FEMININE = "fem"
NEUTER = "neut"
featMap[GENDER] = [MASCULINE, FEMININE, NEUTER]

CASE = "case"
NOMINATIVE = "nom"
GENITIVE = "gen"
DATIVE = "dat"
ACCUSATIVE = "acc"
ABLATIVE = "abl"
VOCATIVE = "voc"
LOCATIVE = "loc"
featMap[CASE] = [NOMINATIVE, GENITIVE, DATIVE, ACCUSATIVE, ABLATIVE, VOCATIVE, LOCATIVE]

DEGREE = "degree"
POSITIVE = "pos"
COMPARATIVE = "comp"
SUPERLATIVE = "superl"
featMap[DEGREE] = [POSITIVE, COMPARATIVE, SUPERLATIVE]

REGULARITY = "regularity"
REGULAR = "reg"
IRREGULAR = "irreg"
featMap[REGULARITY] = [REGULAR, IRREGULAR]

LEMMA = "lemma"
ACCENTEDFORM = "accentedform"


def ldt_to_parse(ldt_tag):
    parse = {}

    if ldt_tag[0] == '-':
        pass
    elif ldt_tag[0] == 'n':
        parse[PART_OF_SPEECH] = NOUN
    elif ldt_tag[0] == 'v':
        parse[PART_OF_SPEECH] = VERB
    elif ldt_tag[0] == 't':
        parse[PART_OF_SPEECH] = VERB
        parse[MOOD] = PARTICIPLE
        print("Note: 'participle' used as POS")
    elif ldt_tag[0] == 'a':
        parse[PART_OF_SPEECH] = ADJECTIVE
    elif ldt_tag[0] == 'd':
        parse[PART_OF_SPEECH] = ADVERB
    elif ldt_tag[0] == 'c':
        parse[PART_OF_SPEECH] = CONJUNCTION
    elif ldt_tag[0] == 'r':
        parse[PART_OF_SPEECH] = PREPOSITION
    elif ldt_tag[0] == 'p':
        parse[PART_OF_SPEECH] = PRONOUN
    elif ldt_tag[0] == 'm':
        parse[PART_OF_SPEECH] = NUMERAL
    elif ldt_tag[0] == 'i':
        parse[PART_OF_SPEECH] = INTERJECTION
    elif ldt_tag[0] == 'e':
        parse[PART_OF_SPEECH] = EXCLAMATION
    elif ldt_tag[0] == 'u':
        parse[PART_OF_SPEECH] = PUNCTUATION
    else:
        print("Warning: unknown part of speech:", ldt_tag[0])

    if ldt_tag[1] == '-':
        pass
    elif ldt_tag[1] == '1':
        parse[PERSON] = FIRST_PERSON
    elif ldt_tag[1] == '2':
        parse[PERSON] = SECOND_PERSON
    elif ldt_tag[1] == '3':
        parse[PERSON] = THIRD_PERSON
    else:
        print("Warning: unknown person:", ldt_tag[1])

    if ldt_tag[2] == '-':
        pass
    elif ldt_tag[2] == 's':
        parse[NUMBER] = SINGULAR
    elif ldt_tag[2] == 'p':
        parse[NUMBER] = PLURAL
    else:
        print("Warning: unknown number:", ldt_tag[2])

    if ldt_tag[3] == '-':
        pass
    elif ldt_tag[3] == 'p':
        parse[TENSE] = PRESENT
    elif ldt_tag[3] == 'i':
        parse[TENSE] = IMPERFECT
    elif ldt_tag[3] == 'r':
        parse[TENSE] = PERFECT
    elif ldt_tag[3] == 'l':
        parse[TENSE] = PLUPERFECT
    elif ldt_tag[3] == 't':
        parse[TENSE] = FUTURE_PERFECT
    elif ldt_tag[3] == 'f':
        parse[TENSE] = FUTURE
    else:
        print("Warning: unknown tense:", ldt_tag[3])

    if ldt_tag[4] == '-':
        pass
    elif ldt_tag[4] == 'i':
        parse[MOOD] = INDICATIVE
    elif ldt_tag[4] == 's':
        parse[MOOD] = SUBJUNCTIVE
    elif ldt_tag[4] == 'n':
        parse[MOOD] = INFINITIVE
    elif ldt_tag[4] == 'm':
        parse[MOOD] = IMPERATIVE
    elif ldt_tag[4] == 'p':
        parse[MOOD] = PARTICIPLE
    elif ldt_tag[4] == 'd':
        parse[MOOD] = GERUND
    elif ldt_tag[4] == 'g':
        parse[MOOD] = GERUNDIVE
    elif ldt_tag[4] == 'u':
        parse[MOOD] = SUPINE
    else:
        print("Warning: unknown mood:", ldt_tag[4])

    if ldt_tag[5] == '-':
        pass
    elif ldt_tag[5] == 'a':
        parse[VOICE] = ACTIVE
    elif ldt_tag[5] == 'p':
        parse[VOICE] = PASSIVE
    else:
        print("Warning: unknown voice:", ldt_tag[5])

    if ldt_tag[6] == '-':
        pass
    elif ldt_tag[6] == 'm':
        parse[GENDER] = MASCULINE
    elif ldt_tag[6] == 'f':
        parse[GENDER] = FEMININE
    elif ldt_tag[6] == 'n':
        parse[GENDER] = NEUTER
    else:
        print("Warning: unknown gender:", ldt_tag[6])

    if ldt_tag[7] == '-':
        pass
    elif ldt_tag[7] == 'n':
        parse[CASE] = NOMINATIVE
    elif ldt_tag[7] == 'g':
        parse[CASE] = GENITIVE
    elif ldt_tag[7] == 'd':
        parse[CASE] = DATIVE
    elif ldt_tag[7] == 'a':
        parse[CASE] = ACCUSATIVE
    elif ldt_tag[7] == 'b':
        parse[CASE] = ABLATIVE
    elif ldt_tag[7] == 'v':
        parse[CASE] = VOCATIVE
    elif ldt_tag[7] == 'l':
        parse[CASE] = LOCATIVE
    else:
        print("Warning: unknown case:", ldt_tag[7])

    if ldt_tag[8] == '-':
        pass
    elif ldt_tag[8] == 'c':
        parse[DEGREE] = COMPARATIVE
    elif ldt_tag[8] == 's':
        parse[DEGREE] = SUPERLATIVE
    else:
        print("Warning: unknown degree:", ldt_tag[8])

    return parse


def parse_to_ldt(parse):
    ldt_tag = ""

    if parse.get(PART_OF_SPEECH, '') == NOUN:
        ldt_tag += 'n'
    elif parse.get(PART_OF_SPEECH, '') == VERB:
        ldt_tag += 'v'
    elif parse.get(PART_OF_SPEECH, '') == ADJECTIVE:
        ldt_tag += 'a'
    elif parse.get(PART_OF_SPEECH, '') == ADVERB or parse.get(PART_OF_SPEECH, '') == ADVERBIAL:
        ldt_tag += 'd'
    elif parse.get(PART_OF_SPEECH, '') == CONJUNCTION:
        ldt_tag += 'c'
    elif parse.get(PART_OF_SPEECH, '') == PREPOSITION:
        ldt_tag += 'r'
    elif parse.get(PART_OF_SPEECH, '') == PRONOUN:
        ldt_tag += 'p'
    elif parse.get(PART_OF_SPEECH, '') == NUMERAL:
        ldt_tag += 'm'
    elif parse.get(PART_OF_SPEECH, '') == INTERJECTION:
        ldt_tag += 'i'
    elif parse.get(PART_OF_SPEECH, '') == EXCLAMATION:
        ldt_tag += 'e'
    elif parse.get(PART_OF_SPEECH, '') == PUNCTUATION:
        ldt_tag += 'u'
    else:
        ldt_tag += '-'

    if parse.get(PERSON, '') == FIRST_PERSON:
        ldt_tag += '1'
    elif parse.get(PERSON, '') == SECOND_PERSON:
        ldt_tag += '2'
    elif parse.get(PERSON, '') == THIRD_PERSON:
        ldt_tag += '3'
    else:
        ldt_tag += '-'

    if parse.get(NUMBER, '') == SINGULAR:
        ldt_tag += 's'
    elif parse.get(NUMBER, '') == PLURAL:
        ldt_tag += 'p'
    else:
        ldt_tag += '-'

    if parse.get(TENSE, '') == PRESENT:
        ldt_tag += 'p'
    elif parse.get(TENSE, '') == IMPERFECT:
        ldt_tag += 'i'
    elif parse.get(TENSE, '') == PERFECT:
        ldt_tag += 'r'
    elif parse.get(TENSE, '') == PLUPERFECT:
        ldt_tag += 'l'
    elif parse.get(TENSE, '') == FUTURE_PERFECT:
        ldt_tag += 't'
    elif parse.get(TENSE, '') == FUTURE:
        ldt_tag += 'f'
    else:
        if parse.get(MOOD, '') == GERUNDIVE or parse.get(MOOD, '') == GERUND:
            ldt_tag += 'p'
        else:
            ldt_tag += '-'

    if parse.get(MOOD, '') == INDICATIVE:
        ldt_tag += 'i'
    elif parse.get(MOOD, '') == SUBJUNCTIVE:
        ldt_tag += 's'
    elif parse.get(MOOD, '') == INFINITIVE:
        ldt_tag += 'n'
    elif parse.get(MOOD, '') == IMPERATIVE:
        ldt_tag += 'm'
    elif parse.get(MOOD, '') == GERUNDIVE:
        ldt_tag += 'g'
    elif parse.get(MOOD, '') == SUPINE:
        ldt_tag += 'u'
    elif parse.get(MOOD, '') == GERUND:
        ldt_tag += 'd'
    elif parse.get(MOOD, '') == PARTICIPLE:
        ldt_tag += 'p'
    else:
        ldt_tag += '-'

    if parse.get(VOICE, '') == ACTIVE:
        ldt_tag += 'a'
    elif parse.get(VOICE, '') == PASSIVE:
        ldt_tag += 'p'
    else:
        if parse.get(TENSE, '') == PRESENT and parse.get(MOOD, '') == PARTICIPLE or parse.get(MOOD, '') == GERUND:
            ldt_tag += 'a'
        elif parse.get(TENSE, '') == PERFECT and parse.get(MOOD, '') == PARTICIPLE or parse.get(MOOD, '') == GERUNDIVE:
            ldt_tag += 'p'
        else:
            ldt_tag += '-'

    if parse.get(GENDER, '') == MASCULINE:
        ldt_tag += 'm'
    elif parse.get(GENDER, '') == FEMININE:
        ldt_tag += 'f'
    elif parse.get(GENDER, '') == NEUTER:
        ldt_tag += 'n'
    else:
        ldt_tag += '-'

    if parse.get(CASE, '') == NOMINATIVE:
        ldt_tag += 'n'
    elif parse.get(CASE, '') == GENITIVE:
        ldt_tag += 'g'
    elif parse.get(CASE, '') == DATIVE:
        ldt_tag += 'd'
    elif parse.get(CASE, '') == ACCUSATIVE:
        ldt_tag += 'a'
    elif parse.get(CASE, '') == ABLATIVE:
        ldt_tag += 'b'
    elif parse.get(CASE, '') == VOCATIVE:
        ldt_tag += 'v'
    elif parse.get(CASE, '') == LOCATIVE:
        ldt_tag += 'l'
    else:
        ldt_tag += '-'

    if parse.get(DEGREE, '') == POSITIVE:
        ldt_tag += '-'
    elif parse.get(DEGREE, '') == COMPARATIVE and parse.get(REGULARITY, '') != IRREGULAR and ldt_tag[0] != 'd':
        ldt_tag += 'c'
    elif parse.get(DEGREE, '') == SUPERLATIVE and parse.get(REGULARITY, '') != IRREGULAR and ldt_tag[0] != 'd':
        ldt_tag += 's'
    else:
        ldt_tag += '-'

    return ldt_tag


def unicodeaccents(txt):
    for source, replacement in [("a_", "ā"), ("e_", "ē"), ("i_", "ī"), ("o_", "ō"), ("u_", "ū"), ("y_", "ȳ"),
                                ("A_", "Ā"), ("E_", "Ē"), ("I_", "Ī"), ("O_", "Ō"), ("U_", "Ū"), ("Y_", "Ȳ"),
                                ("ä_", "ā"), ("ë_", "ē"), ("ï_", "ī"), ("ö_", "ō"), ("ü_", "ū"), ("ÿ_", "ȳ"),
                                ("æ_", "æ"), ("œ_", "œ"), ("Æ_", "Æ"), ("Œ_", "Œ")]:
        txt = txt.replace(source, replacement)
    return txt


def escape_macrons(txt):
    for source, replacement in [("ā", "a_"), ("ē", "e_"), ("ī", "i_"), ("ō", "o_"), ("ū", "u_"), ("ȳ", "y_"),
                                ("Ā", "A_"), ("Ē", "E_"), ("Ī", "I_"), ("Ō", "O_"), ("Ū", "U_"), ("Ȳ", "Y_")]:
        txt = txt.replace(source, replacement)
    return txt


def removemacrons(txt):
    for source, replacement in [("ā", "a"), ("ē", "e"), ("ī", "i"), ("ō", "o"), ("ū", "u"), ("ȳ", "y"),
                                ("Ā", "A"), ("Ē", "E"), ("Ī", "I"), ("Ō", "O"), ("Ū", "U"), ("Ȳ", "Y")]:
        txt = txt.replace(source, replacement)
    return txt


def filter_accents(accented):
    accented = accented.replace("^_", "_^")
    accented = re.sub(r"_\^([bcdfgpt][lr])", r"^\1", accented)
    accented = re.sub(r"u_m$", "um", accented)
    accented = re.sub(r"([AEIOUYaeiouy])\^?n([sfx]|ct)", r"\1_n\2", accented)
    return accented


def morpheus_to_parses(wordform, nl):
    """Based on CruncherToXML.java in Perseus Hopper"""
    parse = {}
    nl = nl.replace("irreg_comp", "irreg comp")
    nl = nl.replace("irreg_superl", "irreg superl")
    morph_codes = nl.split()

    accented = morph_codes[1]
    lemma = None
    if accented.count(",") == 0:
        lemma = accented
        if accented[0] == accented[0].upper():
            accented = wordform.capitalize()
        else:
            accented = wordform
    elif accented.count(",") == 1:
        lemma = accented.split(",")[1]
        accented = accented.split(",")[0]
    assert lemma is not None
    parse[LEMMA] = lemma
    parse[ACCENTEDFORM] = filter_accents(accented)

    last_morph_code = morph_codes[-1]
    pos_abbrev = morph_codes[0]

    if last_morph_code == "adverb":
        parse[PART_OF_SPEECH] = ADVERB
    elif last_morph_code == "article":
        parse[PART_OF_SPEECH] = ARTICLE
    elif last_morph_code == "particle":
        parse[PART_OF_SPEECH] = PARTICLE
    elif last_morph_code == "conj":
        parse[PART_OF_SPEECH] = CONJUNCTION
    elif last_morph_code == "prep":
        parse[PART_OF_SPEECH] = PREPOSITION
    elif last_morph_code in ["pron1", "pron2", "pron3", "relative", "demonstr", "indef", "interrog"]:
        parse[PART_OF_SPEECH] = PRONOUN
    elif last_morph_code == "numeral":
        parse[PART_OF_SPEECH] = NUMERAL
    elif last_morph_code == "exclam":
        parse[PART_OF_SPEECH] = EXCLAMATION
    elif last_morph_code == "alphabetic":
        parse[PART_OF_SPEECH] = IRREGULAR
    elif morph_codes[2] == "adverbial":
        parse[PART_OF_SPEECH] = ADVERBIAL
    elif pos_abbrev == "V":
        parse[PART_OF_SPEECH] = VERB
    elif pos_abbrev == "P":
        parse[PART_OF_SPEECH] = VERB
        parse[MOOD] = PARTICIPLE
    elif pos_abbrev == "N":
        if last_morph_code in ["us_a_um", "0_a_um", "er_ra_rum", "er_era_erum", "ius_ia_ium", "is_e", "er_ris_re",
                               "ans_adj", "ens_adj", "us_ius_adj", "0_ius_adj", "ior_ius_comp", "or_us_comp", "ax_adj",
                               "0_adj3", "peLs_pedis_adj", "ox_adj", "ix_adj", "s_tis_adj", "ex_icis_adj", "s_dis_adj",
                               "irreg_adj3", "irreg_adj1", "irreg_adj2", "pron_adj1", "pron_adj3"]:
            parse[PART_OF_SPEECH] = ADJECTIVE
        elif "pp4" in last_morph_code:
            if 'supine' in morph_codes:
                parse[PART_OF_SPEECH] = VERB
            else:
                parse[PART_OF_SPEECH] = ADJECTIVE
        else:
            parse[PART_OF_SPEECH] = NOUN
    else:
        print("Warning: Unknown Morpheus Part-of-Speech tag: " + pos_abbrev)

    def setfeature(parse, code, overwrite=False):
        featfound = False
        for feature, possiblevalues in featMap.items():
            if code in possiblevalues:
                if parse.get(feature) is None or overwrite:
                    parse[feature] = code
                    featfound = True
                elif parse.get(feature) == code:
                    featfound = True
                else:
                    print("Warning: Feature", feature, "already set! Old:", parse.get(feature), "New:", code)
        if not featfound:
            pass

    grouped_parses = [parse]
    for i in range(2, len(morph_codes)-1):
        code = morph_codes[i]
        if code.count('/') > 0:
            code_components = code.split('/')
            new_parses = []
            for existingParse in grouped_parses:
                for code_component in code_components:
                    dup_parse = existingParse.copy()
                    setfeature(dup_parse, code_component)
                    new_parses.append(dup_parse)
            grouped_parses = new_parses
        else:
            for group_parse in grouped_parses:
                setfeature(group_parse, code)

    final_parses = []
    for parse in grouped_parses:
        if parse.get(MOOD, '') == GERUNDIVE and parse.get(NUMBER, '') == SINGULAR \
                and parse.get(GENDER, '') == NEUTER and parse.get(CASE, '') != NOMINATIVE:
            new_parse = parse.copy()
            setfeature(new_parse, GERUND, overwrite=True)
            final_parses.append(new_parse)
        elif parse.get(GENDER, '') == '' and parse.get(CASE, '') != '':
            new_parse = parse.copy()
            setfeature(new_parse, MASCULINE)
            final_parses.append(new_parse)
            new_parse = parse.copy()
            setfeature(new_parse, FEMININE)
            final_parses.append(new_parse)
            setfeature(parse, NEUTER)
        final_parses.append(parse)
    return final_parses


def tag_distance(tag1, tag2):
    """Calculate distance measure between two LDT tags."""
    if not (len(tag1) == len(tag2) == 9 or len(tag1) == len(tag2) == 12):
        return 99

    def is_nomen(tag):
        if tag[0] in ('n', 'a') or (tag[0] == 'v' and tag[3:6] in ('rpp', 'ppa')):
            return True
        elif tag[0] in ('N', 'A') or (tag[0] == 'V' and tag[4:7] in ('rpp', 'ppa')):
            return True
        return False

    dist = 0
    bothnomenbutdifferent = is_nomen(tag1) and is_nomen(tag2) and tag1[0] != tag2[0]
    for i in range(0, len(tag1)):
        if bothnomenbutdifferent and ((len(tag1) == 9 and i in [3, 4, 5]) or (len(tag1) == 12 and i in [4, 5, 6])):
            continue
        if tag1[i] != tag2[i]:
            dist += 1
    return dist
```

latin_macronizer/scansion.py
```
import re

from .helpers import prefixeswithshortj


def allvowelsambiguous(accented):
    """Generate accented forms for unknown words"""
    accented = re.sub("([aeiouy])", "\\1_^", accented)
    accented = accented.replace("qu_^", "qu")
    accented = re.sub(r"_\^(ns|nf|nct)", "_\\1", accented)
    accented = re.sub(r"_\^([bcdfgjklmnpqrstv]{2,}|[xz])", "\\1", accented)
    accented = re.sub(r"_\^m$", "m", accented)
    return accented


def separate_ambiguous_vowels(accenteds):
    """
    If a vowel is ambiguous (_^), generate separate accented forms, one for each possible combination.
    Input: ['ba_^ce_^]
    Output: ['bace', 'ba_ce', 'bace_', 'ba_ce_']
    """
    accented_modifications = {'nescio_': 'nescio_^',
                              'u_ni_us': 'u_ni_^us',
                              'illi_us': 'illi_^us',
                              'ipsi_us': 'ipsi_^us',
                              'alteri_us': 'alteri_^us'}
    new_accenteds = []
    for accented in accenteds:
        accented = accented_modifications.get(accented, accented)
        parts = accented.split('_^')
        for variant in range(1 << len(parts) - 1):
            new_accented = []
            for bit_pos, part in enumerate(parts):
                new_accented.append(part)
                if 1 << bit_pos & variant:
                    new_accented.append('_')
            new_accenteds.append(''.join(new_accented))
    return new_accenteds


def segmentaccented(accented):
    """Split an accented form into a list of individual vowel phonemes and consonant clusters"""
    if accented == "hoc":  # Ad hoc fix. (Haha!)
        return ['o', 'cc']
    text = accented.lower().replace("qu", "q").replace("x", "cs").replace("z", "ds").replace("+", "^") + "#"
    segments = []
    segmentstart = 0
    pos = 0
    while True:
        if text[pos:pos + 2] in ["ae", "au", "ei", "eu", "oe"] and text[pos + 2] not in "_^+":
            pos += 2
        elif text[pos] in "aeiouy":
            pos += 1
            while text[pos] in "_^+":
                pos += 1
        else:
            while text[pos] not in "aeiouy#":
                pos += 1
        segment = text[segmentstart:pos].replace("h", "")
        if segment != "":
            segments.append(segment)
        if text[pos] == "#":
            break
        segmentstart = pos
    return segments


def possiblescans(accentedcandidates, followingsegment):
    """A form with marked vowel lengths can be scanned differently, considering
    muta cum liquida, diphthong vs. diaeresis, elision, etc.
    input: followingsegment is one of ["V", "C", "CC", "#"]
    returns: [(penalty, scansion, accented), ...]"""
    REPRIORITIZEPENALTY = 1
    MUTACUMLIQUIDAPENALTY = 1
    DIAERESISPENALTY = 2
    NOSYNEZISPENALTY = 2  # in the context s or ng + u + vowel
    SYNEZISPENALTY = 3
    HIATUSPENALTY = 3
    isfirstaccented = True
    scans = []
    for accented in separate_ambiguous_vowels(accentedcandidates):
        segments = segmentaccented(accented)
        segments.append(followingsegment)
        basepenalty = 0 if isfirstaccented else REPRIORITIZEPENALTY
        temps = [(basepenalty, "")]
        for i, thisseg in enumerate(segments):
            prevseg = "#" if i == 0 else segments[i - 1]
            nextseg = "#" if i == len(segments) - 1 else segments[i + 1]
            if i == 0 and not thisseg[0] in "aeiouy":
                continue
            news = []
            for (penaltysofar, scansofar) in temps:
                if "_" in thisseg:
                    news.append((penaltysofar, scansofar + "L"))
                elif thisseg in ["ae", "au", "ei", "oe", "eu"]:
                    news.append((penaltysofar, scansofar + "L"))
                    news.append((penaltysofar + DIAERESISPENALTY, scansofar + "VV"))
                elif (prevseg.endswith("s") or prevseg.endswith("ng")) and thisseg == "u" and nextseg[
                    0] in "aeiouy":
                    news.append((penaltysofar, scansofar + "C"))
                    news.append((penaltysofar + NOSYNEZISPENALTY, scansofar + "V"))
                elif thisseg[0] in "ui" and (nextseg[0] in "aeiouy" or prevseg[0] in "aeiouy"):
                    news.append((penaltysofar, scansofar + "V"))
                    news.append((penaltysofar + SYNEZISPENALTY, scansofar + "C"))
                elif thisseg[0] in "aeiouy":
                    news.append((penaltysofar, scansofar + "V"))
                elif thisseg == "m" and nextseg in ["V", "C", "CC", "#"]:
                    news.append((penaltysofar, scansofar + "M"))
                elif thisseg == "j" and prevseg != "#":
                    if accented.startswith(prefixeswithshortj):
                        news.append((penaltysofar, scansofar + "C"))
                    else:
                        news.append((penaltysofar, scansofar + "CC"))
                elif thisseg == "V":  # next word begins with vowel
                    if scansofar.endswith("V") or scansofar.endswith("L"):
                        news.append((penaltysofar, scansofar[:-1]))
                        news.append((penaltysofar + HIATUSPENALTY, scansofar))
                    elif scansofar.endswith("M"):
                        news.append((penaltysofar, scansofar[:-2]))
                        news.append((penaltysofar + HIATUSPENALTY, scansofar))
                    else:
                        news.append((penaltysofar, scansofar))
                elif thisseg == "#":
                    news.append((penaltysofar, scansofar))
                elif len(thisseg) == 1:
                    news.append((penaltysofar, scansofar + "C"))
                elif len(thisseg) == 2 and thisseg[0] in "tpcdbgf" and thisseg[1] in "rl":
                    news.append((penaltysofar, scansofar + "C"))
                    news.append((penaltysofar + MUTACUMLIQUIDAPENALTY, scansofar + "CC"))
                else:
                    news.append((penaltysofar, scansofar + "CC"))
            temps = news
        for (penalty, scansion) in temps:
            scansion = re.sub("VMC*|VCCC*|LM?C*", "L", scansion)
            scansion = re.sub("VC?", "S", scansion)
            scansion = re.sub("^C*", "", scansion)
            scans.append((penalty, scansion, accented))
        isfirstaccented = False
    filteredscans = []
    foundscansions = set()
    for (penalty, scansion, accented) in sorted(scans):
        if scansion not in foundscansions:
            filteredscans.append((penalty, scansion, accented))
            foundscansions.add(scansion)
    return filteredscans


def scanverse(verse, automaton):
    """Input: The "verse" is a complicated list of the format
    [(tokenindex, [(penalty, scansion, accented), (penalty, scansion, accented), ...]), ...]
    For example: [(0, [(0, 'L', 'in')]), (2, [(0, 'SL', 'no^va_'), (1, 'SS', 'no^va')]), ...]
    It returns a tuple such as ([(0, 'in'), (2, 'no^va'), (4, 'fe^rt'), ...], 'DDSSDS') """

    def scanverserecurse(verse, wordindex, automaton, oldnodeindex):
        if wordindex == len(verse):
            return [], [], 0
        (tokenindex, wordscansions) = verse[wordindex]
        besttail = []
        besttailfeet = []
        besttailpenalty = 100
        for (scanpenalty, scansion, accented) in wordscansions:
            nodeindex = oldnodeindex
            feet = []
            finished = False
            meterpenalty = 0
            for syllable in scansion:
                (nodeindex, foot, meterpenaltypart) = automaton.get((nodeindex, syllable), (-1, "", 0))
                meterpenalty += meterpenaltypart
                if nodeindex == 0:
                    finished = True
                feet.append(foot)
            if nodeindex == -1 or finished and (nodeindex != 0 or wordindex != len(verse) - 1):
                continue
            tail, tailfeet, tailpenalty = scanverserecurse(verse, wordindex + 1, automaton, nodeindex)
            if scanpenalty + meterpenalty + tailpenalty < besttailpenalty:
                besttail = [(tokenindex, accented)] + tail
                besttailfeet = feet + tailfeet
                besttailpenalty = scanpenalty + meterpenalty + tailpenalty
        return besttail, besttailfeet, besttailpenalty

    # enddef
    indexaccentedpairs, feet, penalty = scanverserecurse(verse, 0, automaton, 0)
    return indexaccentedpairs, "".join(feet)


def scanverses(tokens, meterautomatons):
    """Try to scan the text according to meterautomatons. This function will, for each token,
    reconsider the order of the accented forms given by the getaccents function, by finding
    a likely combination of accented forms that make the verses scan."""

    scannedfeet = []
    verse = []
    automatonindex = 0
    for (index, token) in enumerate(tokens):
        if token.isword:
            followingtext = ""
            nextindex = index
            while True:
                nextindex += 1
                if nextindex == len(tokens) or "\n" in tokens[nextindex].text:
                    break
                if tokens[nextindex].isspace:
                    followingtext += " "
                elif tokens[nextindex].isword:
                    followingtext += tokens[nextindex].accented[0]
                    if "aeiouy" in followingtext:
                        break
            followingtext = followingtext.lower().replace("h", "")
            if followingtext == "":
                followingsegment = "#"
            elif re.match(" *[aeiouy]", followingtext):
                followingsegment = "V"
            elif re.match(" *([bcdfgjklmnpqrstv] *|[tpcdbgf][lr])[aeiouy]", followingtext):
                followingsegment = "C"
            else:
                followingsegment = "CC"
            if token.isunknown:
                token.accented.append(allvowelsambiguous(token.text.lower()))
            verse.append((index, possiblescans(token.accented, followingsegment)))
        if "\n" in token.text or index == len(tokens) - 1:
            (accentcorrections, feet) = scanverse(verse, meterautomatons[automatonindex])
            scannedfeet.append(feet)
            scannedfeet += [""] * (token.text.count("\n") - 1)
            for (tokenindex, newaccented) in accentcorrections:
                try:
                    tokens[tokenindex].accented.remove(newaccented)
                except ValueError:
                    pass
                tokens[tokenindex].accented.insert(0, newaccented)
            verse = []
            automatonindex += 1
            if automatonindex == len(meterautomatons):
                automatonindex = 0
```

latin_macronizer/wordlist.py
```
from collections import defaultdict
import sqlite3
from tempfile import mkstemp
import os

from . import postags

MACRONS_FILE = os.path.join(os.path.dirname(__file__), 'macrons.txt')
MORPHEUS_DIR = os.path.join(os.path.dirname(__file__), 'morpheus')


def pairwise(iterable):
    """s -> (s0,s1), (s2,s3), (s4, s5), ..."""
    a = iter(iterable)
    return zip(a, a)


def clean_lemma(lemma):
    return lemma.replace("#", "").replace("1", "").replace(" ", "+").replace("-", "").replace("^", "").replace("_", "")


class Wordlist:
    def __init__(self, db_path):
        self.unknownwords = set()  # Unknown to Morpheus
        self.formtolemmas = defaultdict(list)
        self.formtoaccenteds = defaultdict(list)
        self.formtotaglemmaaccents = defaultdict(list)
        if db_path:
            self.dbconn = sqlite3.connect(db_path)
            self.dbcursor = self.dbconn.cursor()
            self.dbcursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='morpheus';")
            if not self.dbcursor.fetchone():
                print("Initializing database...")
                self.reinitializedatabase()
        else:
            self.dbconn = None
            self.loadwordsfromfile(MACRONS_FILE)
    # enddef

    def reinitializedatabase(self):
        self.dbcursor.execute("DROP TABLE IF EXISTS morpheus")
        self.dbcursor.execute('''
            CREATE TABLE morpheus(
                id INTEGER PRIMARY KEY, 
                wordform TEXT NOT NULL, 
                morphtag TEXT, 
                lemma TEXT, 
                accented TEXT, 
                UNIQUE(wordform, morphtag, lemma, accented)
            )
        ''')
        self.loadwordsfromfile(MACRONS_FILE, storeindb=True)
        self.dbcursor.execute("CREATE INDEX morpheus_wordform_index ON morpheus (wordform)")
        self.dbconn.commit()
    # enddef

    def loadwordsfromfile(self, filename, storeindb=False):
        with open(filename, 'r', encoding='utf-8') as plaindbfile:
            for line in plaindbfile:
                if line.startswith("#"):
                    continue
                [wordform, morphtag, lemma, accented] = line.split()
                self.addwordparse(wordform, morphtag, lemma, accented)
                if self.dbconn and storeindb:
                    self.dbcursor.execute(
                        "INSERT OR IGNORE INTO morpheus (wordform, morphtag, lemma, accented) VALUES (?, ?, ?, ?)",
                        (wordform, morphtag, lemma, accented))
    # enddef

    def loadwords(self, words):  # Expects a set of lowercase words
        unseenwords = set()
        for word in words:
            if word in self.formtotaglemmaaccents:  # Word is already loaded
                continue
            if not self.loadwordfromdb(word):  # Could not find word in database
                unseenwords.add(word)
        if len(unseenwords) > 0:
            self.crunchwords(unseenwords)  # Try to parse unseen words with Morpheus, and add result to the database
            for word in unseenwords:
                if not self.loadwordfromdb(word):
                    raise Exception("Could not store %s in the database." % word)
    # enddef

    def loadwordfromdb(self, word):
        if self.dbconn:
            try:
                self.dbcursor.execute(
                    "SELECT wordform, morphtag, lemma, accented FROM morpheus WHERE wordform = ?", (word,))
            except Exception:
                raise Exception("Database table is missing. Please reset the database using --initialize.")
            rows = self.dbcursor.fetchall()
            if len(rows) == 0:
                return False
            for [wordform, morphtag, lemma, accented] in rows:
                self.addwordparse(wordform, morphtag, lemma, accented)
        else:
            self.addwordparse(word, None, None, None)
        return True
    # enddef

    def addwordparse(self, wordform, morphtag, lemma, accented):
        if accented is None:
            if wordform not in {"que", "ne", "ve", "st"}:
                self.unknownwords.add(wordform)
        else:
            accented = accented.replace('_^', '').replace('^', '')
            self.formtolemmas[wordform].append(lemma)
            self.formtoaccenteds[wordform].append(accented.lower())
            self.formtotaglemmaaccents[wordform].append((morphtag, lemma, accented))

    def crunchwords(self, words):
        morphinpfd, morphinpfname = mkstemp()
        os.close(morphinpfd)
        crunchedfd, crunchedfname = mkstemp()
        os.close(crunchedfd)
        with open(morphinpfname, 'w', encoding='utf-8') as morphinpfile:
            for word in words:
                morphinpfile.write(word.strip().lower() + '\n')
                morphinpfile.write(word.strip().capitalize() + '\n')
        morpheus_command = "MORPHLIB=%s/stemlib %s/bin/cruncher -L < %s > %s 2> /dev/null" % \
                               (MORPHEUS_DIR, MORPHEUS_DIR, morphinpfname, crunchedfname)
        exitcode = os.system(morpheus_command)
        if exitcode != 0:
            raise Exception("Failed to execute: %s" % morpheus_command)
        os.remove(morphinpfname)
        with open(crunchedfname, 'r', encoding='utf-8') as crunchedfile:
            morpheus = crunchedfile.read()
        os.remove(crunchedfname)
        crunchedwordforms = {}
        knownwords = set()
        for wordform, nls in pairwise(morpheus.split("\n")):
            wordform = wordform.strip().lower()
            nls = nls.strip()
            crunchedwordforms[wordform] = crunchedwordforms.get(wordform, "") + nls
        for wordform, nls in crunchedwordforms.items():
            parses = []
            for nl in nls.split("<NL>"):
                nl = nl.replace("</NL>", "")
                nlparts = nl.split()
                if len(nlparts) > 0:
                    parses += postags.morpheus_to_parses(wordform, nl)
            lemmatagtoaccenteds = defaultdict(list)
            for parse in parses:
                lemma = clean_lemma(parse[postags.LEMMA])
                parse[postags.LEMMA] = lemma
                accented = parse[postags.ACCENTEDFORM]
                # Work around shortcoming in Morpheus, adding _ in tradu_co_, etc.:
                if parse[postags.LEMMA].startswith("trans") and accented[3] != "_":
                    accented = accented[:3] + "_" + accented[3:]
                parse[postags.ACCENTEDFORM] = accented
                tag = postags.parse_to_ldt(parse)
                lemmatagtoaccenteds[(lemma, tag)].append(accented)
            if len(lemmatagtoaccenteds) == 0:
                continue
            knownwords.add(wordform)
            for (lemma, tag), accenteds in lemmatagtoaccenteds.items():
                # Sometimes there are multiple accented forms; prefer 'volvit' to 'voluit', 'Ju_lius' to 'Iu_lius' etc.:
                bestaccented = sorted(accenteds, key=lambda x: x.count('v') + x.count('j') + x.count('J'))[-1]
                lemmatagtoaccenteds[(lemma, tag)] = bestaccented
            for (lemma, tag), accented in lemmatagtoaccenteds.items():
                self.dbcursor.execute("INSERT OR IGNORE INTO morpheus (wordform, morphtag, lemma, accented) VALUES (?, ?, ?, ?)",
                                      (wordform, tag, lemma, accented))
        # The remaining were unknown to Morpheus:
        for wordform in words - knownwords:
            self.dbcursor.execute("INSERT OR IGNORE INTO morpheus (wordform) VALUES (?)", (wordform,))

        self.dbconn.commit()
    # enddef
# endclass
```

scripts/gemini.py
```
import argparse
import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
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

    async def _process_file(self, raw_file: Path) -> None:
        rel_path = str(raw_file.relative_to(self.config.raw_dir))
        out_file = self.config.macronized_dir / rel_path
        out_file.parent.mkdir(parents=True, exist_ok=True)

        is_priority = self._is_priority_file(raw_file)

        last_chunk = self.state.file_progress.get(rel_path, -1)
        if last_chunk == -1 and not out_file.exists():
            out_file.write_text("", encoding="utf-8")

        raw_text = raw_file.read_text(encoding="utf-8")
        file_bytes = raw_file.stat().st_size
        chunk_idx = 0

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for chunk_text in self.generate_chunks(raw_text):
            current_idx = chunk_idx
            chunk_idx += 1

            if current_idx <= last_chunk:
                continue

            if is_priority:
                self.session_stats.priority_files_worked_on[rel_path] = f"In Progress (Chunk {current_idx + 1})"

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
                f"[{rel_path}] Chunk {current_idx + 1}: Resolved {stats.resolved_slots}/{stats.total_slots} slots."
            )

        self.state.completed_files.append(rel_path)
        self.checkpoint_manager.save(self.state)
        self.session_stats.files_processed_today += 1

        if is_priority:
            self.session_stats.priority_files_worked_on[rel_path] = "Completed"

        logger.info(f"Successfully finished file: {rel_path}")

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
                await self._process_file(raw_file)
            logger.info("Corpus processing complete! All files processed.")
        except DailyQuotaExhaustedException as e:
            logger.info(f"Stopping execution for today: {e}")
        finally:
            self.checkpoint_manager.save(self.state)
            self._print_run_summary(all_raw_files)


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
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    config = PipelineConfig(
        priority_file=args.priority_file,
        priority_inputs_dir=args.priority_inputs,
    )
    pipeline = MacronCorpusPipeline(config=config)
    asyncio.run(pipeline.run())
```

.github/workflows/macronize_corpus.yml
```
name: Daily Corpus Macronization

on:
  schedule:
    # Runs daily at 09:00 UTC
    - cron: '0 9 * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  process-corpus:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout runner repository
        uses: actions/checkout@v4

      - name: Checkout output repository
        uses: actions/checkout@v4
        with:
          repository: 'njand/lat_text_latin_library_macronized'
          token: ${{ secrets.OUTPUT_REPO_TOKEN }}
          path: 'output_repo'

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies from pyproject.toml
        run: |
          python -m pip install --upgrade pip
          pip install .

      - name: Run Macronization Pipeline
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          python scripts/gemini.py

      - name: Commit & Push Progress Checkpoints (Runner Repo)
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "Update macronization state checkpoint"
          file_pattern: "data/"

      - name: Commit & Push Processed Texts (Output Repo)
        run: |
          cd output_repo
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add .
          git status
          git diff-index --quiet HEAD || (git commit -m "Automated daily corpus update" && git push)
          
```

</source_code>
</current_codebase>
