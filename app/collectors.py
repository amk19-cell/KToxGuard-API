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
YOUTUBE_SEARCH_QUERY = os.environ.get("YOUTUBE_SEARCH_QUERY", "kpop,korea,music,vlog,news")
YOUTUBE_MAX_VIDEOS = int(os.environ.get("YOUTUBE_MAX_VIDEOS", "3"))
YOUTUBE_MAX_COMMENTS = int(os.environ.get("YOUTUBE_MAX_COMMENTS", "20"))

# ---------- FONCTION DE RECHERCHE DE VIDÉOS ----------
def search_youtube_videos(query, max_results):
    """Recherche des vidéos YouTube récentes pour une requête donnée."""
    if not YOUTUBE_AVAILABLE or not YOUTUBE_API_KEY:
        return []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.search().list(
            part="id",
            q=query,
            type="video",
            order="date",
            maxResults=max_results,
            relevanceLanguage="ko"
        )
        response = request.execute()
        video_ids = [item["id"]["videoId"] for item in response.get("items", [])]
        logger.info(f"[YouTube Search] {len(video_ids)} vidéos pour '{query}'")
        return video_ids
    except Exception as e:
        logger.error(f"[YouTube Search] Erreur: {e}")
        return []

def fetch_comments_for_video(video_id, max_comments):
    """Récupère les commentaires d'une vidéo YouTube."""
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
        logger.info(f"[YouTube] {len(comments)} commentaires pour {video_id}")
        return comments
    except Exception as e:
        logger.error(f"[YouTube] Erreur sur {video_id}: {e}")
        return []

# ---------- REDDIT (désactivé) ----------
async def fetch_reddit_comments(subreddit, since_time):
    logger.warning("[Reddit] Désactivé (bloqué)")
    return []

# ---------- KOREABOO (désactivé) ----------
async def fetch_koreaboo_articles(limit=3):
    logger.warning("[Koreaboo] Désactivé")
    return []

# ---------- COLLECTEUR GLOBAL ----------
async function collect_all_sources():
    all_comments = []
    
    # YouTube Search
    if YOUTUBE_API_KEY:
        queries = [q.strip() for q in YOUTUBE_SEARCH_QUERY.split(",") if q.strip()]
        loop = asyncio.get_event_loop()
        for query in queries:
            video_ids = await loop.run_in_executor(None, search_youtube_videos, query, YOUTUBE_MAX_VIDEOS)
            for vid in video_ids:
                comments = await loop.run_in_executor(None, fetch_comments_for_video, vid, YOUTUBE_MAX_COMMENTS)
                all_comments.extend(comments)
    
    logger.info(f"Collecte totale: {len(all_comments)} commentaires")
    return all_comments
