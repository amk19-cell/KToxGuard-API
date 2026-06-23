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
import re
from pathlib import Path

# ---------- BASE DE DONNÉES ----------
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if "?sslmode=" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?sslmode=")[0]
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
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

# ---------- LEXIQUE CORÉEN ----------
def load_korean_lexicon():
    path = Path(__file__).parent / "lexicon.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

KOREAN_LEXICON = load_korean_lexicon()
HIGH_SEVERITY_CATEGORIES = {"death_threats", "threat_veiled", "threats_general", "family_paedrip"}
MEDIUM_SEVERITY_CATEGORIES = {"misogyny", "misandry", "body_shaming", "appearance_bullying",
                                "dehumanization", "racial_xenophobic", "homophobic", "school_bullying",
                                "cyber_harassment", "ostracism"}
EXCLUDED_FROM_SCAN = {"full_comment_examples", "sources"}

# ---------- LEXIQUE ANGLAIS ----------
ENGLISH_LEXICON = {
    "slang_offensive": {
        "idiot": "idiot", "stupid": "stupide", "moron": "débile", "loser": "loser",
        "trash": "déchet", "garbage": "ordure", "pathetic": "pathétique", "worthless": "sans valeur",
        "fuck you": "fuck you", "asshole": "connard", "bitch": "salope", "whore": "pute",
        "scum": "vermine", "disgusting": "dégoûtant", "ugly": "moche", "freak": "monstre"
    },
    "death_threats": {
        "kill yourself": "suicide-toi", "kys": "suicide-toi (abr.)", "go die": "va mourir",
        "i'll kill you": "je vais te tuer", "you should die": "tu devrais mourir",
        "end yourself": "finis-en", "hope you die": "j'espère que tu meurs"
    },
    "body_shaming": {
        "fatass": "gros cul", "obese": "obèse", "lose weight": "perds du poids",
        "too fat to": "trop gros pour", "too big to": "trop gros pour",
        "shouldn't show": "ne devrait pas montrer", "shouldn't be on": "ne devrait pas être sur"
    },
    "cyber_harassment": {
        "i know where you live": "je sais où tu vis", "i'll find you": "je vais te trouver",
        "doxx": "doxxing", "leak her info": "diffuser ses infos", "send her address": "envoyer son adresse"
    },
    "misogyny_en": {
        "women shouldn't": "les femmes ne devraient pas", "know your place": "reste à ta place"
    },
    "racial_xenophobic": {
        "go back to your country": "retourne dans ton pays"
    }
}

CONTEXTUAL_PATTERNS = [
    (r"(too|so)\s+(fat|big)\s+(to|for)", "body_shaming_structural", 0.75),
    (r"(shouldn'?t)\s+(show|post|be on)", "appearance_judgment", 0.7),
    (r"(no one|nobody)\s+(wants to see)", "appearance_rejection", 0.65),
    (r"(shouldn'?t exist|doesn'?t deserve to)", "dehumanization_structural", 0.8),
    (r"(go back to)\s+(your country)", "xenophobic_structural", 0.75),
]

def detect_contextual_patterns(text: str):
    text_lower = text.lower()
    matches = []
    max_score = 0.0
    for pattern, ptype, weight in CONTEXTUAL_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            matches.append(ptype)
            max_score = max(max_score, weight)
    return matches, max_score

def detect_toxicity(text: str, lang: str = "en"):
    if not text:
        return {"label": "neutre", "confidence": 0.0, "keywords_found": [], "threat_types": [], "recommendations": {}}

    text_lower = text.lower()
    keywords_found = []
    threat_types = set()
    severity_score = 0.0

    for category, terms in KOREAN_LEXICON.items():
        if category in EXCLUDED_FROM_SCAN or not isinstance(terms, dict):
            continue
        for kr_term in terms.keys():
            if kr_term in text:
                keywords_found.append(kr_term)
                threat_types.add(category)
                if category in HIGH_SEVERITY_CATEGORIES:
                    severity_score = max(severity_score, 0.95)
                elif category in MEDIUM_SEVERITY_CATEGORIES:
                    severity_score = max(severity_score, 0.8)
                else:
                    severity_score = max(severity_score, 0.6)

    for category, terms in ENGLISH_LEXICON.items():
        for en_term in terms.keys():
            if en_term in text_lower:
                keywords_found.append(en_term)
                threat_types.add(category)
                if category == "death_threats":
                    severity_score = max(severity_score, 0.95)
                elif category in ("body_shaming", "cyber_harassment", "misogyny_en", "racial_xenophobic"):
                    severity_score = max(severity_score, 0.8)
                else:
                    severity_score = max(severity_score, 0.6)

    pattern_matches, pattern_score = detect_contextual_patterns(text)
    if pattern_matches:
        threat_types.update(pattern_matches)
        severity_score = max(severity_score, pattern_score)

    label = "toxique" if severity_score >= 0.6 else "neutre"

    recommendations = {}
    if label == "toxique":
        if "death_threats" in threat_types:
            recommendations["action"] = "export_evidence_contact_police"
        elif "body_shaming" in threat_types or "body_shaming_structural" in threat_types:
            recommendations["action"] = "body_shaming_support"
        elif "cyber_harassment" in threat_types or "ostracism" in threat_types:
            recommendations["action"] = "report_and_document"
        else:
            recommendations["action"] = "monitor"

    return {
        "label": label,
        "confidence": round(severity_score, 2),
        "keywords_found": keywords_found,
        "threat_types": list(threat_types),
        "recommendations": recommendations
    }

# ---------- COLLECTEUR ----------
from app.collectors import collect_all_sources

last_collect_time = datetime.now() - timedelta(hours=1)

async def save_message(db: AsyncSession, comment: dict, now: datetime):
    """Sauvegarde un seul message avec son propre commit, isolé des autres."""
    try:
        result = detect_toxicity(comment["text"], "en")
        db_msg = Message(
            text=comment["text"][:2000],
            platform=comment.get("platform", "unknown"),
            author=comment.get("author", "unknown"),
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
        return True
    except Exception as e:
        print(f"[Collect] Erreur sauvegarde: {e}")
        await db.rollback()
        return False

async def trigger_collect(db: AsyncSession):
    global last_collect_time
    now = datetime.now()
    try:
        comments = await collect_all_sources(last_collect_time)
    except Exception as e:
        print(f"[Collect] Erreur collecte sources: {e}")
        comments = []

    saved = 0
    for comment in comments:
        if not comment.get("text"):
            continue
        success = await save_message(db, comment, now)
        if success:
            saved += 1

    last_collect_time = now
    print(f"[Collect] {saved}/{len(comments)} messages sauvegardés")
    return saved

# ---------- ENDPOINTS ----------
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
    result = detect_toxicity(msg.text, msg.lang)
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
        result = detect_toxicity(msg.text, msg.lang)
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
    try:
        total_result = await db.execute(select(func.count(Message.id)))
        total = total_result.scalar() or 0
        if total == 0:
            return {"total_messages": 0, "toxic_count": 0, "toxic_percentage": 0.0, "by_threat_type": {}, "top_keywords": {}}
        toxic_result = await db.execute(select(func.count()).where(Message.label == "toxique"))
        toxic_count = toxic_result.scalar() or 0
        toxic_percentage = round((toxic_count / total) * 100, 2)
        threat_result = await db.execute(select(Message.threat_types))
        threat_counts = {}
        for row in threat_result:
            if row[0]:
                for t in json.loads(row[0]):
                    threat_counts[t] = threat_counts.get(t, 0) + 1
        kw_result = await db.execute(select(Message.keywords_found))
        kw_counts = {}
        for row in kw_result:
            if row[0]:
                for kw in json.loads(row[0]):
                    kw_counts[kw] = kw_counts.get(kw, 0) + 1
        top_keywords = dict(sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)[:5])
        return {
            "total_messages": total,
            "toxic_count": toxic_count,
            "toxic_percentage": toxic_percentage,
            "by_threat_type": threat_counts,
            "top_keywords": top_keywords
        }
    except Exception as e:
        print(f"[Stats] Erreur: {e}")
        return {"total_messages": 0, "toxic_count": 0, "toxic_percentage": 0.0, "by_threat_type": {}, "top_keywords": {}}

@app.get("/messages")
async def get_messages(limit: int = 50, skip: int = 0, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message).order_by(Message.timestamp.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()

@app.get("/artists")
async def get_artists():
    path = Path(__file__).parent / "artists.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
