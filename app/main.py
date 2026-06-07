from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from app.database import engine, get_db
from app import models
from app.collectors import fetch_reddit_comments
import json
from pathlib import Path
import re

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

last_collect_time = datetime.now() - timedelta(hours=1)

@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

@app.get("/")
def root():
    return {"message": "KToxGuard API is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

# Fonction de détection simplifiée (sans dépendances externes)
def simple_detect(text: str, lang: str):
    # Mots-clés toxiques basiques (pour l'import, évite les fichiers manquants)
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

@app.post("/analyze")
async def analyze(msg: MessageIn, db: AsyncSession = Depends(get_db)):
    result = simple_detect(msg.text, msg.lang)
    db_msg = models.Message(
        text=msg.text,
        platform=msg.platform,
        author=msg.author,
        ip_address=msg.ip_address,
        label=result["label"],
        confidence=result["confidence"],
        keywords_found=result["keywords_found"],
        threat_types=result["threat_types"],
        recommendations=result["recommendations"],
        lang=msg.lang
    )
    db.add(db_msg)
    await db.commit()
    return result

@app.post("/import")
async def import_messages(messages: List[MessageIn], db: AsyncSession = Depends(get_db)):
    imported = 0
    for msg in messages:
        result = simple_detect(msg.text, msg.lang)
        db_msg = models.Message(
            text=msg.text,
            platform=msg.platform,
            author=msg.author,
            ip_address=msg.ip_address,
            label=result["label"],
            confidence=result["confidence"],
            keywords_found=result["keywords_found"],
            threat_types=result["threat_types"],
            recommendations=result["recommendations"],
            lang=msg.lang
        )
        db.add(db_msg)
        imported += 1
    await db.commit()
    return {"imported": imported, "received": len(messages)}

@app.get("/collect")
async def collect_get(db: AsyncSession = Depends(get_db)):
    return await trigger_collect(db)

@app.post("/collect")
async def collect_post(db: AsyncSession = Depends(get_db)):
    return await trigger_collect(db)

async def trigger_collect(db: AsyncSession):
    global last_collect_time
    now = datetime.now()
    comments = await fetch_reddit_comments("kpop", last_collect_time)
    for comment in comments:
        result = simple_detect(comment["text"], "en")
        db_msg = models.Message(
            text=comment["text"],
            platform=comment["platform"],
            author=comment["author"],
            label=result["label"],
            confidence=result["confidence"],
            keywords_found=result["keywords_found"],
            threat_types=result["threat_types"],
            recommendations=result["recommendations"],
            lang="en"
        )
        db.add(db_msg)
    await db.commit()
    last_collect_time = now
    return {"status": "ok", "collected": len(comments)}

@app.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_result = await db.execute(select(func.count(models.Message.id)))
    total = total_result.scalar() or 0
    if total == 0:
        return {
            "total_messages": 0,
            "toxic_count": 0,
            "toxic_percentage": 0.0,
            "by_threat_type": {},
            "top_keywords": {}
        }
    toxic_result = await db.execute(select(func.count()).where(models.Message.label == "toxique"))
    toxic_count = toxic_result.scalar() or 0
    toxic_percentage = round((toxic_count / total) * 100, 2)
    return {
        "total_messages": total,
        "toxic_count": toxic_count,
        "toxic_percentage": toxic_percentage,
        "by_threat_type": {},
        "top_keywords": {}
    }

@app.get("/messages")
async def get_messages(limit: int = 50, skip: int = 0, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Message)
        .order_by(models.Message.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    messages = result.scalars().all()
    return messages

@app.get("/artists")
async def get_artists():
    path = Path(__file__).parent / "artists.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        artists = json.load(f)
    return artists
