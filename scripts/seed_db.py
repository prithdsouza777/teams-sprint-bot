
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.services.database import get_database
from app.config import settings
from loguru import logger

async def seed_data():
    logger.info("Connecting to MongoDB...")
    db = get_database()
    
    if db is None:
        logger.error("Failed to connect to database. Check your MONGODB_URL in .env")
        return

    logger.info("Clearing existing data...")
    await db.users.delete_many({})
    await db.tasks.delete_many({})

    # Fake users
    users = [
        {"name": "Pritham", "teams_id": "user_pritham", "role": "Scrum Master"},
        {"name": "Mukund", "teams_id": "user_mukund", "role": "Member"},
        {"name": "Ragavan", "teams_id": "user_ragavan", "role": "Member"},
        {"name": "Shawn", "teams_id": "user_shawn", "role": "Member"},
        {"name": "Joel", "teams_id": "user_joel", "role": "Member"},
    ]

    logger.info(f"Seeding {len(users)} users...")
    await db.users.insert_many(users)

    # Fake tasks - assignee_id uses display names to match participant IDs
    tasks = [
        # Pritham's tasks
        {"title": "Implement MongoDB seeding", "assignee_id": "Pritham", "status": "IN_PROGRESS", "responses": []},
        {"title": "Fix docker container crash", "assignee_id": "Pritham", "status": "TODO", "responses": []},
        
        # Mukund's tasks
        {"title": "Design new home page", "assignee_id": "Mukund", "status": "DONE", "responses": []},
        {"title": "Update CSS varibales", "assignee_id": "Mukund", "status": "IN_PROGRESS", "responses": []},

        # Ragavan's tasks
        {"title": "Write unit tests for auth", "assignee_id": "Ragavan", "status": "TODO", "responses": []},
        {"title": "Manual testing of login flow", "assignee_id": "Ragavan", "status": "BLOCKED", "responses": []},

        # Shawn's tasks
        {"title": "Create new logo assets", "assignee_id": "Shawn", "status": "DONE", "responses": []},
        {"title": "Redesign email templates", "assignee_id": "Shawn", "status": "TODO", "responses": []},

        # Joel's tasks
        {"title": "Review Q1 goals", "assignee_id": "Joel", "status": "IN_PROGRESS", "responses": []},
        {"title": "Team capacity planning", "assignee_id": "Joel", "status": "TODO", "responses": []},
    ]

    logger.info(f"Seeding {len(tasks)} tasks...")
    await db.tasks.insert_many(tasks)

    logger.success("Database seeded successfully!")
    
    # Verify
    user_count = await db.users.count_documents({})
    task_count = await db.tasks.count_documents({})
    logger.info(f"Verification: Found {user_count} users and {task_count} tasks.")

if __name__ == "__main__":
    if not settings.MONGODB_URL:
        logger.error("MONGODB_URL is not set in .env file.")
    else:
        asyncio.run(seed_data())
