from google import genai
from google.genai import types
from loguru import logger

from app.config import settings

# Model to use
MODEL = "gemini-3-flash-preview"

# Lazy-initialised client (avoids crash when GEMINI_API_KEY is unset)
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


async def generate_response(prompt: str, context: str = "") -> str:
    """Generate a response using Gemini."""
    try:
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        response = await _get_client().aio.models.generate_content(
            model=MODEL,
            contents=full_prompt
        )
        return response.text
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return ""


async def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/mp3") -> str:
    """Transcribe audio using Gemini's multimodal capabilities."""
    try:
        response = await _get_client().aio.models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                "Transcribe this audio accurately. Return only the transcription."
            ]
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini STT error: {e}")
        return ""


async def analyze_standup_response(user_response: str, tasks: list, conversation_history: list = None) -> dict:
    """Analyze a standup response to extract task updates and identify which tasks were mentioned."""
    task_list = "\n".join([f"- {t['title']} (ID: {t['id']}, Status: {t['status']})" for t in tasks])
    
    # Include conversation history for context
    history_text = ""
    if conversation_history:
        history_text = "\n\nPrevious conversation:\n" + "\n".join(conversation_history[-5:])  # Last 5 messages
    
    prompt = f"""Analyze this standup update and extract structured information.

User's Assigned Tasks:
{task_list}
{history_text}

User's Latest Response:
{user_response}

IMPORTANT: Identify which tasks the user mentioned or provided updates for, even if they didn't change status.

Return a JSON object with:
- "mentioned_task_ids": ["task_id1", "task_id2", ...] - IDs of ALL tasks the user talked about
- "task_updates": [{{"task_id": "...", "new_status": "TODO|IN_PROGRESS|BLOCKED|DONE", "reason": "user's specific quote about this task"}}] - only if status changed. IMPORTANT: reason must contain what the user said specifically about THIS task, not the entire response.
- "blockers": ["blocker description", ...]
- "summary": "one sentence summary of their update"

Only return the JSON, no markdown.
"""
    
    try:
        response = await _get_client().aio.models.generate_content(
            model=MODEL,
            contents=prompt
        )
        # Clean up response text
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        
        import json
        return json.loads(cleaned_text)
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return {"mentioned_task_ids": [], "task_updates": [], "blockers": [], "summary": user_response}

