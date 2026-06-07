from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import sqlite3
import json
import os
import requests
from googleapiclient.discovery import build

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

# ---------- Détection ----------
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

# ---------- Collecte YouTube ----------
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY) if YOUTUBE_API_KEY else None

def fetch_youtube_comments(video_id):
    """Récupère les commentaires d'une vidéo YouTube (max 100)."""
    if not youtube:
        return []
    try:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=100,
            textFormat="plainText"
        )
        response = request.execute()
        comments = []
        for item in response.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            text = snippet.get("textDisplay", "")
            author = snippet.get("authorDisplayName", "unknown")
            # On ne filtre pas par langue (beaucoup de commentaires k-pop sont en anglais/coréen)
            comments.append({
                "text": text,
                "platform": "youtube",
                "author": author,
                "timestamp": datetime.fromtimestamp(int(snippet.get("publishedAt", "1970-01-01T00:00:00Z").replace("Z", "").replace("T", " ")[:19])),
                "lang": "en"  # on peut améliorer plus tard
            })
        return comments
    except Exception as e:
        print(f"Erreur YouTube: {e}")
        return []

# ---------- Collecte Reddit ----------
KEYWORDS = [
    "bts", "bangtan", "seventeen", "txt", "newjeans",
    "방탄소년단", "세븐틴", "투모로우바이투게더", "뉴진스",
    "jimin", "jungkook", "v", "suga", "rm", "jin", "jhope",
    "vernon", "mingyu", "wonwoo", "woozi", "dk", "hoshi",
    "soobin", "yeonjun", "beomgyu", "taehyun", "hueningkai",
    "minji", "hanni", "danielle", "haerin", "hyein"
]

def fetch_reddit_comments():
    url = "https://www.reddit.com/r/kpop/comments.json?limit=100"
    headers = {"User-Agent": "KToxGuard/1.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        comments = []
        for child in data.get("data", {}).get("children", []):
            cd = child.get("data", {})
            body = cd.get("body", "")
            if any(kw in body.lower() for kw in KEYWORDS):
                comments.append({
                    "text": body,
                    "platform": "reddit",
                    "author": cd.get("author", "unknown"),
                    "timestamp": datetime.fromtimestamp(cd.get("created_utc", 0)),
                    "lang": "en"
                })
        return comments
    except Exception as e:
        print(f"Erreur Reddit: {e}")
        return []

# ---------- Gestion du dernier timestamp de collecte ----------
LAST_COLLECT_FILE = "last_collect.txt"

def get_last_collect_time():
    if os.path.exists(LAST_COLLECT_FILE):
        with open(LAST_COLLECT_FILE, "r") as f:
            try:
                return datetime.fromisoformat(f.read().strip())
            except:
                return datetime.now() - timedelta(hours=1)
    return datetime.now() - timedelta(hours=1)

def save_last_collect_time(dt):
    with open(LAST_COLLECT_FILE, "w") as f:
        f.write(dt.isoformat())

def collect_new_comments():
    last = get_last_collect_time()
    now = datetime.now()
    all_comments = []
    # Reddit
    all_comments.extend(fetch_reddit_comments())
    # YouTube (sur quelques vidéos populaires)
    if youtube:
        # Liste de vidéos k-pop populaires (vous pouvez changer)
        video_ids = ["d3w2rHl4P8E", "GDJilJ0n1fE", "kXpZkL5vM2M", "9S0x5eJm6qE"]  # exemples
        for vid in video_ids:
            all_comments.extend(fetch_youtube_comments(vid))
    # Filtrer les commentaires plus récents que `last`
    new_comments = [c for c in all_comments if c["timestamp"] > last]
    if not new_comments:
        return 0
    conn = get_db()
    for c in new_comments:
        result = simple_detect(c["text"], c["lang"])
        conn.execute(
            "INSERT INTO messages (text, platform, author, timestamp, label, confidence, keywords_found, threat_types, recommendations, lang) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (c["text"], c["platform"], c["author"], c["timestamp"], result["label"], result["confidence"],
             json.dumps(result["keywords_found"]), json.dumps(result["threat_types"]), json.dumps(result["recommendations"]), c["lang"])
        )
    conn.commit()
    conn.close()
    save_last_collect_time(now)
    return len(new_comments)

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
    count = collect_new_comments()
    return {"status": "ok", "collected": count}

@app.get("/artists")
def get_artists():
    return [
        {"id": 1, "name": "BTS", "members": 7, "photo": "https://cdn.britannica.com/77/213477-050-32E30A3D/BTS-South-Korean-boy-band-June-6-2019.jpg"},
        {"id": 2, "name": "SEVENTEEN", "members": 13, "photo": "https://cdn.britannica.com/39/236339-050-2C6CE9A7/K-pop-boy-band-Seventeen-2022.jpg"},
        {"id": 3, "name": "TXT", "members": 5, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/TXT_logo.svg/200px-TXT_logo.svg.png"},
        {"id": 4, "name": "NewJeans", "members": 5, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2b/NewJeans_logo.svg/200px-NewJeans_logo.svg.png"}
        ]
