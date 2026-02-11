import asyncio
import os
from dotenv import load_dotenv
from pymongo import AsyncMongoClient

load_dotenv()

async def add_user():
    mongo_url = os.getenv("MONGODB_URL")
    if not mongo_url:
        print("MONGODB_URL not found in .env")
        return

    try:
        client = AsyncMongoClient(mongo_url)
        db = client.scrum_bot
        
        # Check if Mukund exists
        existing = await db.users.find_one({"name": "Mukund"})
        if existing:
            print("User 'Mukund' already exists.")
        else:
            new_user = {
                "name": "Mukund",
                "role": "Member",
                "teams_id": "", # Empty initially, will be linked on first connect
                "email": "mukund@example.com" # Placeholder
            }
            result = await db.users.insert_one(new_user)
            print(f"User 'Mukund' added with ID: {result.inserted_id}")
            
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(add_user())
