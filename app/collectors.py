import aiohttp
from datetime import datetime
import os
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import asyncio

# ---------- CONFIGURATION ----------
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "AIzaSyBrPBb3u__WQicvkokTco77roF_xJ9_czY")
YOUTUBE_SEARCH_QUERIES = os.environ.get("YOUTUBE_SEARCH_QUERIES", "bts,blackpink,ive,nmixx,katseye")
YOUTUBE_MAX_VIDEOS_PER_QUERY = int(os.environ.get("YOUTUBE_MAX_VIDEOS", "3"))
YOUTUBE_MAX_COMMENTS_PER_VIDEO = int(os.environ.get("YOUTUBE_MAX_COMMENTS", "20"))

KEYWORDS = [
    "bts", "bangtan", "seventeen", "txt", "newjeans", "blackpink", "ive", "nmixx", "katseye",
    "kpop", "k-pop", "idol", "fan", "comeback", "concert", "music", "song",
    "방탄소년단", "세븐틴", "투모로우바이투게더", "뉴진스", "블랙핑크", "아이브", "엔믹스"
]

# ---------- REDDIT ----------
async def fetch_reddit_comments(subreddit, since_time):
    url = f"https://www.reddit.com/r/{subreddit}/comments.json?limit=50"
    headers = {"User-Agent": "KToxGuard/1.0 (social listening bot)"}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status != 200:
                    print(f"[Reddit] Status {response.status} pour r/{subreddit}")
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
                print(f"[Reddit] r/{subreddit}: {len(comments)} commentaires pertinents trouvés")
                return comments
        except Exception as e:
            print(f"[Reddit] Erreur r/{subreddit}: {e}")
            return []

# ---------- KOREABOO ----------
async def fetch_koreaboo_articles(limit=5):
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
def search_youtube_videos(query, max_results):
    if not YOUTUBE_API_KEY:
        print("[YouTube] Pas de clé API configurée")
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
        print(f"[YouTube] Recherche '{query}': {len(video_ids)} vidéos trouvées")
        return video_ids
    except HttpError as e:
        print(f"[YouTube Search] Erreur HTTP pour '{query}': {e.resp.status} - {e.content}")
        return []
    except Exception as e:
        print(f"[YouTube Search] Erreur pour '{query}': {e}")
        return []

def fetch_youtube_comments_sync(video_id):
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
        print(f"[YouTube] Vidéo {video_id}: {len(comments)} commentaires récupérés")
        return comments
    except HttpError as e:
        # Erreur fréquente : commentaires désactivés sur la vidéo (403)
        print(f"[YouTube Comments] Erreur HTTP sur {video_id}: {e.resp.status}")
        return []
    except Exception as e:
        print(f"[YouTube Comments] Erreur sur {video_id}: {e}")
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
            filtered = [c for c in comments if c["timestamp"].replace(tzinfo=None) > since_time]
            all_comments.extend(filtered)

    print(f"[YouTube] Total: {len(all_comments)} commentaires collectés")
    return all_comments

# ---------- COLLECTEUR GLOBAL ----------
async def collect_all_sources(since_time):
    all_comments = []

    reddit_comments = await fetch_reddit_comments("kpop", since_time)
    all_comments.extend(reddit_comments)

    koreaboo_articles = await fetch_koreaboo_articles(limit=5)
    all_comments.extend(koreaboo_articles)

    youtube_comments = await fetch_youtube_comments(since_time)
    all_comments.extend(youtube_comments)

    print(f"[Collect] Total global: {len(all_comments)} éléments collectés")
    return all_comments
