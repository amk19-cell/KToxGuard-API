import aiohttp
from datetime import datetime
import json
from pathlib import Path

# Charger les mots-clés des artistes
ARTIST_FILE = Path(__file__).parent / "artists.json"
ARTIST_KEYWORDS = []
if ARTIST_FILE.exists():
    with open(ARTIST_FILE, "r", encoding="utf-8") as f:
        artists = json.load(f)
        for artist in artists:
            ARTIST_KEYWORDS.extend(artist.get("keywords", []))
else:
    ARTIST_KEYWORDS = ["bts", "seventeen", "txt", "newjeans"]

async def fetch_reddit_comments(subreddit, since_time):
    url = f"https://www.reddit.com/r/{subreddit}/comments.json?limit=30"
    headers = {"User-Agent": "KToxGuard/1.0 (social listening bot)"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return []
                data = await response.json()
                comments = []
                for child in data.get("data", {}).get("children", []):
                    comment_data = child.get("data", {})
                    created_utc = datetime.fromtimestamp(comment_data.get("created_utc", 0))
                    if created_utc > since_time:
                        text = comment_data.get("body", "").lower()
                        if any(kw in text for kw in ARTIST_KEYWORDS) and any('\uac00' <= c <= '\ud7a3' for c in text):
                            comments.append({
                                "text": comment_data.get("body", ""),
                                "platform": "reddit",
                                "author": comment_data.get("author", "unknown")
                            })
                return comments
        except Exception as e:
            print(f"Erreur Reddit: {e}")
            return []
