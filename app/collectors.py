import aiohttp
from datetime import datetime, timedelta
import os
import asyncio
import logging

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
YOUTUBE_MAX_VIDEOS = int(os.environ.get("YOUTUBE_MAX_VIDEOS", "5"))
YOUTUBE_MAX_COMMENTS = int(os.environ.get("YOUTUBE_MAX_COMMENTS", "20"))
YOUTUBE_REGION = os.environ.get("YOUTUBE_REGION", "KR")

# ---------- YOUTUBE (FONCTIONNE) ----------
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
        logger.info(f"[YouTube] Vidéo {vid}: {len(comments)} commentaires")
    return all_comments

# ---------- REDDIT (bloqué, on le désactive) ----------
async def fetch_reddit_comments(subreddit, since_time):
    logger.warning("[Reddit] Désactivé (bloqué par Reddit)")
    return []

# ---------- KOREABOO (problème de scraping, désactivé) ----------
async def fetch_koreaboo_articles(limit=3):
    logger.warning("[Koreaboo] Désactivé (problème de scraping)")
    return []

# ---------- COLLECTEUR GLOBAL ----------
async def collect_all_sources(since_time=None):
    if since_time is None:
        since_time = datetime.now() - timedelta(days=7)
    
    all_comments = []
    
    # YouTube (seul)
    youtube_comments = await fetch_youtube_comments()
    all_comments.extend(youtube_comments)
    
    logger.info(f"Collecte totale: {len(all_comments)} commentaires YouTube")
    return all_comments
