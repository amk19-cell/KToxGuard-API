import snscrape.modules.reddit as sns_reddit
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fetch_reddit_comments(subreddit, since_time, limit=30):
    """Récupère les commentaires récents d'un subreddit via snscrape."""
    try:
        query = f"subreddit:{subreddit}"
        comments = []
        for i, comment in enumerate(sns_reddit.RedditCommentScraper(query).get_items()):
            if i >= limit:
                break
            created = comment.date
            if created > since_time:
                comments.append({
                    "text": comment.content,
                    "platform": "reddit",
                    "author": comment.user.username,
                    "timestamp": created
                })
        logger.info(f"[Reddit] {len(comments)} commentaires récupérés")
        return comments
    except Exception as e:
        logger.error(f"[Reddit] Erreur: {e}")
        return []

async def collect_all_sources():
    since_time = datetime.now() - timedelta(minutes=10)
    all_comments = []
    
    # Reddit (via snscrape)
    reddit_comments = await fetch_reddit_comments("kpop", since_time, limit=30)
    all_comments.extend(reddit_comments)
    
    # YouTube (si clé API disponible)
    # à ajouter plus tard
    
    logger.info(f"Collecte totale: {len(all_comments)} commentaires")
    return all_comments
