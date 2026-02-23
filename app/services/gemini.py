from typing import List, Optional

from google import genai
from google.genai import types
from loguru import logger
from pydantic import BaseModel

from app.config import settings


# ── Response schemas for Gemini structured output ──────────────────────


class TaskUpdate(BaseModel):
    task_id: str = ""
    new_status: str = ""
    reason: str = ""


class StandupAnalysis(BaseModel):
    mentioned_task_ids: List[str] = []
    task_updates: List[TaskUpdate] = []
    blockers: List[str] = []
    summary: str = ""


class TaskAssignmentParsed(BaseModel):
    assignee_name: Optional[str] = None
    task_title: Optional[str] = None
    task_description: str = ""
    confidence: str = "low"

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


async def generate_json_response(prompt: str, schema: type[BaseModel]) -> dict:
    """Generate a Gemini response constrained to a JSON schema.

    Uses ``response_mime_type="application/json"`` so the model is forced to
    return valid JSON matching *schema*.  On any failure the safe defaults
    from ``schema()`` are returned.
    """
    try:
        response = await _get_client().aio.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        import json
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Gemini JSON error: {e}")
        return schema().model_dump()


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

Return:
- "mentioned_task_ids": IDs of ALL tasks the user talked about
- "task_updates": only if status changed. reason must contain what the user said specifically about THIS task, not the entire response. new_status must be one of TODO, IN_PROGRESS, BLOCKED, DONE.
- "blockers": list of blocker descriptions
- "summary": one sentence summary of their update
"""

    try:
        return await generate_json_response(prompt, StandupAnalysis)
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return {"mentioned_task_ids": [], "task_updates": [], "blockers": [], "summary": user_response}


async def parse_task_assignment(prompt: str) -> dict:
    """Parse a task assignment request using Gemini structured output."""
    return await generate_json_response(prompt, TaskAssignmentParsed)

