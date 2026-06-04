import json
import re
from pathlib import Path

LEXICON_PATH = Path(__file__).parent / "lexicon.json"
with open(LEXICON_PATH, "r", encoding="utf-8") as f:
    lexicon = json.load(f)

RECO_FILES = {
    "en": "recommendations_en.json",
    "ko": "recommendations_ko.json",
    "fr": "recommendations_fr.json"
}

_recommendations_cache = {}

def _load_recommendations(lang):
    if lang not in _recommendations_cache:
        file_path = Path(__file__).parent / RECO_FILES.get(lang, "recommendations_en.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                _recommendations_cache[lang] = json.load(f)
        except FileNotFoundError:
            _recommendations_cache[lang] = {}
    return _recommendations_cache[lang]

toxic_words = []
for category, words in lexicon.items():
    if isinstance(words, dict):
        toxic_words.extend(words.keys())

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
    recommendations = _load_recommendations(lang)
    
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
        if not reco and "default" in recommendations:
            reco["default"] = recommendations["default"]
    
    return {
        "label": label,
        "confidence": final_score,
        "keywords_found": found_keywords,
        "threat_types": list(set(threat_types)),
        "recommendations": reco
    }
