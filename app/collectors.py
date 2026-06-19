import aiohttp
from datetime import datetime
from typing import List, Dict
import re
import json
from pathlib import Path

# ========== ARTISTES ET MOTS-CLÉS ==========
ARTIST_FILE = Path(__file__).parent / "artists.json"
ARTIST_KEYWORDS = []
if ARTIST_FILE.exists():
    with open(ARTIST_FILE, "r", encoding="utf-8") as f:
        artists = json.load(f)
        for artist in artists:
            ARTIST_KEYWORDS.extend(artist.get("keywords", []))
else:
    # Fallback si le fichier n'existe pas
    ARTIST_KEYWORDS = ["bts", "blackpink", "ive", "nmixx", "katseye"]

# ========== REDDIT (sans filtre de langue) ==========
async def fetch_reddit_comments(subreddit: str, since_time: datetime) -> List[Dict]:
    """Récupère les commentaires Reddit depuis since_time, sans filtre de langue."""
    url = f"https://www.reddit.com/r/{subreddit}/comments.json?limit=30"
    headers = {"User-Agent": "KToxGuard/1.0 (social listening bot)"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status != 200:
                    return []
                data = await response.json()
                comments = []
                for child in data.get("data", {}).get("children", []):
                    comment_data = child.get("data", {})
                    created_utc = datetime.fromtimestamp(comment_data.get("created_utc", 0))
                    if created_utc > since_time:
                        text = comment_data.get("body", "").lower()
                        # Filtre par mots-clés (toutes langues)
                        if any(kw in text for kw in ARTIST_KEYWORDS):
                            comments.append({
                                "text": comment_data.get("body", ""),
                                "platform": "reddit",
                                "author": comment_data.get("author", "unknown"),
                                "timestamp": created_utc
                            })
                return comments
        except Exception as e:
            print(f"[Reddit] Erreur: {e}")
            return []

# ========== KOREABOO (scraping) ==========
async def fetch_koreaboo_articles(limit: int = 10) -> List[Dict]:
    """Scrape les articles récents de Koreaboo et leurs commentaires (simulé)."""
    url = "https://www.koreaboo.com"
    headers = {"User-Agent": "KToxGuard/1.0 (social listening bot)"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status != 200:
                    return []
                html = await response.text()
                # Extraction basique des articles (les liens, titres, etc.)
                # Note : ceci est une version simplifiée, à améliorer avec BeautifulSoup si besoin
                article_pattern = r'<a href="([^"]+)"[^>]*>([^<]+)</a>'
                matches = re.findall(article_pattern, html)
                articles = []
                for link, title in matches[:limit]:
                    if "news" in link or "article" in link:
                        articles.append({
                            "text": f"[Koreaboo] {title.strip()} - {link}",
                            "platform": "koreaboo",
                            "author": "koreaboo",
                            "timestamp": datetime.now()
                        })
                return articles
        except Exception as e:
            print(f"[Koreaboo] Erreur: {e}")
            return []

# ========== TELEGRAM (préparation) ==========
# Pour activer Telegram, décommentez les lignes suivantes et ajoutez vos identifiants.
# Vous devez aussi installer telethon : pip install telethon
#
# from telethon import TelegramClient
#
# TELEGRAM_API_ID = os.environ.get("TELEGRAM_API_ID")
# TELEGRAM_API_HASH = os.environ.get("TELEGRAM_API_HASH")
# TELEGRAM_CHANNELS = os.environ.get("TELEGRAM_CHANNELS", "").split(",")
#
# async def fetch_telegram_messages(since_time: datetime) -> List[Dict]:
#     if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
#         return []
#     client = TelegramClient('ktoxguard_session', int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
#     await client.start()
#     messages = []
#     for channel in TELEGRAM_CHANNELS:
#         try:
#             entity = await client.get_entity(channel.strip())
#             async for msg in client.iter_messages(entity, offset_date=since_time):
#                 if msg.text and any(kw in msg.text.lower() for kw in ARTIST_KEYWORDS):
#                     messages.append({
#                         "text": msg.text,
#                         "platform": "telegram",
#                         "author": str(msg.sender_id),
#                         "timestamp": msg.date
#                     })
#         except Exception as e:
#             print(f"[Telegram] Erreur sur {channel}: {e}")
#     await client.disconnect()
#     return messages

# ========== COLLECTEUR GLOBAL ==========
async def collect_all_sources(since_time: datetime) -> List[Dict]:
    """Récupère les commentaires depuis Reddit, Koreaboo, et (optionnel) Telegram."""
    all_comments = []
    # Reddit
    reddit_comments = await fetch_reddit_comments("kpop", since_time)
    all_comments.extend(reddit_comments)
    # Koreaboo
    koreaboo_articles = await fetch_koreaboo_articles(limit=5)
    all_comments.extend(koreaboo_articles)
    # Telegram (si activé)
    # telegram_messages = await fetch_telegram_messages(since_time)
    # all_comments.extend(telegram_messages)
    return all_comments
