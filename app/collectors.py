import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- COLLECTEUR SIMPLIFIÉ (pour éviter les erreurs) ----------
async def collect_all_sources():
    """Version simplifiée qui ne collecte rien pour l'instant."""
    logger.info("Collecte désactivée – API en ligne")
    return []
