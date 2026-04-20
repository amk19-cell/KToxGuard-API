from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from app.detector import detect_toxicity

# Création de l'application
app = FastAPI(
    title="KToxGuard API",
    description="API de détection de harcèlement et menaces en coréen",
    version="1.0.0"
)

# Configuration CORS (pour que le frontend puisse appeler l'API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre plus tard avec les domaines autorisés
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèle de données pour la requête
class MessageIn(BaseModel):
    text: str
    platform: Optional[str] = None
    author: Optional[str] = None
    ip_address: Optional[str] = None

# Modèle de données pour la réponse
class ToxicityResponse(BaseModel):
    label: str
    confidence: float
    keywords_found: List[str]
    threat_types: List[str]

# Endpoint racine (GET) - pour vérifier que l'API est vivante
@app.get("/")
def root():
    return {"message": "Anti-Violence API is running", "status": "ok"}

# Endpoint d'analyse (POST)
@app.post("/analyze", response_model=ToxicityResponse)
async def analyze(msg: MessageIn):
    result = detect_toxicity(msg.text)
    return result

# Endpoint de santé (pour UptimeRobot)
@app.get("/health")
def health():
    return {"status": "healthy"}
