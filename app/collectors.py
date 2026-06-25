from datetime import datetime
import os
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import asyncio
import re

# ---------- CONFIGURATION ----------
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "AIzaSyBrPBb3u__WQicvkokTco77roF_xJ9_czY")
YOUTUBE_SEARCH_QUERIES = os.environ.get(
    "YOUTUBE_SEARCH_QUERIES",
    # REQUÊTES ÉLARGIES (anglais + coréen)
    "bts,blackpink,ive,nmixx,katseye,korea school bullying,korea cyberbullying,"
    "korean news,korean society,korean education,"
    "학교 폭력,왕따,한국 사회,한국 교육,한국 뉴스,사이버폭력,청소년,한국 생활"
)
YOUTUBE_MAX_VIDEOS_PER_QUERY = int(os.environ.get("YOUTUBE_MAX_VIDEOS", "2"))
YOUTUBE_MAX_COMMENTS_PER_VIDEO = int(os.environ.get("YOUTUBE_MAX_COMMENTS", "20"))

# ---------- FONCTIONS ----------
def search_youtube_videos(query, max_results):
    if not YOUTUBE_API_KEY:
        return []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.search().list(
            part="id", q=query, type="video", order="date", maxResults=max_results
        )
        response = request.execute()
        video_ids = [item["id"]["videoId"] for item in response.get("items", [])]
        print(f"[YouTube] '{query}': {len(video_ids)} vidéos")
        return video_ids
    except HttpError as e:
        print(f"[YouTube Search] Erreur HTTP '{query}': {e.resp.status}")
        return []
    except Exception as e:
        print(f"[YouTube Search] Erreur '{query}': {e}")
        return []

def fetch_youtube_comments_sync(video_id):
    if not YOUTUBE_API_KEY:
        return []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.commentThreads().list(
            part="snippet", videoId=video_id,
            maxResults=YOUTUBE_MAX_COMMENTS_PER_VIDEO, textFormat="plainText"
        )
        response = request.execute()
        comments = []
        for item in response.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            published_at = snippet.get("publishedAt", "")
            try:
                timestamp = datetime.fromisoformat(published_at.replace('Z', '+00:00')).replace(tzinfo=None)
            except:
                timestamp = datetime.now()
            comments.append({
                "text": snippet.get("textDisplay", ""),
                "platform": "youtube",
                "author": snippet.get("authorDisplayName", "unknown"),
                "timestamp": timestamp
            })
        print(f"[YouTube] Vidéo {video_id}: {len(comments)} commentaires")
        return comments
    except HttpError as e:
        print(f"[YouTube Comments] Erreur HTTP {video_id}: {e.resp.status}")
        return []
    except Exception as e:
        print(f"[YouTube Comments] Erreur {video_id}: {e}")
        return []

async def fetch_youtube_comments(since_time):
    if not YOUTUBE_API_KEY:
        return []
    queries = [q.strip() for q in YOUTUBE_SEARCH_QUERIES.split(",") if q.strip()]
    all_comments = []
    loop = asyncio.get_event_loop()
    for query in queries:
        video_ids = await loop.run_in_executor(None, search_youtube_videos, query, YOUTUBE_MAX_VIDEOS_PER_QUERY)
        for vid in video_ids:
            comments = await loop.run_in_executor(None, fetch_youtube_comments_sync, vid)
            filtered = [c for c in comments if c["timestamp"] > since_time]
            all_comments.extend(filtered)
    print(f"[YouTube] Total: {len(all_comments)} commentaires")
    return all_comments

async def collect_all_sources(since_time):
    all_comments = await fetch_youtube_comments(since_time)
    print(f"[Collect] Total: {len(all_comments)} éléments")
    return all_comments
