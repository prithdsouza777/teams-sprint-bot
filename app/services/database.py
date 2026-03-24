from pymongo import AsyncMongoClient
from loguru import logger
from typing import Optional, List, Dict, Any, Tuple
from app.config import settings
from datetime import datetime, timezone

# MongoDB client
_client: Optional[AsyncMongoClient] = None


def get_database():
    global _client
    if _client is None:
        try:
            _client = AsyncMongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
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


async def update_task_status(task_id: str, new_status: str, response_text: str = None) -> bool:
    """Update a task's status and optionally log the response."""
    db = get_database()
    if db is None:
        return False
    try:
        from bson import ObjectId
        
        query = {"_id": ObjectId(task_id)} if ObjectId.is_valid(task_id) else {"_id": task_id}
        
        update_ops = {"$set": {"status": new_status}}
        if response_text:
            update_ops["$push"] = {
                "responses": {
                    "text": response_text,
                    "timestamp": datetime.now(timezone.utc),
                    "new_status": new_status
                }
            }
        
        result = await db.tasks.update_one(query, update_ops)
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


async def get_user_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Find user by display name (case-insensitive)."""
    db = get_database()
    if db is None:
        return None
    try:
        import re as _re
        # Clean and escape input to prevent regex injection
        clean_name = _re.escape(name.strip())
        # Case-insensitive exact match
        return await db.users.find_one({"name": {"$regex": f"^{clean_name}$", "$options": "i"}})
    except Exception as e:
        logger.warning(f"MongoDB query failed: {e}")
        return None


async def register_user(teams_id: str, name: str) -> Optional[Dict[str, Any]]:
    """Register a new user or link Teams ID to existing user."""
    db = get_database()
    if db is None:
        return None
    try:
        # Try to find existing user by name
        existing = await get_user_by_name(name)
        if existing:
            # Update Teams ID (may change between channels/conversations)
            await db.users.update_one(
                {"_id": existing["_id"]},
                {"$set": {"teams_id": teams_id}}
            )
            logger.info(f"Linked Teams ID to existing user: {name}")
            return await db.users.find_one({"_id": existing["_id"]})
        else:
            # Create a new user record automatically
            new_user = {
                "name": name,
                "teams_id": teams_id,
                "role": "Member",
                "created_at": datetime.now(timezone.utc)
            }
            result = await db.users.insert_one(new_user)
            logger.info(f"Automatically created new user: {name}")
            return await db.users.find_one({"_id": result.inserted_id})
    except Exception as e:
        logger.warning(f"MongoDB register failed: {e}")
        return None


async def get_user_role(teams_id: str) -> str:
    """Get user's role from database. Role cannot be modified through the bot."""
    user = await get_user_by_teams_id(teams_id)
    if user:
        return user.get("role", "Member")
    return "Member"


async def create_task_for_user(
    assignee_name: str, 
    title: str, 
    assigned_by: str,
    description: str = ""
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Create a new TODO task for a user. Only Scrum Masters should call this.
    Returns: (task_dict, error_message)
    """
    db = get_database()
    if db is None:
        return None, "Database connection failed"
    try:
        # Verify assignee exists
        assignee = await get_user_by_name(assignee_name)
        if not assignee:
            logger.warning(f"Cannot assign task - user not found: {assignee_name}")
            return None, f"I couldn't find a user named '{assignee_name}'. Please check the name and try again."
        
        # Check for duplicate task (same title, same assignee, status TODO)
        duplicate = await db.tasks.find_one({
            "assignee_id": assignee_name,
            "title": title,
            "status": "TODO"
        })
        if duplicate:
            return None, f"Task '{title}' already exists for {assignee_name}."

        task = {
            "title": title,
            "description": description,
            "assignee_id": assignee_name,
            "assigned_by": assigned_by,
            "status": "TODO",
            "created_at": datetime.now(timezone.utc),
            "notified": False,  # Track if user has been notified
            "responses": []
        }
        
        result = await db.tasks.insert_one(task)
        logger.info(f"Task created: '{title}' assigned to {assignee_name} by {assigned_by}")
        new_task = await db.tasks.find_one({"_id": result.inserted_id})
        return new_task, None
    except Exception as e:
        logger.warning(f"MongoDB task creation failed: {e}")
        return None, f"Database error: {str(e)}"


async def get_pending_assigned_tasks(user_name: str) -> List[Dict[str, Any]]:
    """Get tasks assigned to user that haven't been notified yet."""
    db = get_database()
    if db is None:
        return []
    try:
        cursor = db.tasks.find({
            "assignee_id": user_name,
            "notified": False,
            "status": "TODO"
        })
        return await cursor.to_list(length=50)
    except Exception as e:
        logger.warning(f"MongoDB query failed: {e}")
        return []


async def mark_tasks_as_notified(task_ids: List[str]) -> bool:
    """Mark tasks as notified so they don't show up again."""
    db = get_database()
    if db is None:
        return False
    try:
        from bson import ObjectId
        
        object_ids = []
        for task_id in task_ids:
            if ObjectId.is_valid(task_id):
                object_ids.append(ObjectId(task_id))
            else:
                object_ids.append(task_id)
        
        result = await db.tasks.update_many(
            {"_id": {"$in": object_ids}},
            {"$set": {"notified": True}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.warning(f"MongoDB update failed: {e}")
        return False


async def get_all_users() -> List[Dict[str, Any]]:
    """Get all registered users (for task assignment dropdown)."""
    db = get_database()
    if db is None:
        return []
    try:
        cursor = db.users.find({})
        return await cursor.to_list(length=100)
    except Exception as e:
        logger.warning(f"MongoDB query failed: {e}")
        return []


async def update_user_entra_oid(teams_id: str, entra_oid: str) -> bool:
    """Store an Entra Object ID on a user document (used for ACS voice calls)."""
    db = get_database()
    if db is None:
        return False
    try:
        result = await db.users.update_one(
            {"teams_id": teams_id},
            {"$set": {"entra_oid": entra_oid}},
        )
        if result.modified_count == 0:
            # Fallback: try matching by name-based _id
            result = await db.users.update_one(
                {"entra_oid": {"$exists": False}},
                {"$set": {"entra_oid": entra_oid}},
            )
        return result.modified_count > 0
    except Exception as e:
        logger.warning(f"MongoDB update_user_entra_oid failed: {e}")
        return False


async def get_user_entra_oid(teams_id: str) -> Optional[str]:
    """Return the cached Entra Object ID for a user, or None."""
    user = await get_user_by_teams_id(teams_id)
    if user:
        return user.get("entra_oid")
    return None


async def get_users_with_entra_oids() -> List[Dict[str, Any]]:
    """Return all users that have an entra_oid field set."""
    db = get_database()
    if db is None:
        return []
    try:
        cursor = db.users.find({"entra_oid": {"$ne": ""}})
        return await cursor.to_list(length=100)
    except Exception as e:
        logger.warning(f"MongoDB query failed: {e}")
        return []


