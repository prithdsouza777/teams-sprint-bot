"""
Voice Routes – ACS Webhook handler and audio file server.

Handles the call event loop:
  CallConnected → Greet → PlayCompleted → Listen → RecognizeCompleted → Process → Play → ...

All routes are "silent" (not included in the main app router) until integration.
"""

from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import Response
from loguru import logger
from typing import Dict
import hashlib
import os
import tempfile

from app.config import settings
from app.voice.call_manager import CallManager
from app.services.polly import text_to_speech

# ── Constants ─────────────────────────────────────────────────────────
MAX_SILENCE_RETRIES = 2  # How many times to re-prompt on silence before hanging up.

# ── Router & Manager ─────────────────────────────────────────────────
router = APIRouter(tags=["Voice"])
call_manager = CallManager()

# ── In-memory audio cache (hash → bytes) ─────────────────────────────
# Avoids calling Polly twice for the same sentence.
_audio_cache: Dict[str, bytes] = {}
_AUDIO_DIR = os.path.join(tempfile.gettempdir(), "scrum_bot_audio")
os.makedirs(_AUDIO_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════
#  Audio file server – serves generated Polly audio to ACS
# ══════════════════════════════════════════════════════════════════════

@router.get("/api/voice/audio/{audio_id}.mp3")
async def serve_audio(audio_id: str):
    """Serve a cached Polly audio file by its hash ID."""
    if audio_id in _audio_cache:
        return Response(content=_audio_cache[audio_id], media_type="audio/mpeg")

    # Fallback: check disk
    path = os.path.join(_AUDIO_DIR, f"{audio_id}.mp3")
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
        _audio_cache[audio_id] = data  # warm cache
        return Response(content=data, media_type="audio/mpeg")

    return Response(status_code=404)


async def generate_and_cache_audio(text: str) -> str:
    """
    Generate TTS audio via Polly, cache it, and return its public URL.

    Returns a URL like:  {ACS_CALLBACK_URL}/api/voice/audio/{hash}.mp3
    """
    audio_id = hashlib.md5(text.encode()).hexdigest()

    if audio_id not in _audio_cache:
        audio_bytes = await text_to_speech(text)
        if not audio_bytes:
            logger.error(f"Polly TTS failed for: {text[:40]}...")
            return ""

        _audio_cache[audio_id] = audio_bytes

        # Also persist to disk so it survives memory pressure
        path = os.path.join(_AUDIO_DIR, f"{audio_id}.mp3")
        with open(path, "wb") as f:
            f.write(audio_bytes)

    base = settings.ACS_CALLBACK_URL.rstrip("/")
    return f"{base}/api/voice/audio/{audio_id}.mp3"


# ══════════════════════════════════════════════════════════════════════
#  ACS Webhook – Call Automation event handler
# ══════════════════════════════════════════════════════════════════════

@router.post("/api/voice/callbacks")
async def handle_acs_callback(request: Request, background_tasks: BackgroundTasks):
    """
    Receives CloudEvents from Azure Communication Services.
    Dispatches each event to the appropriate handler in the background
    to avoid blocking the 200 OK response.
    """
    try:
        body = await request.json()
        events = body if isinstance(body, list) else [body]

        for event in events:
            event_type = event.get("type", "")
            data = event.get("data", {})
            conn_id = data.get("callConnectionId", "")

            logger.info(f"ACS event: {event_type} | conn={conn_id[:12]}...")

            if event_type == "Microsoft.Communication.CallConnected":
                call_manager.register_session(conn_id)
                background_tasks.add_task(_on_call_connected, conn_id)

            elif event_type == "Microsoft.Communication.PlayCompleted":
                background_tasks.add_task(_on_play_completed, conn_id)

            elif event_type == "Microsoft.Communication.RecognizeCompleted":
                speech_text = (
                    data.get("recognitionResult", {}).get("text", "").strip()
                )
                background_tasks.add_task(_on_recognize_completed, conn_id, speech_text)

            elif event_type == "Microsoft.Communication.RecognizeFailed":
                background_tasks.add_task(_on_recognize_failed, conn_id)

            elif event_type == "Microsoft.Communication.CallDisconnected":
                call_manager.remove_session(conn_id)

    except Exception as e:
        logger.error(f"Callback handler error: {e}")

    return {"status": "ok"}


# ══════════════════════════════════════════════════════════════════════
#  Event Handlers (run in background)
# ══════════════════════════════════════════════════════════════════════

async def _on_call_connected(conn_id: str):
    """Greet the user when the call is established."""
    await _speak(conn_id, "Hello! I'm your AI Scrum Master. What would you like to do?")


async def _on_play_completed(conn_id: str):
    """After bot finishes speaking, start listening."""
    await call_manager.start_recognizing(conn_id)


async def _on_recognize_completed(conn_id: str, user_text: str):
    """Process recognized speech through the bot brain."""
    if not user_text:
        await _handle_silence(conn_id)
        return

    call_manager.reset_silence_retry(conn_id)
    logger.info(f"User said: {user_text}")

    # ── Brain Integration Point ──────────────────────────────────
    # TODO: Replace placeholder with GraphAgent call:
    #   from app.agent.graph import run_standup_agent
    #   response_text = await run_standup_agent(state, user_text)
    #
    # For now, use simple keyword matching as a placeholder.
    response_text = _placeholder_brain(user_text)
    # ─────────────────────────────────────────────────────────────

    # Check for goodbye intent
    if any(word in user_text.lower() for word in ["bye", "goodbye", "that's all", "end"]):
        await _speak(conn_id, "Goodbye! Have a productive day.")
        # Hangup after the farewell plays (handled via PlayCompleted → skip recognize)
        # For now, just hang up directly:
        # await call_manager.hangup(conn_id)
        return

    await _speak(conn_id, response_text)


async def _on_recognize_failed(conn_id: str):
    """Handle recognition failure (timeout / no speech detected)."""
    await _handle_silence(conn_id)


async def _handle_silence(conn_id: str):
    """Re-prompt up to MAX_SILENCE_RETRIES, then hang up gracefully."""
    retries = call_manager.increment_silence_retry(conn_id)

    if retries >= MAX_SILENCE_RETRIES:
        await _speak(conn_id, "I haven't heard anything. Ending the call. You can message me anytime!")
        # await call_manager.hangup(conn_id)
    else:
        await _speak(conn_id, "I didn't catch that. Could you repeat?")


# ══════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════

async def _speak(conn_id: str, text: str):
    """Generate audio and play it into the call."""
    audio_url = await generate_and_cache_audio(text)
    if not audio_url:
        logger.error("Audio generation failed – cannot speak")
        return

    success = await call_manager.play_audio(conn_id, audio_url)
    if not success:
        # Fallback: log only (ACS might not be connected in silent mode)
        logger.info(f"[VOICE-SIM] Bot says: {text}")


def _placeholder_brain(user_text: str) -> str:
    """
    Placeholder NLU logic. Will be replaced by GraphAgent integration.
    Kept simple to demonstrate the voice loop structure.
    """
    text_lower = user_text.lower()

    if "standup" in text_lower or "start" in text_lower:
        return "Let's start your daily standup. What did you work on yesterday?"
    elif "yesterday" in text_lower:
        return "Thanks. What's your plan for today?"
    elif "today" in text_lower:
        return "Got it. Do you have any blockers?"
    elif "no" in text_lower and "blocker" in text_lower:
        return "Great, no blockers! Your standup is complete. Anything else?"
    elif "task" in text_lower or "assign" in text_lower:
        return "Task management is available. Please use the text chat for assigning tasks."
    else:
        return f"I heard: {user_text}. How can I help further?"
