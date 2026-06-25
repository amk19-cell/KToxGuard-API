from datetime import datetime
import os
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import asyncio
import feedparser

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_SEARCH_QUERIES = os.environ.get(
    "YOUTUBE_SEARCH_QUERIES",
    "bts,blackpink,ive,nmixx,katseye,korea school bullying,korean society,학교 폭력"
)
YOUTUBE_MAX_VIDEOS_PER_QUERY = int(os.environ.get("YOUTUBE_MAX_VIDEOS", "2"))
YOUTUBE_MAX_COMMENTS_PER_VIDEO = int(os.environ.get("YOUTUBE_MAX_COMMENTS", "20"))

RSS_FEEDS = [
    "https://www.yna.co.kr/rss/news.xml",
    "https://www.yna.co.kr/rss/society.xml",
]

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
        await asyncio.sleep(1)  # pause entre requêtes pour éviter le 429
    print(f"[YouTube] Total: {len(all_comments)} commentaires")
    return all_comments

def fetch_rss_feeds():
    articles = []
    seen_titles = set()
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                title = entry.get("title", "")
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                articles.append({
                    "text": f"[RSS] {title} - {entry.get('summary', '')}",
                    "platform": "rss",
                    "author": "Yonhap",
                    "timestamp": datetime.now()
                })
            print(f"[RSS] {len(feed.entries)} articles depuis {url}")
        except Exception as e:
            print(f"[RSS] Erreur sur {url}: {e}")
    return articles

async def collect_all_sources(since_time):
    all_comments = []
    youtube_comments = await fetch_youtube_comments(since_time)
    all_comments.extend(youtube_comments)
    rss_articles = fetch_rss_feeds()
    all_comments.extend(rss_articles)
    print(f"[Collect] Total: {len(all_comments)} éléments")
    return all_comments
