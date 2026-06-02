import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# Récupérer l'URL de connexion
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# 1. CORRECTION : SQLAlchemy asynchrone nécessite le préfixe +asyncpg
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# 2. NETTOYAGE : Supprimer les paramètres ?sslmode=... qui peuvent bloquer
if "?sslmode=" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?sslmode=")[0]

# 3. CRÉATION DU MOTEUR avec SSL forcé
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    connect_args={"ssl": "require"}
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
