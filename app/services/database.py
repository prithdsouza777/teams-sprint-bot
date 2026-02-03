from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from typing import Optional, List, Dict, Any

from app.config import settings

# MongoDB client
_client: Optional[AsyncIOMotorClient] = None


def get_database():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGODB_URL)
    return _client.scrum_bot


async def get_user_by_teams_id(teams_id: str) -> Optional[Dict[str, Any]]:
    """Find user by their Teams ID."""
    db = get_database()
    return await db.users.find_one({"teams_id": teams_id})


async def get_tasks_for_user(user_id: str) -> List[Dict[str, Any]]:
    """Get active tasks for a user."""
    db = get_database()
    cursor = db.tasks.find({
        "assignee_id": user_id,
        "status": {"$in": ["TODO", "IN_PROGRESS", "BLOCKED"]}
    })
    return await cursor.to_list(length=50)


async def update_task_status(task_id: str, new_status: str) -> bool:
    """Update a task's status."""
    db = get_database()
    result = await db.tasks.update_one(
        {"_id": task_id},
        {"$set": {"status": new_status}}
    )
    return result.modified_count > 0


async def save_standup_summary(meeting_id: str, summary: Dict[str, Any]) -> None:
    """Save a completed standup summary."""
    db = get_database()
    await db.standups.insert_one({
        "meeting_id": meeting_id,
        **summary
    })
