from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

app = FastAPI(title="KToxGuard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MessageIn(BaseModel):
    text: str
    platform: Optional[str] = None
    author: Optional[str] = None
    ip_address: Optional[str] = None
    lang: Optional[str] = "en"

# Stockage en mémoire (perdu à chaque redémarrage)
messages_db = []

def simple_detect(text: str, lang: str):
    toxic_words = ["바보", "병신", "시발", "죽어", "쓰레기", "stupid", "kill", "hate", "fuck"]
    score = 0.8 if any(w in text.lower() for w in toxic_words) else 0.0
    label = "toxique" if score >= 0.7 else "neutre"
    return {
        "label": label,
        "confidence": score,
        "keywords_found": [],
        "threat_types": [],
        "recommendations": {}
    }

@app.get("/")
def root():
    return {"message": "KToxGuard API is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/analyze")
async def analyze(msg: MessageIn):
    result = simple_detect(msg.text, msg.lang)
    msg_dict = msg.dict()
    msg_dict["timestamp"] = datetime.now().isoformat()
    msg_dict.update(result)
    messages_db.append(msg_dict)
    return result

@app.post("/import")
async def import_messages(messages: List[MessageIn]):
    imported = 0
    for msg in messages:
        result = simple_detect(msg.text, msg.lang)
        msg_dict = msg.dict()
        msg_dict["timestamp"] = datetime.now().isoformat()
        msg_dict.update(result)
        messages_db.append(msg_dict)
        imported += 1
    return {"imported": imported, "received": len(messages)}

@app.get("/collect")
async def collect_get():
    # Pour le test, on renvoie juste un message factice
    return {"status": "ok", "collected": 0}

@app.get("/stats")
async def get_stats():
    total = len(messages_db)
    toxic_count = sum(1 for m in messages_db if m.get("label") == "toxique")
    toxic_percentage = round((toxic_count / total) * 100, 2) if total else 0
    return {
        "total_messages": total,
        "toxic_count": toxic_count,
        "toxic_percentage": toxic_percentage,
        "by_threat_type": {},
        "top_keywords": {}
    }

@app.get("/messages")
async def get_messages(limit: int = 50, skip: int = 0):
    return messages_db[skip:skip+limit]

@app.get("/artists")
async def get_artists():
    return []  # Pas d'artistes pour l'instant
