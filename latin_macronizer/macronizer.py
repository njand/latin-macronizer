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