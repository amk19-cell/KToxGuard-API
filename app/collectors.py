import aiohttp
import logging
from datetime import datetime, timedelta
import json as jsonlib

async def fetch_reddit_comments(subreddit, since_time, limit=30):
    url = f"https://api.allorigins.win/get?url={aiohttp.helpers.quote(f'https://www.reddit.com/r/{subreddit}/comments.json?limit={limit}', safe='')}"
    headers = {"User-Agent": "KToxGuard/1.0"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status != 200:
                    return []
                data = await response.json()
                reddit_data = jsonlib.loads(data.get('contents', '{}'))
                comments = []
                for child in reddit_data.get('data', {}).get('children', []):
                    comment_data = child.get('data', {})
                    created_utc = datetime.fromtimestamp(comment_data.get('created_utc', 0))
                    if created_utc > since_time:
                        comments.append({
                            "text": comment_data.get('body', ''),
                            "platform": "reddit",
                            "author": comment_data.get('author', 'unknown'),
                            "timestamp": created_utc
                        })
                return comments
        except Exception as e:
            logger.error(f"[Reddit] Erreur: {e}")
            return []
