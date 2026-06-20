import aiohttp
from datetime import datetime
import os
import re
from googleapiclient.discovery import build
import asyncio

# ---------- CONFIGURATION ----------
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_VIDEO_IDS = os.environ.get("YOUTUBE_VIDEO_IDS", "dQw4w9WgXcQ").split(",")

# Mots-clés pour filtrer les discussions K-pop
KEYWORDS = [
    "bts", "bangtan", "seventeen", "txt", "newjeans", "blackpink", "ive", "nmixx", "katseye",
    "kpop", "k-pop", "idol", "fan", "comeback", "concert", "music", "song",
    "방탄소년단", "세븐틴", "투모로우바이투게더", "뉴진스", "블랙핑크", "아이브", "엔믹스"
]

# ---------- REDDIT ----------
async def fetch_reddit_comments(subreddit, since_time):
    """Récupère les commentaires Reddit depuis since_time."""
    url = f"https://www.reddit.com/r/{subreddit}/comments.json?limit=50"
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
                        if any(kw in text for kw in KEYWORDS):
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

# ---------- KOREABOO ----------
async def fetch_koreaboo_articles(limit=5):
    """Scrape les articles récents de Koreaboo."""
    url = "https://www.koreaboo.com"
    headers = {"User-Agent": "KToxGuard/1.0"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status != 200:
                    return []
                html = await response.text()
                article_links = re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', html)
                articles = []
                for link, title in article_links[:limit]:
                    if "/news/" in link or "/article/" in link:
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

# ---------- YOUTUBE ----------
def fetch_youtube_comments_sync(video_id):
    """Récupère les commentaires YouTube (bloquant, à exécuter dans un thread)."""
    if not YOUTUBE_API_KEY:
        return []
    
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=50,
            textFormat="plainText"
        )
        response = request.execute()
        
        comments = []
        for item in response.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            text = snippet.get("textDisplay", "")
            author = snippet.get("authorDisplayName", "unknown")
            published_at = snippet.get("publishedAt", "")
            # Convertir la date ISO en datetime
            try:
                timestamp = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            except:
                timestamp = datetime.now()
            
            # Filtrer par mots-clés
            if any(kw in text.lower() for kw in KEYWORDS):
                comments.append({
                    "text": text,
                    "platform": "youtube",
                    "author": author,
                    "timestamp": timestamp
                })
        return comments
    except Exception as e:
        print(f"[YouTube] Erreur sur {video_id}: {e}")
        return []

async def fetch_youtube_comments(video_ids, since_time):
    """Récupère les commentaires YouTube depuis since_time."""
    if not YOUTUBE_API_KEY or not video_ids:
        return []
    
    all_comments = []
    loop = asyncio.get_event_loop()
    
    for video_id in video_ids:
        comments = await loop.run_in_executor(None, fetch_youtube_comments_sync, video_id)
        # Filtrer par date
        filtered = [c for c in comments if c["timestamp"] > since_time]
        all_comments.extend(filtered)
    
    return all_comments

# ---------- COLLECTEUR GLOBAL ----------
async def collect_all_sources(since_time):
    """Récupère toutes les sources (Reddit + Koreaboo + YouTube)."""
    all_comments = []
    
    # Reddit
    reddit_comments = await fetch_reddit_comments("kpop", since_time)
    all_comments.extend(reddit_comments)
    
    # Koreaboo
    koreaboo_articles = await fetch_koreaboo_articles(limit=5)
    all_comments.extend(koreaboo_articles)
    
    # YouTube
    youtube_comments = await fetch_youtube_comments(YOUTUBE_VIDEO_IDS, since_time)
    all_comments.extend(youtube_comments)
    
    return all_comments
