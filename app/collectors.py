# Fichier collectors.py minimaliste pour stabiliser l'API
# Ce fichier ne fait rien pour le moment, mais il ne contient aucune erreur de syntaxe.

import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def collect_all_sources():
    """Version ultra-simple qui ne collecte rien pour l'instant."""
    logger.info("Collecte désactivée (API stabilisée).")
    return []
