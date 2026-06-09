import asyncio
import discord
import requests
from datetime import datetime
import os
import json
import sqlite3

# ---------- Configuration ----------
DB_FILE = "database.sqlite"

# Discord
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_NAMES = os.environ.get("DISCORD_CHANNEL_NAMES", "KToxguards Tests")

# ---------- Fonction de détection ----------
def simple_detect(text: str, lang: str = "en"):
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

# ---------- Stockage en base ----------
def save_message(text, platform, author, timestamp, lang="en"):
    conn = sqlite3.connect(DB_FILE)
    result = simple_detect(text, lang)
    conn.execute(
        "INSERT INTO messages (text, platform, author, timestamp, label, confidence, keywords_found, threat_types, recommendations, lang) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (text, platform, author, timestamp, result["label"], result["confidence"],
         json.dumps(result["keywords_found"]), json.dumps(result["threat_types"]), json.dumps(result["recommendations"]), lang)
    )
    conn.commit()
    conn.close()

# ---------- Collecte Discord (par NOM de salon) ----------
class DiscordClient(discord.Client):
    async def on_ready(self):
        print(f"Bot Discord connecté en tant que {self.user}")
        channel_names = [name.strip() for name in DISCORD_CHANNEL_NAMES.split(",") if name.strip()]
        for guild in self.guilds:
            for channel_name in channel_names:
                channel = discord.utils.get(guild.text_channels, name=channel_name)
                if channel:
                    print(f"Lecture du salon #{channel.name} sur le serveur {guild.name}")
                    async for message in channel.history(limit=100):
                        if message.content:
                            save_message(message.content, "discord", str(message.author), message.created_at, "en")
                else:
                    print(f"Salon '{channel_name}' non trouvé sur le serveur {guild.name}")
        await self.close()

def collect_discord():
    if not DISCORD_BOT_TOKEN or not DISCORD_CHANNEL_NAMES:
        print("Discord non configuré (token ou noms de salons manquants)")
        return 0
    client = DiscordClient(intents=discord.Intents.default())
    client.intents.message_content = True
    client.run(DISCORD_BOT_TOKEN)
    return 1

# ---------- Collecte Reddit ----------
KEYWORDS = [
    # Groupes
    "bts", "bangtan", "seventeen", "txt", "newjeans",
    "방탄소년단", "세븐틴", "투모로우바이투게더", "뉴진스",
    # BTS
    "jimin", "jungkook", "v", "suga", "rm", "jin", "jhope",
    # SEVENTEEN (13 membres)
    "scoups", "s.coups", "에스쿱스",
    "jeonghan", "정한",
    "joshua", "조슈아",
    "jun", "준",
    "hoshi", "호시",
    "wonwoo", "원우",
    "woozi", "우지",
    "dk", "도겸", "dokyeom",
    "mingyu", "민규",
    "the8", "디에잇", "minghao",
    "seungkwan", "승관",
    "vernon", "버논",
    "dino", "디노",
    # TXT
    "soobin", "yeonjun", "beomgyu", "taehyun", "hueningkai",
    # NewJeans
    "minji", "hanni", "danielle", "haerin", "hyein"
]

def collect_reddit():
    url = "https://www.reddit.com/r/kpop/comments.json?limit=100"
    headers = {"User-Agent": "KToxGuard/1.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return 0
        data = resp.json()
        count = 0
        for child in data.get("data", {}).get("children", []):
            cd = child.get("data", {})
            body = cd.get("body", "")
            if any(kw in body.lower() for kw in KEYWORDS):
                save_message(body, "reddit", cd.get("author", "unknown"), datetime.fromtimestamp(cd.get("created_utc", 0)), "en")
                count += 1
        return count
    except Exception as e:
        print(f"Erreur Reddit: {e}")
        return 0

# ---------- Point d'entrée unique ----------
def collect_all():
    total = 0
    total += collect_reddit()
    total += collect_discord()
    return total
