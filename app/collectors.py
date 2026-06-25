from datetime import datetime
import os
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import asyncio
import feedparser
import re
import twscrape   # <-- remplace snscrape

# ---------- CONFIGURATION ----------
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "AIzaSyBrPBb3u__WQicvkokTco77roF_xJ9_czY")
YOUTUBE_SEARCH_QUERIES = os.environ.get(
    "YOUTUBE_SEARCH_QUERIES",
    "bts,blackpink,ive,nmixx,katseye,korea school bullying,korea cyberbullying,"
    "korean news,korean society,korean education,"
    "학교 폭력,왕따,한국 사회,한국 교육,한국 뉴스,사이버폭력,청소년,한국 생활"
)
YOUTUBE_MAX_VIDEOS_PER_QUERY = int(os.environ.get("YOUTUBE_MAX_VIDEOS", "2"))
YOUTUBE_MAX_COMMENTS_PER_VIDEO = int(os.environ.get("YOUTUBE_MAX_COMMENTS", "20"))

# ---------- FLUX RSS ----------
RSS_FEEDS = [
    "https://www.yna.co.kr/rss/news.xml",
    "https://www.yna.co.kr/rss/politics.xml",
    "https://www.yna.co.kr/rss/economy.xml",
    "https://www.yna.co.kr/rss/society.xml",
    "https://www.yna.co.kr/rss/culture.xml",
]

# ---------- CONFIGURATION TWITTER ----------
TWITTER_MAX_TWEETS_PER_QUERY = 15
TWITTER_QUERIES = [
    "학교 폭력", "왕따", "한국 교육", "사이버폭력", "한국 사회",
    "청소년 문제", "한국 뉴스", "korea school bullying", "korea cyberbullying",
    "korean society", "korean education", "Korean youth", "Korean students"
]

# ---------- FONCTIONS YOUTUBE ----------
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

# ---------- FONCTIONS RSS ----------
def fetch_rss_feeds():
    articles = []
    seen_titles = set()
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                title = entry.get("title", "")
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                text = f"[RSS] {title} - {entry.get('summary', '')}"
                articles.append({
                    "text": text,
                    "platform": "rss",
                    "author": "Yonhap",
                    "timestamp": datetime.now()
                })
            print(f"[RSS] {len(feed.entries)} articles récupérés depuis {url}")
        except Exception as e:
            print(f"[RSS] Erreur sur {url}: {e}")
    return articles

# ---------- FONCTION TWITTER (avec twscrape) ----------
def fetch_twitter_twscrape(since_time, max_tweets_per_query=TWITTER_MAX_TWEETS_PER_QUERY):
    """
    Récupère des tweets récents avec twscrape (fork compatible Python 3.12).
    """
    tweets = []
    since_str = since_time.strftime("%Y-%m-%d") if since_time else "2020-01-01"
    
    # Utilisation de l'API twscrape (similaire à snscrape)
    scraper = twscrape.TwitterSearchScraper()
    
    for query in TWITTER_QUERIES:
        search_query = f"{query} since:{since_str} lang:ko OR lang:en"
        try:
            count = 0
            # Récupération des tweets via le scraper
            for tweet in scraper.get_items(search_query, limit=max_tweets_per_query):
                # Les objets tweet ont des attributs : date, content, user.username
                if tweet.date.replace(tzinfo=None) < since_time:
                    continue
                tweets.append({
                    "text": tweet.content,
                    "platform": "twitter",
                    "author": tweet.user.username,
                    "timestamp": tweet.date.replace(tzinfo=None)
                })
                count += 1
            print(f"[Twitter] {count} tweets récupérés pour '{query}'")
        except Exception as e:
            print(f"[Twitter] Erreur sur la requête '{query}': {e}")
    
    print(f"[Twitter] Total: {len(tweets)} tweets")
    return tweets

# ---------- COLLECTEUR GLOBAL ----------
async def collect_all_sources(since_time):
    all_comments = []
    
    youtube_comments = await fetch_youtube_comments(since_time)
    all_comments.extend(youtube_comments)
    
    rss_articles = fetch_rss_feeds()
    all_comments.extend(rss_articles)
    
    # Twitter (twscrape) – exécution synchrone dans un thread
    loop = asyncio.get_event_loop()
    twitter_tweets = await loop.run_in_executor(None, fetch_twitter_twscrape, since_time)
    all_comments.extend(twitter_tweets)
    
    print(f"[Collect] Total: {len(all_comments)} éléments")
    return all_comments
