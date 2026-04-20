from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from app.detector import detect_toxicity
from app.database import engine, get_db
from app import models

app = FastAPI(title="KToxGuard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MessageIn(BaseModel):
    text: str
    platform: Optional[str] = None
    author: Optional[str] = None
    ip_address: Optional[str] = None

@app.on_event("startup")
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

@app.get("/")
def root():
    return {"message": "KToxGuard API is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/analyze")
async def analyze(msg: MessageIn, db: AsyncSession = Depends(get_db)):
    result = detect_toxicity(msg.text)
    
    db_msg = models.Message(
        text=msg.text,
        platform=msg.platform,
        author=msg.author,
        ip_address=msg.ip_address,
        label=result["label"],
        confidence=result["confidence"],
        keywords_found=result["keywords_found"],
        threat_types=result["threat_types"]
    )
    db.add(db_msg)
    await db.commit()
    
    return result

# ========== NOUVEL ENDPOINT STATISTIQUES ==========
@app.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    # Nombre total de messages
    total = await db.scalar(func.count(models.Message.id))
    
    # Nombre de messages toxiques
    toxic_count = await db.scalar(
        func.count().filter(models.Message.label == "toxique")
    )
    
    # Pourcentage de toxicité
    toxic_percentage = (toxic_count / total * 100) if total > 0 else 0
    
    # Répartition par type de menace (dérouler le JSON)
    threat_counts = {}
    messages = await db.execute(models.Message.threat_types)
    for row in messages:
        for t in row[0] or []:
            threat_counts[t] = threat_counts.get(t, 0) + 1
    
    # Top 5 des mots-clés les plus fréquents
    keyword_counts = {}
    kw_messages = await db.execute(models.Message.keywords_found)
    for row in kw_messages:
        for kw in row[0] or []:
            keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
    
    top_keywords = dict(sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:5])
    
    return {
        "total_messages": total,
        "toxic_count": toxic_count,
        "toxic_percentage": round(toxic_percentage, 2),
        "by_threat_type": threat_counts,
        "top_keywords": top_keywords
    }
