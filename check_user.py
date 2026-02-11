import asyncio
import os
from dotenv import load_dotenv
from pymongo import AsyncMongoClient

load_dotenv()

async def check_user():
    mongo_url = os.getenv("MONGODB_URL")
    if not mongo_url:
        print("MONGODB_URL not found in .env")
        return

    try:
        client = AsyncMongoClient(mongo_url)
        db = client.scrum_bot
        
        # List all users to verify DB content
        users = await db.users.find({}).to_list(length=100)
        print(f"Total users found: {len(users)}")
        for u in users:
            print(f"- {u.get('name')} (Teams ID: {u.get('teams_id')}) (Role: {u.get('role')})")
            
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(check_user())
