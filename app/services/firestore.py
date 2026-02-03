from google.cloud import firestore
from loguru import logger
from typing import Any, Dict, Optional

from app.config import settings

# Initialize Firestore client
_db: Optional[firestore.AsyncClient] = None


def get_firestore_client() -> Optional[firestore.AsyncClient]:
    global _db
    if _db is None:
        try:
            _db = firestore.AsyncClient(project=settings.GOOGLE_PROJECT_ID)
        except Exception as e:
            logger.warning(f"Firestore init failed: {e}")
    return _db


async def save_state(key: str, data: Dict[str, Any]) -> None:
    """Save agent state to Firestore."""
    db = get_firestore_client()
    if not db:
        return
    try:
        doc_ref = db.collection("scrum_states").document(key)
        await doc_ref.set(data, merge=True)
        logger.debug(f"State saved for {key}")
    except Exception as e:
        logger.error(f"Error saving state: {e}")


async def load_state(key: str) -> Optional[Dict[str, Any]]:
    """Load agent state from Firestore."""
    db = get_firestore_client()
    if not db:
        return None
    try:
        doc_ref = db.collection("scrum_states").document(key)
        doc = await doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"Error loading state: {e}")
        return None
