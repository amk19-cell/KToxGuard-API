import aiohttp
from datetime import datetime
import os
import json
from pathlib import Path

# ---------- MOTS-CLÉS ÉLARGIS ----------
KEYWORDS = [
    # Groupes
    "bts", "bangtan", "seventeen", "txt", "newjeans", "blackpink", "ive", "nmixx", "katseye",
    # Coréen
    "방탄소년단", "세븐틴", "투모로우바이투게더", "뉴진스", "블랙핑크", "아이브", "엔믹스", "캣츠아이",
    # Membres BTS
    "jimin", "rm", "v", "jungkook", "suga", "jin", "jhope",
    # Membres SEVENTEEN
    "scoups", "jeonghan", "joshua", "jun", "hoshi", "wonwoo", "woozi", "dk", "mingyu", "the8", "seungkwan", "vernon", "dino",
    # Membres TXT
    "soobin", "yeonjun", "beomgyu", "taehyun", "hueningkai",
    # Membres NewJeans
    "minji", "hanni", "danielle", "haerin", "hyein",
    # Membres BLACKPINK
    "jisoo", "jennie", "rosé", "lisa",
    # Membres IVE
    "yujin", "gaeul", "rei", "wonyoung", "liz", "leeseo",
    # Mots généraux
    "kpop", "k-pop", "korea", "corée", "idol", "fan"
]

async def fetch_reddit_comments(subreddit, since_time):
    url = f"https://www.reddit.com/r/{subreddit}/comments.json?limit=30"
    headers = {"User-Agent": "KToxGuard/1.0 (social listening bot)"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status != 200:
                    return []
                data = await response.json()
                comments = []
                for child in data.get("data", {}).get("children", []):
                    comment_data = child.get("data", {})
                    created_utc = datetime.fromtimestamp(comment_data.get("created_utc", 0))
                    if created_utc > since_time:
                        text = comment_data.get("body", "").lower()
                        # Filtre par mots-clés (sans restriction de langue)
                        if any(kw in text for kw in KEYWORDS):
                            comments.append({
                                "text": comment_data.get("body", ""),
                                "platform": "reddit",
                                "author": comment_data.get("author", "unknown"),
                                "timestamp": created_utc
                            })
                return comments
        except Exception as e:
            print(f"[Reddit] Erreur: {e}")
            return []

# ---------- KOREABOO (scraping) ----------
async def fetch_koreaboo_articles(limit: int = 10) -> list:
    url = "https://www.koreaboo.com"
    headers = {"User-Agent": "KToxGuard/1.0 (social listening bot)"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status != 200:
                    return []
                html = await response.text()
                # Extraction basique (à améliorer avec BeautifulSoup si besoin)
                import re
                article_pattern = r'<a href="([^"]+)"[^>]*>([^<]+)</a>'
                matches = re.findall(article_pattern, html)
                articles = []
                for link, title in matches[:limit]:
                    if "news" in link or "article" in link:
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

# ---------- COLLECTEUR GLOBAL ----------
async def collect_all_sources(since_time: datetime) -> list:
    all_comments = []
    # Reddit
    reddit_comments = await fetch_reddit_comments("kpop", since_time)
    all_comments.extend(reddit_comments)
    # Koreaboo
    koreaboo_articles = await fetch_koreaboo_articles(limit=5)
    all_comments.extend(koreaboo_articles)
    return all_comments
