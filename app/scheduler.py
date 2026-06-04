import asyncio
from threading import Thread
from app.collectors import fetch_reddit_comments
from app.database import AsyncSessionLocal
from app import models
from app.detector import detect_toxicity
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def collect_and_store():
    logger.info(f"[Scheduler] Collecte Reddit démarrée à {datetime.now()}")
    async with AsyncSessionLocal() as db:
        since = datetime.now()
        comments = await fetch_reddit_comments("kpop", since)
        for comment in comments:
            result = detect_toxicity(comment["text"], lang="en")
            db_msg = models.Message(
                text=comment["text"],
                platform=comment["platform"],
                author=comment["author"],
                label=result["label"],
                confidence=result["confidence"],
                keywords_found=result["keywords_found"],
                threat_types=result["threat_types"],
                recommendations=result.get("recommendations", {}),
                lang="en"
            )
            db.add(db_msg)
        await db.commit()
        logger.info(f"[Scheduler] {len(comments)} commentaires collectés")

def run_async_in_thread(loop, coro):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(coro)

def start_scheduler():
    def scheduler_loop():
        loop = asyncio.new_event_loop()
        while True:
            try:
                loop.run_until_complete(collect_and_store())
            except Exception as e:
                logger.error(f"Erreur dans le scheduler: {e}")
            import time
            time.sleep(600)  # 10 minutes

    thread = Thread(target=scheduler_loop, daemon=True)
    thread.start()
    logger.info("[Scheduler] Service de collecte Reddit démarré (toutes les 10 minutes)")
