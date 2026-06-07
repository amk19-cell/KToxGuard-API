from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import sqlite3
import json
import os

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

# ---------- Base de données SQLite ----------
DB_FILE = "database.sqlite"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            platform TEXT,
            author TEXT,
            ip_address TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            label TEXT,
            confidence REAL,
            keywords_found TEXT,
            threat_types TEXT,
            recommendations TEXT,
            lang TEXT DEFAULT 'en'
        )
    ''')
    conn.commit()
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
    conn = get_db()
    conn.execute(
        "INSERT INTO messages (text, platform, author, ip_address, label, confidence, keywords_found, threat_types, recommendations, lang) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (msg.text, msg.platform, msg.author, msg.ip_address, result["label"], result["confidence"],
         json.dumps(result["keywords_found"]), json.dumps(result["threat_types"]), json.dumps(result["recommendations"]), msg.lang)
    )
    conn.commit()
    conn.close()
    return result

@app.post("/import")
def import_messages(messages: List[MessageIn]):
    imported = 0
    for msg in messages:
        result = simple_detect(msg.text, msg.lang)
        conn = get_db()
        conn.execute(
            "INSERT INTO messages (text, platform, author, ip_address, label, confidence, keywords_found, threat_types, recommendations, lang) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (msg.text, msg.platform, msg.author, msg.ip_address, result["label"], result["confidence"],
             json.dumps(result["keywords_found"]), json.dumps(result["threat_types"]), json.dumps(result["recommendations"]), msg.lang)
        )
        conn.commit()
        conn.close()
        imported += 1
    return {"imported": imported, "received": len(messages)}

@app.get("/stats")
def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    toxic = conn.execute("SELECT COUNT(*) FROM messages WHERE label = 'toxique'").fetchone()[0]
    conn.close()
    percent = round((toxic / total) * 100, 2) if total else 0
    return {
        "total_messages": total,
        "toxic_count": toxic,
        "toxic_percentage": percent,
        "by_threat_type": {},
        "top_keywords": {}
    }

@app.get("/messages")
def get_messages(limit: int = 50, skip: int = 0):
    conn = get_db()
    rows = conn.execute("SELECT * FROM messages ORDER BY timestamp DESC LIMIT ? OFFSET ?", (limit, skip)).fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.api_route("/collect", methods=["GET", "POST"])
def collect():
    # Placeholder pour la collecte Reddit (à implémenter plus tard)
    return {"status": "ok", "collected": 0}

@app.get("/artists")
def get_artists():
    return [
        {"id": 1, "name": "BTS", "members": 7, "photo": "https://cdn.britannica.com/77/213477-050-32E30A3D/BTS-South-Korean-boy-band-June-6-2019.jpg"},
        {"id": 2, "name": "SEVENTEEN", "members": 13, "photo": "https://cdn.britannica.com/39/236339-050-2C6CE9A7/K-pop-boy-band-Seventeen-2022.jpg"},
        {"id": 3, "name": "TXT", "members": 5, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/TXT_logo.svg/200px-TXT_logo.svg.png"},
        {"id": 4, "name": "NewJeans", "members": 5, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2b/NewJeans_logo.svg/200px-NewJeans_logo.svg.png"}
    ]
