import aiohttp
from datetime import datetime
from typing import List, Dict

# Mots-clés élargis (anglais + coréen)
KEYWORDS = [
    "bts", "bangtan", "seventeen", "txt", "newjeans",
    "방탄소년단", "세븐틴", "투모로우바이투게더", "뉴진스",
    "jimin", "jungkook", "v", "suga", "rm", "jin", "jhope",
    "vernon", "mingyu", "wonwoo", "woozi"
]

async def fetch_reddit_comments(subreddit, since_time):
    """Récupère les 30 derniers commentaires (toutes langues) contenant les mots-clés."""
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
                        # Filtre par mots-clés (suppression du filtre coréen)
                        if any(kw in text for kw in KEYWORDS):
                            comments.append({
                                "text": comment_data.get("body", ""),
                                "platform": "reddit",
                                "author": comment_data.get("author", "unknown")
                            })
                return comments
        except Exception as e:
            print(f"Erreur collecte: {e}")
            return []
