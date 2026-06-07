from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from app.detector import detect_toxicity
from app.database import engine, get_db
from app import models
from app.collectors import fetch_reddit_comments
import json
from pathlib import Path

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

@app.post("/analyze")
async def analyze(msg: MessageIn, db: AsyncSession = Depends(get_db)):
    result = detect_toxicity(msg.text, msg.lang)
    db_msg = models.Message(
        text=msg.text,
        platform=msg.platform,
        author=msg.author,
        ip_address=msg.ip_address,
        label=result["label"],
        confidence=result["confidence"],
        keywords_found=result["keywords_found"],
        threat_types=result["threat_types"],
        recommendations=result.get("recommendations", {}),
        lang=msg.lang
    )
    db.add(db_msg)
    await db.commit()
    return result

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
        result = detect_toxicity(comment["text"], "en")
        db_msg = models.Message(
            text=comment["text"],
            platform=comment["platform"],
            author=comment["author"],
            label=result["label"],
            confidence=result["confidence"],
            keywords_found=result["keywords_found"],
            threat_types=result["threat_types"],
            recommendations=result.get("recommendations", {}),
            lang="en"
        )
        db.add(db_msg)
    await db.commit()
    last_collect_time = now
    return {"status": "ok", "collected": len(comments)}

@app.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    try:
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
        threat_result = await db.execute(select(models.Message.threat_types))
        threat_counts = {}
        for row in threat_result:
            if row[0]:
                for t in row[0]:
                    threat_counts[t] = threat_counts.get(t, 0) + 1
        kw_result = await db.execute(select(models.Message.keywords_found))
        kw_counts = {}
        for row in kw_result:
            if row[0]:
                for kw in row[0]:
                    kw_counts[kw] = kw_counts.get(kw, 0) + 1
        top_keywords = dict(sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)[:5])
        return {
            "total_messages": total,
            "toxic_count": toxic_count,
            "toxic_percentage": toxic_percentage,
            "by_threat_type": threat_counts,
            "top_keywords": top_keywords
        }
    except Exception:
        return {
            "total_messages": 0,
            "toxic_count": 0,
            "toxic_percentage": 0.0,
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
