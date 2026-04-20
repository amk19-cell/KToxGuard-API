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
from sqlalchemy import func, select

@app.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    # 1. Total (syntaxe universelle)
    total_result = await db.execute(select(func.count(models.Message.id)))
    total = total_result.scalar() or 0
    
    if total == 0:
        return {
            "total_messages": 0,
            "toxic_count": 0,
            "toxic_percentage": 0.0,
            "by_threat_type": {},
            "top_keywords": {}
        }
    
    # 2. Toxiques (syntaxe universelle)
    toxic_result = await db.execute(
        select(func.count()).where(models.Message.label == "toxique")
    )
    toxic_count = toxic_result.scalar() or 0
    
    toxic_percentage = round((toxic_count / total) * 100, 2)
    
    # 3. Types de menace
    threat_result = await db.execute(select(models.Message.threat_types))
    threat_counts = {}
    for row in threat_result:
        if row[0]:
            for t in row[0]:
                threat_counts[t] = threat_counts.get(t, 0) + 1
    
    # 4. Mots-clés
    kw_result = await db.execute(select(models.Message.keywords_found))
    kw_counts = {}
    for row in kw_result:
        if row[0]:
            for kw in row[0]:
                kw_counts[kw] = kw_counts.get(kw, 0) + 1
    
    top_keywords = dict(sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)[:5])
    
    return {
        "total_messages": total,
        "toxic_count": toxic_count,
        "toxic_percentage": toxic_percentage,
        "by_threat_type": threat_counts,
        "top_keywords": top_keywords
    }
