import json
import re
from pathlib import Path

with open(Path(__file__).parent / "lexicon.json", "r", encoding="utf-8") as f:
    lexicon = json.load(f)
with open(Path(__file__).parent / "konglish_lexicon.json", "r", encoding="utf-8") as f:
    konglish = json.load(f)
with open(Path(__file__).parent / "recommendations.json", "r", encoding="utf-8") as f:
    recommendations = json.load(f)

toxic_words = []
for cat in lexicon.values():
    if isinstance(cat, dict):
        toxic_words.extend(cat.keys())
toxic_words.extend(konglish.keys())

threat_patterns = [
    (r"학교 앞에서\s*보자", "death_threat", 0.85),
    (r"죽여버린다", "death_threat", 0.95),
    (r"재기해", "death_threat", 0.95),
    (r"신상\s*털", "doxxing", 0.9),
    (r"왕따", "school_bullying", 0.8),
    (r"학폭", "school_bullying", 0.85),
]

def detect_toxicity(text):
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
    recos = {t: recommendations[t] for t in set(threat_types) if t in recommendations}
    return {
        "label": label,
        "confidence": final_score,
        "keywords_found": found_keywords,
        "threat_types": list(set(threat_types)),
        "recommendations": recos
    }
