import aiohttp
from datetime import datetime
import os
import re
from googleapiclient.discovery import build
import asyncio

# ---------- CONFIGURATION ----------
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "AIzaSyBrPBb3u__WQicvkokTco77roF_xJ9_czY")
YOUTUBE_SEARCH_QUERIES = os.environ.get("YOUTUBE_SEARCH_QUERIES", "kpop,bts,blackpink,ive,nmixx,katseye,newjeans,seventeen,txt")
YOUTUBE_MAX_VIDEOS_PER_QUERY = int(os.environ.get("YOUTUBE_MAX_VIDEOS", "30"))
YOUTUBE_MAX_COMMENTS_PER_VIDEO = int(os.environ.get("YOUTUBE_MAX_COMMENTS", "30"))

# Mots-clés pour filtrer les discussions K-pop (pour Reddit)
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

# ---------- YOUTUBE (avec recherche) ----------
def search_youtube_videos(query, max_results):
    """Recherche des vidéos YouTube récentes pour une requête donnée."""
    if not YOUTUBE_API_KEY:
        return []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.search().list(
            part="id",
            q=query,
            type="video",
            order="date",
            maxResults=max_results,
            relevanceLanguage="en"
        )
        response = request.execute()
        video_ids = [item["id"]["videoId"] for item in response.get("items", [])]
        return video_ids
    except Exception as e:
        print(f"[YouTube Search] Erreur pour '{query}': {e}")
        return []

def fetch_youtube_comments_sync(video_id):
    """Récupère les commentaires d'une vidéo YouTube (bloquant)."""
    if not YOUTUBE_API_KEY:
        return []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=YOUTUBE_MAX_COMMENTS_PER_VIDEO,
            textFormat="plainText"
        )
        response = request.execute()
        comments = []
        for item in response.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            text = snippet.get("textDisplay", "")
            author = snippet.get("authorDisplayName", "unknown")
            published_at = snippet.get("publishedAt", "")
            try:
                timestamp = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            except:
                timestamp = datetime.now()
            comments.append({
                "text": text,
                "platform": "youtube",
                "author": author,
                "timestamp": timestamp
            })
        return comments
    except Exception as e:
        print(f"[YouTube Comments] Erreur sur {video_id}: {e}")
        return []

async def fetch_youtube_comments(since_time):
    """Recherche des vidéos et récupère les commentaires récents."""
    if not YOUTUBE_API_KEY:
        return []
    
    queries = [q.strip() for q in YOUTUBE_SEARCH_QUERIES.split(",") if q.strip()]
    all_comments = []
    loop = asyncio.get_event_loop()
    
    for query in queries:
        video_ids = await loop.run_in_executor(None, search_youtube_videos, query, YOUTUBE_MAX_VIDEOS_PER_QUERY)
        for vid in video_ids:
            comments = await loop.run_in_executor(None, fetch_youtube_comments_sync, vid)
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
    youtube_comments = await fetch_youtube_comments(since_time)
    all_comments.extend(youtube_comments)
    
    return all_comments
