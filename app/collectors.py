import aiohttp
from datetime import datetime
import json
from pathlib import Path

# Liste de mots-clés par défaut (sans fichier)
DEFAULT_KEYWORDS = ["bts", "bangtan", "seventeen", "txt", "newjeans", "뉴진스", "방탄"]

async def fetch_reddit_comments(subreddit, since_time):
    url = f"https://www.reddit.com/r/{subreddit}/comments.json?limit=30"
    headers = {"User-Agent": "KToxGuard/1.0"}
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
                        if any(kw in text for kw in DEFAULT_KEYWORDS) and any('\uac00' <= c <= '\ud7a3' for c in text):
                            comments.append({
                                "text": comment_data.get("body", ""),
                                "platform": "reddit",
                                "author": comment_data.get("author", "unknown")
                            })
                return comments
        except Exception as e:
            print(f"Erreur collecte: {e}")
            return []
