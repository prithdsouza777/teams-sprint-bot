import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Load env vars for local script run
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")
if not MONGODB_URL:
    print("Error: MONGODB_URL not found in environment")
    exit(1)

async def update_data():
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client.scrum_bot
    
    # 1. Correct "Ragavan" to "Raghavan"
    print("Checking for user 'Ragavan'...")
    ragavan = await db.users.find_one({"name": {"$regex": "^Ragavan$", "$options": "i"}})
    if ragavan:
        old_id = ragavan["name"]
        new_name = "Raghavan"
        print(f"Found {old_id}. Updating to {new_name}...")
        
        # Update user name
        await db.users.update_one({"_id": ragavan["_id"]}, {"$set": {"name": new_name}})
        
        # Update tasks assigned to them
        task_update = await db.tasks.update_many({"assignee_id": old_id}, {"$set": {"assignee_id": new_name}})
        print(f"Updated {task_update.modified_count} tasks for {new_name}.")
    else:
        # Check if already updated
        raghavan = await db.users.find_one({"name": {"$regex": "^Raghavan$", "$options": "i"}})
        if raghavan:
            print("User 'Raghavan' already exists correctly.")
        else:
            print("Warning: Neither 'Ragavan' nor 'Raghavan' found in users collection.")

    # 2. Add user "Palak"
    print("Checking for user 'Palak'...")
    palak = await db.users.find_one({"name": {"$regex": "^Palak$", "$options": "i"}})
    if not palak:
        print("Adding user 'Palak'...")
        palak_user = {
            "name": "Palak",
            "role": "Member",
            "teams_id": None  # Will be linked on registration
        }
        await db.users.insert_one(palak_user)
        print("User 'Palak' added successfully.")
    else:
        print("User 'Palak' already exists.")

    # 3. Add 3 tasks for Palak
    print("Checking tasks for Palak...")
    palak_tasks_count = await db.tasks.count_documents({"assignee_id": "Palak"})
    if palak_tasks_count < 3:
        new_tasks = [
            {
                "title": f"Task {palak_tasks_count + 1} for Palak",
                "description": "Initial task assigned by admin.",
                "assignee_id": "Palak",
                "assigned_by": "Admin",
                "status": "TODO",
                "notified": False,
                "created_at": None, # Will be set below
                "responses": []
            } for i in range(3 - palak_tasks_count)
        ]
        
        from datetime import datetime, timezone
        for t in new_tasks:
            t["created_at"] = datetime.now(timezone.utc)
            await db.tasks.insert_one(t)
        print(f"Added {len(new_tasks)} tasks for Palak.")
    else:
        print(f"Palak already has {palak_tasks_count} tasks.")

    print("Data updates complete.")
    client.close()

if __name__ == "__main__":
    asyncio.run(update_data())
