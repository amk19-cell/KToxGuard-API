import json
import re
from pathlib import Path

# Charger le lexique
LEXICON_PATH = Path(__file__).parent / "lexicon.json"
with open(LEXICON_PATH, "r", encoding="utf-8") as f:
    lexicon = json.load(f)

# Dictionnaire des fichiers de recommandations par langue
RECO_FILES = {
    "en": "recommendations_en.json",
    "ko": "recommendations_ko.json",
    "fr": "recommendations_fr.json"
}

# Par défaut, charger l'anglais
DEFAULT_LANG = "en"
RECO_PATH = Path(__file__).parent / RECO_FILES[DEFAULT_LANG]
with open(RECO_PATH, "r", encoding="utf-8") as f:
    recommendations = json.load(f)

# Tous les mots toxiques
toxic_words = []
for category, words in lexicon.items():
    if isinstance(words, dict):
        toxic_words.extend(words.keys())

# Patterns de menaces
threat_patterns = [
    (r"학교 앞에서\s*보자", "death_threat", 0.85),
    (r"죽여버린다", "death_threat", 0.95),
    (r"재기해", "death_threat", 0.95),
    (r"신상\s*털", "doxxing", 0.9),
    (r"왕따", "school_bullying", 0.8),
    (r"학폭", "school_bullying", 0.85),
    (r"강간", "sexual_harassment", 0.95),
]

def detect_toxicity(text: str, lang: str = "en"):
    global recommendations
    if lang in RECO_FILES:
        reco_path = Path(__file__).parent / RECO_FILES[lang]
        with open(reco_path, "r", encoding="utf-8") as f:
            recommendations = json.load(f)
    
    found_keywords = [w for w in toxic_words if w in text]
    keyword_score = 0.8 if found_keywords else 0.0
    
    threat_types = []
    context_score = 0.0
    for pat, ttype, conf in threat_patterns:
        if re.search(pat, text):
            threat_types.append(ttype)
            context_score = max(context_score, conf)
    
    final_score = max(keyword_score, context_score)
    label = "toxique" if final_score >= 0.7 else "neutre"
    
    reco = {}
    if label == "toxique":
        for t in threat_types:
            if t in recommendations:
                reco[t] = recommendations[t]
        if not reco:
            reco["default"] = recommendations.get("default", {})
    
    return {
        "label": label,
        "confidence": final_score,
        "keywords_found": found_keywords,
        "threat_types": list(set(threat_types)),
        "recommendations": reco
    }
