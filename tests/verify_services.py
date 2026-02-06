import asyncio
import os
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

async def verify_gemini():
    logger.info("Verifying Gemini API...")
    try:
        import google.generativeai as genai
        from app.config import settings
        
        if not settings.GEMINI_API_KEY:
            logger.error("❌ GEMINI_API_KEY is missing in settings")
            return False
            
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = await model.generate_content_async("Say 'Gemini is working' in 3 words.")
        logger.success(f"✅ Gemini Response: {response.text.strip()}")
        return True
    except Exception as e:
        logger.error(f"❌ Gemini Verification Failed: {e}")
        return False

async def verify_mongodb():
    logger.info("Verifying MongoDB Connection...")
    try:
        from app.services.database import get_database
        db = get_database()
        # Ping the database
        await db.command("ping")
        logger.success("✅ MongoDB Connection Successful")
        return True
    except Exception as e:
        logger.error(f"❌ MongoDB Verification Failed: {e}")
        return False

async def main():
    logger.info("Starting Environment Credential Verification...")
    
    gemini_ok = await verify_gemini()
    mongo_ok = await verify_mongodb()
    
    if gemini_ok and mongo_ok:
        logger.success("\n🎉 All Core Services Verified Successfully!")
    else:
        logger.error("\n⚠️ Some services failed verification. Check .env file.")

if __name__ == "__main__":
    asyncio.run(main())
