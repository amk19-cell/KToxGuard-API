from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from datetime import datetime, timedelta
import os
import json
from pathlib import Path

# ========== BASE DE DONNÉES ==========
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    text: Mapped[str]
    platform: Mapped[Optional[str]]
    author: Mapped[Optional[str]]
    ip_address: Mapped[Optional[str]]
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    label: Mapped[str]
    confidence: Mapped[float]
    keywords_found: Mapped[Optional[str]]
    threat_types: Mapped[Optional[str]]
    recommendations: Mapped[Optional[str]]
    lang: Mapped[str] = mapped_column(default="en")

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# ========== APPLICATION ==========
app = FastAPI(title="KToxGuard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== MODÈLES ==========
class MessageIn(BaseModel):
    text: str
    platform: Optional[str] = None
    author: Optional[str] = None
    ip_address: Optional[str] = None
    lang: Optional[str] = "en"

# ========== DÉTECTION ==========
def simple_detect(text: str, lang: str = "en"):
    toxic_words = ["바보", "병신", "시발", "죽어", "쓰레기", "stupid", "kill", "hate", "fuck", "idiot", "die", "trash"]
    score = 0.8 if any(w in text.lower() for w in toxic_words) else 0.0
    label = "toxique" if score >= 0.7 else "neutre"
    return {
        "label": label,
        "confidence": score,
        "keywords_found": [],
        "threat_types": [],
        "recommendations": {}
    }

# ========== REDDIT (SANS COLLECTE EXTERNE COMPLEXE) ==========
async def fetch_reddit_comments(subreddit: str, since_time: datetime):
    import aiohttp
    url = f"https://www.reddit.com/r/{subreddit}/comments.json?limit=30"
    headers = {"User-Agent": "KToxGuard/1.0"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status != 200:
                    return []
                data = await response.json()
                comments = []
                for child in data.get("data", {}).get("children", []):
                    cd = child.get("data", {})
                    created = datetime.fromtimestamp(cd.get("created_utc", 0))
                    if created > since_time:
                        text = cd.get("body", "")
                        comments.append({
                            "text": text,
                            "platform": "reddit",
                            "author": cd.get("author", "unknown"),
                            "timestamp": created
                        })
                return comments
        except Exception as e:
            print(f"[Reddit] Erreur: {e}")
            return []

# ========== COLLECTE ==========
last_collect_time = datetime.now() - timedelta(hours=1)

async def trigger_collect(db: AsyncSession):
    global last_collect_time
    now = datetime.now()
    comments = await fetch_reddit_comments("kpop", last_collect_time)
    for comment in comments:
        result = simple_detect(comment["text"], "en")
        db_msg = Message(
            text=comment["text"],
            platform=comment["platform"],
            author=comment["author"],
            timestamp=comment.get("timestamp", now),
            label=result["label"],
            confidence=result["confidence"],
            keywords_found=json.dumps(result["keywords_found"]),
            threat_types=json.dumps(result["threat_types"]),
            recommendations=json.dumps(result["recommendations"]),
            lang="en"
        )
        db.add(db_msg)
    await db.commit()
    last_collect_time = now
    return len(comments)

# ========== ENDPOINTS ==========
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
def root():
    return {"message": "KToxGuard API is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/analyze")
async def analyze(msg: MessageIn, db: AsyncSession = Depends(get_db)):
    result = simple_detect(msg.text, msg.lang)
    db_msg = Message(
        text=msg.text,
        platform=msg.platform,
        author=msg.author,
        ip_address=msg.ip_address,
        label=result["label"],
        confidence=result["confidence"],
        keywords_found=json.dumps(result["keywords_found"]),
        threat_types=json.dumps(result["threat_types"]),
        recommendations=json.dumps(result["recommendations"]),
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
        db_msg = Message(
            text=msg.text,
            platform=msg.platform,
            author=msg.author,
            ip_address=msg.ip_address,
            label=result["label"],
            confidence=result["confidence"],
            keywords_found=json.dumps(result["keywords_found"]),
            threat_types=json.dumps(result["threat_types"]),
            recommendations=json.dumps(result["recommendations"]),
            lang=msg.lang
        )
        db.add(db_msg)
        imported += 1
    await db.commit()
    return {"imported": imported, "received": len(messages)}

@app.get("/collect")
async def collect_get(db: AsyncSession = Depends(get_db)):
    count = await trigger_collect(db)
    return {"status": "ok", "collected": count}

@app.post("/collect")
async def collect_post(db: AsyncSession = Depends(get_db)):
    count = await trigger_collect(db)
    return {"status": "ok", "collected": count}

@app.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_result = await db.execute(select(func.count(Message.id)))
    total = total_result.scalar() or 0
    if total == 0:
        return {
            "total_messages": 0,
            "toxic_count": 0,
            "toxic_percentage": 0.0,
            "by_threat_type": {},
            "top_keywords": {}
        }
    toxic_result = await db.execute(select(func.count()).where(Message.label == "toxique"))
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
        select(Message)
        .order_by(Message.timestamp.desc())
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
