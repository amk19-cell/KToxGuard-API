from app.collectors import collect_all_sources

async def trigger_collect(db: AsyncSession):
    global last_collect_time
    now = datetime.now()
    comments = await collect_all_sources(last_collect_time)
    for comment in comments:
        result = simple_detect(comment["text"], "en")
        db_msg = models.Message(
            text=comment["text"],
            platform=comment["platform"],
            author=comment["author"],
            timestamp=comment.get("timestamp", now),
            label=result["label"],
            confidence=result["confidence"],
            keywords_found=json.dumps(result["keywords_found"]),
            threat_types=json.dumps(result["threat_types"]),
            recommendations=json.dumps(result["recommendations"]),
            lang="en"
        )
        db.add(db_msg)
    await db.commit()
    last_collect_time = now
    return {"status": "ok", "collected": len(comments)}
