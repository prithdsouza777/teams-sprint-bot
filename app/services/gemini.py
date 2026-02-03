import google.generativeai as genai
from loguru import logger

from app.config import settings

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

# Models
gemini_flash = genai.GenerativeModel("gemini-1.5-flash")


async def generate_response(prompt: str, context: str = "") -> str:
    """Generate a response using Gemini 1.5 Flash."""
    try:
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        response = await gemini_flash.generate_content_async(full_prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return ""


async def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/mp3") -> str:
    """Transcribe audio using Gemini's multimodal capabilities."""
    try:
        response = await gemini_flash.generate_content_async([
            {"mime_type": mime_type, "data": audio_bytes},
            "Transcribe this audio accurately. Return only the transcription."
        ])
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini STT error: {e}")
        return ""


async def analyze_standup_response(user_response: str, tasks: list) -> dict:
    """Analyze a standup response to extract task updates and blockers."""
    task_list = "\n".join([f"- {t['title']} (ID: {t['id']}, Status: {t['status']})" for t in tasks])
    
    prompt = f"""
Analyze this standup update and extract structured information.

User's Tasks:
{task_list}

User's Response:
{user_response}

Return a JSON object with:
- "task_updates": [{{ "task_id": "...", "new_status": "TODO|IN_PROGRESS|BLOCKED|DONE", "reason": "..." }}]
- "blockers": ["blocker description", ...]
- "summary": "one sentence summary of their update"

Only return the JSON, no markdown.
"""
    
    try:
        response = await gemini_flash.generate_content_async(prompt)
        import json
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return {"task_updates": [], "blockers": [], "summary": user_response}
