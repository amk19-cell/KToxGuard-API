from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.detector import detect_toxicity

app = FastAPI(title="Anti-Violence API") ): from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre plus tard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MessageIn(BaseModel):
    text: str
    platform: Optional[str] = None
    author: Optional[str] = None
    ip_address: Optional[str] = None

@app.post("/analyze")
async def analyze(msg: MessageIn):
    result = detect_toxicity(msg.text)
    # Pour l'instant on ne stocke pas en base (on le fera plus tard)
    return result

@app.get("/")
def root():
    return {"message": "Anti-Violence API is running"}
