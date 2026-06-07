import aiohttp
from datetime import datetime
from typing import List, Dict

DEFAULT_KEYWORDS = ["bts", "bangtan", "seventeen", "txt", "newjeans", "뉴진스", "방탄", "하이브"]

async def fetch_reddit_comments_paginated(subreddit: str, limit: int = 1000) -> List[Dict]:
    """Récupère les `limit` derniers commentaires (max 1000) du subreddit."""
    url = f"https://www.reddit.com/r/{subreddit}/comments.json?limit=100"
    headers = {"User-Agent": "KToxGuard/1.0"}
    comments = []
    after = None
    while len(comments) < limit:
        params = {"limit": 100}
        if after:
            params["after"] = after
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    break
                data = await response.json()
                children = data.get("data", {}).get("children", [])
                if not children:
                    break
                for child in children:
                    comment_data = child.get("data", {})
                    text = comment_data.get("body", "")
                    # Filtrer les commentaires coréens contenant les mots-clés
                    if any(kw in text.lower() for kw in DEFAULT_KEYWORDS) and any('\uac00' <= c <= '\ud7a3' for c in text):
                        comments.append({
                            "text": text,
                            "platform": "reddit",
                            "author": comment_data.get("author", "unknown"),
                            "created_utc": comment_data.get("created_utc", 0)
                        })
                after = data.get("data", {}).get("after")
                if not after:
                    break
    return comments[:limit]
