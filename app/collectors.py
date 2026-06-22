import aiohttp
from datetime import datetime, timedelta
import os
import re
import asyncio
import logging
import json as jsonlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- YOUTUBE ----------
try:
    from googleapiclient.discovery import build
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False
    build = None

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_MAX_VIDEOS = int(os.environ.get("YOUTUBE_MAX_VIDEOS", "3"))
YOUTUBE_MAX_COMMENTS = int(os.environ.get("YOUTUBE_MAX_COMMENTS", "20"))
YOUTUBE_REGION = os.environ.get("YOUTUBE_REGION", "KR")

# ---------- PROXY REDDIT (contourne le blocage) ----------
async def fetch_reddit_comments(subreddit, since_time):
    """Récupère les commentaires Reddit via un proxy."""
    url = f"https://api.allorigins.win/get?url={aiohttp.helpers.quote(f'https://www.reddit.com/r/{subreddit}/comments.json?limit=30', safe='')}"
    headers = {"User-Agent": "KToxGuard/1.0"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status != 200:
                    logger.warning(f"[Reddit] Erreur HTTP {response.status}")
                    return []
                data = await response.json()
                reddit_data = jsonlib.loads(data.get('contents', '{}'))
                comments = []
                for child in reddit_data.get('data', {}).get('children', []):
                    comment_data = child.get('data', {})
                    created_utc = datetime.fromtimestamp(comment_data.get('created_utc', 0))
                    if created_utc > since_time:
                        comments.append({
                            "text": comment_data.get('body', ''),
                            "platform": "reddit",
                            "author": comment_data.get('author', 'unknown'),
                            "timestamp": created_utc
                        })
                logger.info(f"[Reddit] {len(comments)} commentaires récupérés")
                return comments
        except Exception as e:
            logger.error(f"[Reddit] Erreur: {e}")
            return []

# ---------- KOREABOO ----------
async def fetch_koreaboo_articles(limit=3):
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
            logger.error(f"[Koreaboo] Erreur: {e}")
            return []

# ---------- YOUTUBE ----------
def fetch_popular_video_ids(region_code, max_results):
    if not YOUTUBE_AVAILABLE or not YOUTUBE_API_KEY:
        return []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.videos().list(
            part="id",
            chart="mostPopular",
            regionCode=region_code,
            maxResults=max_results
        )
        response = request.execute()
        video_ids = [item["id"] for item in response.get("items", [])]
        return video_ids
    except Exception as e:
        logger.error(f"[YouTube] Erreur: {e}")
        return []

def fetch_youtube_comments_sync(video_id, max_comments):
    if not YOUTUBE_AVAILABLE or not YOUTUBE_API_KEY:
        return []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_comments,
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
        logger.error(f"[YouTube] Erreur: {e}")
        return []

async def fetch_youtube_comments():
    if not YOUTUBE_AVAILABLE or not YOUTUBE_API_KEY:
        return []
    video_ids = fetch_popular_video_ids(YOUTUBE_REGION, YOUTUBE_MAX_VIDEOS)
    if not video_ids:
        return []
    all_comments = []
    loop = asyncio.get_event_loop()
    for vid in video_ids:
        comments = await loop.run_in_executor(None, fetch_youtube_comments_sync, vid, YOUTUBE_MAX_COMMENTS)
        all_comments.extend(comments)
    return all_comments

# ---------- COLLECTEUR GLOBAL ----------
async def collect_all_sources(since_time=None):
    """Récupère tous les commentaires disponibles."""
    if since_time is None:
        since_time = datetime.now() - timedelta(days=7)
    
    all_comments = []
    
    # Reddit
    try:
        reddit_comments = await fetch_reddit_comments("kpop", since_time)
        all_comments.extend(reddit_comments)
    except Exception as e:
        logger.error(f"[Collect] Reddit: {e}")
    
    # Koreaboo
    try:
        koreaboo_articles = await fetch_koreaboo_articles(limit=3)
        all_comments.extend(koreaboo_articles)
    except Exception as e:
        logger.error(f"[Collect] Koreaboo: {e}")
    
    # YouTube
    try:
        youtube_comments = await fetch_youtube_comments()
        all_comments.extend(youtube_comments)
    except Exception as e:
        logger.error(f"[Collect] YouTube: {e}")
    
    logger.info(f"Collecte totale: {len(all_comments)} commentaires")
    return all_comments
