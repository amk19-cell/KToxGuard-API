
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json
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

# ---------- Connexion base de données ----------
DATABASE_URL = os.environ.get("DATABASE_URL", "")
# Nettoyer l'URL : enlever ?sslmode=...
if "?sslmode=" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?sslmode=")[0]
# Convertir postgresql:// en postgresql:// (sync)
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    pass  # bon format
else:
    # Fallback pour les tests
    DATABASE_URL = "postgresql://postgres:password@localhost:5432/ktoxguard"

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            text TEXT NOT NULL,
            platform TEXT,
            author TEXT,
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            label TEXT,
            confidence FLOAT,
            keywords_found TEXT,
            threat_types TEXT,
            recommendations TEXT,
            lang TEXT DEFAULT 'en'
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ---------- Détection simple ----------
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
@app.get("/")
def root():
    return {"message": "KToxGuard API is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/analyze")
def analyze(msg: MessageIn):
    result = simple_detect(msg.text, msg.lang)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO messages (text, platform, author, ip_address, label, confidence, keywords_found, threat_types, recommendations, lang)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (msg.text, msg.platform, msg.author, msg.ip_address, result["label"], result["confidence"],
          json.dumps(result["keywords_found"]), json.dumps(result["threat_types"]), json.dumps(result["recommendations"]), msg.lang))
    conn.commit()
    cur.close()
    conn.close()
    return result

@app.post("/import")
def import_messages(messages: List[MessageIn]):
    imported = 0
    for msg in messages:
        result = simple_detect(msg.text, msg.lang)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO messages (text, platform, author, ip_address, label, confidence, keywords_found, threat_types, recommendations, lang)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (msg.text, msg.platform, msg.author, msg.ip_address, result["label"], result["confidence"],
              json.dumps(result["keywords_found"]), json.dumps(result["threat_types"]), json.dumps(result["recommendations"]), msg.lang))
        conn.commit()
        cur.close()
        conn.close()
        imported += 1
    return {"imported": imported, "received": len(messages)}

@app.get("/stats")
def get_stats():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as total FROM messages")
    total = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as toxic FROM messages WHERE label = 'toxique'")
    toxic = cur.fetchone()["toxic"]
    toxic_percentage = round((toxic / total) * 100, 2) if total else 0
    cur.close()
    conn.close()
    return {
        "total_messages": total,
        "toxic_count": toxic,
        "toxic_percentage": toxic_percentage,
        "by_threat_type": {},
        "top_keywords": {}
    }

@app.get("/messages")
def get_messages(limit: int = 50, skip: int = 0):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM messages ORDER BY timestamp DESC LIMIT %s OFFSET %s", (limit, skip))
    messages = cur.fetchall()
    cur.close()
    conn.close()
    return messages

@app.api_route("/collect", methods=["GET", "POST"])
def collect():
    # Pour l'instant, on ne collecte rien, juste pour la compatibilité cron
    return {"status": "ok", "collected": 0}

@app.get("/artists")
def get_artists():
    return [
        {"id": 1, "name": "BTS", "members": 7, "photo": "https://cdn.britannica.com/77/213477-050-32E30A3D/BTS-South-Korean-boy-band-June-6-2019.jpg"},
        {"id": 2, "name": "SEVENTEEN", "members": 13, "photo": "https://cdn.britannica.com/39/236339-050-2C6CE9A7/K-pop-boy-band-Seventeen-2022.jpg"},
        {"id": 3, "name": "TXT", "members": 5, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/TXT_logo.svg/200px-TXT_logo.svg.png"},
        {"id": 4, "name": "NewJeans", "members": 5, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2b/NewJeans_logo.svg/200px-NewJeans_logo.svg.png"}
    ]
