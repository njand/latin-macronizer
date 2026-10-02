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