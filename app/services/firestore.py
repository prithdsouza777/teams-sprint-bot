import json
import os
from pathlib import Path
from loguru import logger
from typing import Any, Dict, Optional

# File-based persistent storage (survives server restarts)
_STATE_DIR = Path(__file__).parent.parent.parent / ".state"
_STATE_DIR.mkdir(exist_ok=True)

# In-memory cache for faster reads
_memory_states: Dict[str, Dict[str, Any]] = {}
_memory_conversations: Dict[str, Dict[str, Any]] = {}

# Firestore client (optional cloud backup)
_db = None


def _sanitize_key(key: str) -> str:
    """Sanitize key for use as filename."""
    return key.replace(":", "_").replace("/", "_").replace("\\", "_")


def get_firestore_client():
    global _db
    if _db is None:
        try:
            from google.cloud import firestore
            from app.config import settings
            _db = firestore.AsyncClient(project=settings.GOOGLE_PROJECT_ID)
            logger.info("Firestore client initialized")
        except Exception as e:
            logger.debug(f"Firestore unavailable (using file storage): {e}")
    return _db


async def save_state(key: str, data: Dict[str, Any]) -> None:
    """Save agent state to file and optionally Firestore."""
    # Save to memory first
    _memory_states[key] = data
    
    # Save to file (persistent across restarts)
    try:
        file_path = _STATE_DIR / f"{_sanitize_key(key)}.json"
        with open(file_path, 'w') as f:
            json.dump(data, f)
        logger.debug(f"State saved to file: {file_path.name}")
    except Exception as e:
        logger.error(f"File save failed: {e}")
    
    # Try Firestore backup
    db = get_firestore_client()
    if db:
        try:
            doc_ref = db.collection("scrum_states").document(key)
            await doc_ref.set(data, merge=True)
        except Exception as e:
            logger.warning(f"Firestore save failed for {key}: {e}")


async def load_state(key: str) -> Optional[Dict[str, Any]]:
    """Load agent state from memory, Firestore, or file."""
    # Check memory first
    if key in _memory_states:
        logger.debug(f"State loaded from memory for {key}")
        return _memory_states[key]
    
    # Check Firestore (High Priority for multi-instance consistency)
    db = get_firestore_client()
    if db:
        try:
            doc_ref = db.collection("scrum_states").document(key)
            doc = await doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                _memory_states[key] = data
                logger.debug(f"State loaded from Firestore for {key}")
                return data
        except Exception as e:
            logger.warning(f"Firestore load failed for {key}: {e}")
    
    # Check file (Fallback)
    try:
        file_path = _STATE_DIR / f"{_sanitize_key(key)}.json"
        if file_path.exists():
            with open(file_path, 'r') as f:
                data = json.load(f)
            _memory_states[key] = data  # Cache in memory
            logger.debug(f"State loaded from file: {file_path.name}")
            return data
    except Exception as e:
        logger.warning(f"File load failed for {key}: {e}")
    
    return None


async def clear_state(key: str) -> None:
    """Clear agent state."""
    _memory_states.pop(key, None)
    
    # Remove file
    try:
        file_path = _STATE_DIR / f"{_sanitize_key(key)}.json"
        if file_path.exists():
            file_path.unlink()
    except Exception:
        pass
    
    # Clear Firestore
    db = get_firestore_client()
    if db:
        try:
            await db.collection("scrum_states").document(key).delete()
        except Exception:
            pass


async def save_conversation_reference(reference: Dict[str, Any]) -> None:
    """Save conversation reference for proactive messaging."""
    key = reference.get("conversation", {}).get("id")
    if not key:
        return
    
    _memory_conversations[key] = reference
    
    # Save to file
    try:
        file_path = _STATE_DIR / f"conv_{_sanitize_key(key)}.json"
        with open(file_path, 'w') as f:
            json.dump(reference, f)
    except Exception:
        pass
    
    # Firestore backup
    db = get_firestore_client()
    if db:
        try:
            doc_ref = db.collection("conversations").document(key)
            await doc_ref.set(reference, merge=True)
        except Exception:
            pass


async def get_conversation_reference(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single conversation reference by conversation ID."""
    # Check memory first
    if conversation_id in _memory_conversations:
        return _memory_conversations[conversation_id]

    # Check file system
    try:
        file_path = _STATE_DIR / f"conv_{_sanitize_key(conversation_id)}.json"
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)
    except Exception:
        pass

    # Check Firestore
    db = get_firestore_client()
    if db:
        try:
            doc_ref = db.collection("conversations").document(conversation_id)
            doc = await doc_ref.get()
            if doc.exists:
                return doc.to_dict()
        except Exception:
            pass

    # Fallback: scan all conversations
    all_convs = await get_all_conversations()
    for conv in all_convs:
        conv_id = conv.get("conversation", {}).get("id", "")
        if conv_id == conversation_id:
            return conv

    return None


async def get_all_conversations() -> list[Dict[str, Any]]:
    """Get all active conversation references."""
    # Load from files
    conversations = []
    try:
        for file_path in _STATE_DIR.glob("conv_*.json"):
            with open(file_path, 'r') as f:
                conversations.append(json.load(f))
    except Exception:
        pass
    
    if conversations:
        return conversations
    
    # Try Firestore
    db = get_firestore_client()
    if db:
        try:
            docs = db.collection("conversations").stream()
            return [doc.to_dict() async for doc in docs]
        except Exception:
            pass
    
    return []
