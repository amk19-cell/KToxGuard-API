from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.collectors import fetch_reddit_comments
from app.database import AsyncSessionLocal
from app import models
from app.detector import detect_toxicity
from datetime import datetime

async def collect_and_store():
    print(f"[Scheduler] Collecte Reddit démarrée à {datetime.now()}")
    
    async with AsyncSessionLocal() as db:
        since_time = datetime.now()
        comments = await fetch_reddit_comments("kpop", since_time)
        
        for comment in comments:
            result = detect_toxicity(comment["text"])
            db_msg = models.Message(
                text=comment["text"],
                platform=comment["platform"],
                author=comment["author"],
                label=result["label"],
                confidence=result["confidence"],
                keywords_found=result["keywords_found"],
                threat_types=result["threat_types"]
            )
            db.add(db_msg)
        
        await db.commit()
        print(f"[Scheduler] {len(comments)} commentaires collectés")

def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        collect_and_store,
        trigger=IntervalTrigger(minutes=10),
        id="reddit_collector",
        replace_existing=True
    )
    scheduler.start()
    print("[Scheduler] Service de collecte Reddit démarré (toutes les 10 minutes)")
    return scheduler
