from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from datetime import datetime, timedelta
import os
import json
from app.collectors import fetch_reddit_comments

# ---------- Database ----------
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

# ---------- FastAPI ----------
app = FastAPI(title="KToxGuard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Pydantic models ----------
class MessageIn(BaseModel):
    text: str
    platform: Optional[str] = None
    author: Optional[str] = None
    ip_address: Optional[str] = None
    lang: Optional[str] = "en"

# ---------- Simple detection ----------
def simple_detect(text: str, lang: str):
    toxic_words = ["바보", "병신", "시발", "죽어", "쓰레기", "stupid", "kill", "hate", "fuck", "idiot", "die"]
    score = 0.8 if any(w in text.lower() for w in toxic_words) else 0.0
    label = "toxique" if score >= 0.7 else "neutre"
    return {
        "label": label,
        "confidence": score,
        "keywords_found": [],
        "threat_types": [],
        "recommendations": {}
    }

# ---------- Endpoints ----------
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

# Collecte périodique
last_collect_time = datetime.now() - timedelta(hours=1)

@app.api_route("/collect", methods=["GET", "POST"])
async def collect_endpoint(db: AsyncSession = Depends(get_db)):
    global last_collect_time
    now = datetime.now()
    comments = await fetch_reddit_comments("kpop", last_collect_time)
    count = 0
    for comment in comments:
        result = simple_detect(comment["text"], "en")
        db_msg = Message(
            text=comment["text"],
            platform=comment["platform"],
            author=comment["author"],
            label=result["label"],
            confidence=result["confidence"],
            keywords_found=json.dumps(result["keywords_found"]),
            threat_types=json.dumps(result["threat_types"]),
            recommendations=json.dumps(result["recommendations"]),
            lang="en"
        )
        db.add(db_msg)
        count += 1
    await db.commit()
    last_collect_time = now
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
    return [
        {"id": 1, "name": "BTS", "members": 7, "photo": "https://cdn.britannica.com/77/213477-050-32E30A3D/BTS-South-Korean-boy-band-June-6-2019.jpg"},
        {"id": 2, "name": "SEVENTEEN", "members": 13, "photo": "https://cdn.britannica.com/39/236339-050-2C6CE9A7/K-pop-boy-band-Seventeen-2022.jpg"},
        {"id": 3, "name": "TXT", "members": 5, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/TXT_logo.svg/200px-TXT_logo.svg.png"},
        {"id": 4, "name": "NewJeans", "members": 5, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2b/NewJeans_logo.svg/200px-NewJeans_logo.svg.png"}
    ]
