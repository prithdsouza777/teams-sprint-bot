from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from typing import Optional, List, Dict, Any

from app.config import settings

# MongoDB client
_client: Optional[AsyncIOMotorClient] = None


def get_database():
    global _client
    if _client is None:
        try:
            _client = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
        except Exception as e:
            logger.warning(f"MongoDB client init failed: {e}")
            return None
    return _client.scrum_bot


async def get_user_by_teams_id(teams_id: str) -> Optional[Dict[str, Any]]:
    """Find user by their Teams ID."""
    db = get_database()
    if db is None:
        return None
    try:
        return await db.users.find_one({"teams_id": teams_id})
    except Exception as e:
        logger.warning(f"MongoDB query failed: {e}")
        return None


async def get_tasks_for_user(user_id: str) -> List[Dict[str, Any]]:
    """Get active tasks for a user."""
    db = get_database()
    if db is None:
        return []
    try:
        cursor = db.tasks.find({
            "assignee_id": user_id,
            "status": {"$in": ["TODO", "IN_PROGRESS", "BLOCKED"]}
        })
        return await cursor.to_list(length=50)
    except Exception as e:
        logger.warning(f"MongoDB query failed: {e}")
        return []


async def update_task_status(task_id: str, new_status: str) -> bool:
    """Update a task's status."""
    db = get_database()
    if db is None:
        return False
    try:
        from bson import ObjectId
        
        query = {"_id": ObjectId(task_id)} if ObjectId.is_valid(task_id) else {"_id": task_id}
        
        result = await db.tasks.update_one(
            query,
            {"$set": {"status": new_status}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.warning(f"MongoDB update failed: {e}")
        return False


async def save_standup_summary(meeting_id: str, summary: Dict[str, Any]) -> None:
    """Save a completed standup summary."""
    db = get_database()
    if db is None:
        return
    try:
        await db.standups.insert_one({
            "meeting_id": meeting_id,
            **summary
        })
    except Exception as e:
        logger.warning(f"MongoDB insert failed: {e}")
