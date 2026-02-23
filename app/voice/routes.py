"""
Voice Routes – ACS Webhook handler, audio file server, and voice standup orchestration.

Handles the call event loop for group meeting standups:
  CallConnected → Wait for participants → Greet → For each participant:
    Speak question → PlayCompleted → Recognize speech → Process via agent →
    Follow-up or advance → Summarize → Hang up → Post summary to chat

Also serves cached Polly audio files for backward compatibility.
"""

from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import Response
from loguru import logger
from typing import Dict, Optional
import asyncio
import hashlib
import os
import tempfile
from datetime import datetime, timezone

from app.config import settings
from app.agent.state import (
    AgentState, Participant, StandupMode,
    VoiceStandupSession, VoiceParticipantState,
)
from app.agent.prompts import (
    VOICE_GREETING, VOICE_PARTICIPANT_INTRO, VOICE_FOLLOWUP,
    VOICE_NEXT_PARTICIPANT, VOICE_SKIP_PARTICIPANT,
    VOICE_SILENCE_REPROMPT, VOICE_SUMMARY_INTRO,
)

# ── Constants ─────────────────────────────────────────────────────────
MAX_SILENCE_RETRIES = settings.VOICE_STANDUP_MAX_SILENCE_RETRIES
WAIT_SECONDS = settings.VOICE_STANDUP_WAIT_SECONDS

# ── Router ────────────────────────────────────────────────────────────
router = APIRouter(tags=["Voice"])

# ── Lazy CallManager singleton ────────────────────────────────────────
_call_manager = None


def get_call_manager():
    """Lazy-init the CallManager to avoid import-time side effects."""
    global _call_manager
    if _call_manager is None:
        from app.voice.call_manager import CallManager
        _call_manager = CallManager()
    return _call_manager


# ── In-memory audio cache (hash -> bytes) for Polly backward compat ──
_audio_cache: Dict[str, bytes] = {}
_AUDIO_DIR = os.path.join(tempfile.gettempdir(), "scrum_bot_audio")
os.makedirs(_AUDIO_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════
#  Audio file server – serves generated Polly audio to ACS (legacy)
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
        _audio_cache[audio_id] = data
        return Response(content=data, media_type="audio/mpeg")

    return Response(status_code=404)


async def generate_and_cache_audio(text: str) -> str:
    """
    Generate TTS audio via Polly, cache it, and return its public URL.
    Used for backward-compatible 1:1 calls. Group meetings use TextSource instead.
    """
    from app.services.polly import text_to_speech

    audio_id = hashlib.md5(text.encode()).hexdigest()

    if audio_id not in _audio_cache:
        audio_bytes = await text_to_speech(text)
        if not audio_bytes:
            logger.error(f"Polly TTS failed for: {text[:40]}...")
            return ""

        _audio_cache[audio_id] = audio_bytes

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
    Dispatches each event to the appropriate handler in the background.
    """
    try:
        body = await request.json()
        events = body if isinstance(body, list) else [body]

        for event in events:
            event_type = event.get("type", "")
            data = event.get("data", {})
            conn_id = data.get("callConnectionId", "")
            op_ctx = data.get("operationContext", "")

            logger.info(f"ACS event: {event_type} | conn={conn_id[:12]}... | ctx={op_ctx}")

            if event_type == "Microsoft.Communication.CallConnected":
                cm = get_call_manager()
                cm.register_session(conn_id)
                background_tasks.add_task(_on_call_connected, conn_id)

            elif event_type == "Microsoft.Communication.ParticipantsUpdated":
                background_tasks.add_task(_on_participants_updated, conn_id, data)

            elif event_type == "Microsoft.Communication.PlayCompleted":
                background_tasks.add_task(_on_play_completed, conn_id, op_ctx)

            elif event_type == "Microsoft.Communication.RecognizeCompleted":
                speech_text = (
                    data.get("recognitionResult", {}).get("text", "").strip()
                )
                background_tasks.add_task(
                    _on_recognize_completed, conn_id, speech_text, op_ctx
                )

            elif event_type == "Microsoft.Communication.RecognizeFailed":
                background_tasks.add_task(_on_recognize_failed, conn_id, op_ctx)

            elif event_type == "Microsoft.Communication.CallDisconnected":
                cm = get_call_manager()
                cm.remove_session(conn_id)
                cm.remove_voice_session(conn_id)

            elif event_type in (
                "Microsoft.Communication.AddParticipantSucceeded",
                "Microsoft.Communication.AddParticipantFailed",
            ):
                logger.info(f"Participant add result: {event_type}")

    except Exception as e:
        logger.error(f"Callback handler error: {e}")

    return {"status": "ok"}


# ══════════════════════════════════════════════════════════════════════
#  Event Handlers (run in background)
# ══════════════════════════════════════════════════════════════════════

async def _on_call_connected(conn_id: str):
    """
    Called when the bot connects to the meeting.
    Start a timer, then begin the standup after WAIT_SECONDS.
    """
    cm = get_call_manager()
    session = cm.get_voice_session(conn_id)

    if not session:
        # Fallback for 1:1 calls (no voice session registered)
        logger.info(f"No voice session for {conn_id} — using legacy 1:1 flow")
        audio_url = await generate_and_cache_audio(
            "Hello! I'm your AI Scrum Master. What would you like to do?"
        )
        if audio_url:
            await cm.play_audio(conn_id, audio_url)
        return

    # Group meeting flow: wait for participants to join
    session.phase = "waiting"
    cm.update_voice_session(conn_id, session)

    await cm.speak_to_all(
        conn_id,
        "Hello everyone! I'll start the standup in a moment. Please wait while others join.",
        operation_context="waiting",
    )

    # Background timer: after WAIT_SECONDS, begin standup
    await asyncio.sleep(WAIT_SECONDS)
    await _start_voice_standup(conn_id)


async def _on_participants_updated(conn_id: str, event_data: dict):
    """Track which participants have joined or left the call."""
    cm = get_call_manager()
    session = cm.get_voice_session(conn_id)
    if not session:
        return

    participants_list = event_data.get("participants", [])
    for p in participants_list:
        identifier = p.get("identifier", {})
        # Microsoft Teams users have a "microsoftTeamsUser" field
        teams_user = identifier.get("microsoftTeamsUser", {})
        oid = teams_user.get("userId", "")
        if not oid:
            continue

        is_in_call = p.get("isMuted") is not None  # present = in call

        for vp in session.participants:
            if vp.entra_oid == oid:
                vp.joined = is_in_call
                logger.info(f"Participant {vp.name} ({'joined' if is_in_call else 'left'})")

    cm.update_voice_session(conn_id, session)


async def _on_play_completed(conn_id: str, operation_context: str):
    """
    Route based on operation_context to determine next action after TTS completes.
    """
    cm = get_call_manager()
    session = cm.get_voice_session(conn_id)

    if not session:
        # Legacy 1:1 flow: start listening after bot finishes speaking
        await cm.start_recognizing(conn_id)
        return

    if operation_context == "waiting":
        # Waiting message played — do nothing, timer handles start
        return

    elif operation_context == "greeting":
        # Greeting done — ask the first participant
        await _ask_current_participant(conn_id)

    elif operation_context in ("question", "followup"):
        # Question/followup done — start listening to the current participant
        if session.current_recognizing_oid:
            await cm.start_recognizing_participant(
                conn_id,
                session.current_recognizing_oid,
                operation_context="recognize",
            )

    elif operation_context == "transition":
        # Transition message done — ask the next participant
        await _ask_current_participant(conn_id)

    elif operation_context == "skip":
        # Skip message done — advance to the next participant
        await _advance_to_next_participant(conn_id)

    elif operation_context == "summary":
        # Summary done — finish and hang up
        await _finish_and_hangup(conn_id)

    elif operation_context == "farewell":
        # Farewell done — hang up
        await cm.hangup(conn_id)


async def _on_recognize_completed(conn_id: str, speech_text: str, op_ctx: str):
    """Process recognized speech through the standup agent pipeline."""
    cm = get_call_manager()
    session = cm.get_voice_session(conn_id)

    if not session:
        # Legacy 1:1 flow
        cm.reset_silence_retry(conn_id)
        if not speech_text:
            await _handle_silence_legacy(conn_id)
            return
        logger.info(f"User said: {speech_text}")
        if any(w in speech_text.lower() for w in ["bye", "goodbye", "that's all", "end"]):
            audio_url = await generate_and_cache_audio("Goodbye! Have a productive day.")
            if audio_url:
                await cm.play_audio(conn_id, audio_url)
            return
        # Echo back for legacy
        audio_url = await generate_and_cache_audio(f"I heard: {speech_text}. How can I help?")
        if audio_url:
            await cm.play_audio(conn_id, audio_url)
        return

    # ── Group meeting flow ────────────────────────────────────────────
    if not speech_text:
        await _handle_silence(conn_id)
        return

    # Reset silence retries for current participant
    current_oid = session.current_recognizing_oid
    for vp in session.participants:
        if vp.entra_oid == current_oid:
            vp.silence_retries = 0
            break
    cm.update_voice_session(conn_id, session)

    logger.info(f"Participant said: {speech_text}")

    # Load agent state and run the standup agent
    from app.services.firestore import load_state, save_state
    from app.agent.graph import run_standup_agent

    state_key = session.agent_state_key
    state_dict = await load_state(state_key)
    if not state_dict:
        logger.error(f"No agent state found for key={state_key}")
        return

    state = AgentState(**state_dict)
    state, response_message = await run_standup_agent(state, speech_text)
    await save_state(state_key, state.model_dump())

    # Determine what to do next based on agent state
    if state.final_summary:
        # Standup complete — speak summary
        session.phase = "summarizing"
        cm.update_voice_session(conn_id, session)
        summary_text = VOICE_SUMMARY_INTRO + " " + state.final_summary
        await cm.speak_to_all(conn_id, summary_text, operation_context="summary")

    elif state.last_question and state.current_speaker:
        # Check if same participant (follow-up) or different (advance)
        current_participant_name = ""
        for vp in session.participants:
            if vp.entra_oid == current_oid:
                current_participant_name = vp.name
                break

        if state.current_speaker.name == current_participant_name:
            # Follow-up for the same participant
            await cm.speak_to_all(
                conn_id, state.last_question, operation_context="followup"
            )
        else:
            # Advance to next participant
            prev_name = current_participant_name
            next_name = state.current_speaker.name

            # Mark previous participant as completed
            for vp in session.participants:
                if vp.entra_oid == current_oid:
                    vp.completed = True
                    break

            # Update recognizing OID to the new participant
            for vp in session.participants:
                if vp.name == next_name:
                    session.current_recognizing_oid = vp.entra_oid
                    break

            cm.update_voice_session(conn_id, session)

            transition = VOICE_NEXT_PARTICIPANT.format(
                prev_name=prev_name, next_name=next_name
            )
            await cm.speak_to_all(conn_id, transition, operation_context="transition")

    elif state.is_complete and not state.final_summary:
        # Agent says complete but no summary yet — trigger summarize
        state, response_message = await run_standup_agent(state, "")
        await save_state(state_key, state.model_dump())

        if state.final_summary:
            session.phase = "summarizing"
            cm.update_voice_session(conn_id, session)
            summary_text = VOICE_SUMMARY_INTRO + " " + state.final_summary
            await cm.speak_to_all(conn_id, summary_text, operation_context="summary")


async def _on_recognize_failed(conn_id: str, op_ctx: str):
    """Handle recognition failure (timeout / no speech detected)."""
    cm = get_call_manager()
    session = cm.get_voice_session(conn_id)

    if not session:
        await _handle_silence_legacy(conn_id)
        return

    await _handle_silence(conn_id)


# ══════════════════════════════════════════════════════════════════════
#  Orchestration Functions
# ══════════════════════════════════════════════════════════════════════

async def _start_voice_standup(conn_id: str):
    """Begin the voice standup after the waiting period."""
    cm = get_call_manager()
    session = cm.get_voice_session(conn_id)
    if not session:
        logger.error(f"No voice session to start standup for {conn_id}")
        return

    # Filter to only joined participants
    joined = [vp for vp in session.participants if vp.joined]
    if not joined:
        await cm.speak_to_all(
            conn_id,
            "No one has joined the call yet. Ending the standup.",
            operation_context="farewell",
        )
        return

    # Build AgentState with joined participants
    from app.services.firestore import save_state
    from app.services.database import get_tasks_for_user

    participants = []
    for vp in joined:
        participants.append(
            Participant(
                id=vp.name,
                teams_id="",
                name=vp.name,
                entra_oid=vp.entra_oid,
            )
        )

    state_key = f"voice_standup_{conn_id}"
    state = AgentState(
        meeting_id=session.meeting_id,
        thread_id=session.chat_conversation_id,
        participants=participants,
        mode=StandupMode.VOICE,
        call_connection_id=conn_id,
    )
    await save_state(state_key, state.model_dump())

    session.agent_state_key = state_key
    session.phase = "greeting"
    cm.update_voice_session(conn_id, session)

    # Speak greeting
    participant_names = ", ".join(vp.name for vp in joined)
    greeting = (
        VOICE_GREETING + f" Today we have {participant_names} on the call."
    )
    await cm.speak_to_all(conn_id, greeting, operation_context="greeting")


async def _ask_current_participant(conn_id: str):
    """Ask the current participant their standup question via the agent."""
    cm = get_call_manager()
    session = cm.get_voice_session(conn_id)
    if not session:
        return

    from app.services.firestore import load_state, save_state
    from app.agent.graph import run_standup_agent

    state_key = session.agent_state_key
    state_dict = await load_state(state_key)
    if not state_dict:
        logger.error(f"No agent state for {state_key}")
        return

    state = AgentState(**state_dict)

    # Run the agent to get the next question
    state, response_message = await run_standup_agent(state, "")
    await save_state(state_key, state.model_dump())

    if state.is_complete and state.final_summary:
        # All done
        session.phase = "summarizing"
        cm.update_voice_session(conn_id, session)
        summary_text = VOICE_SUMMARY_INTRO + " " + state.final_summary
        await cm.speak_to_all(conn_id, summary_text, operation_context="summary")
        return

    if state.current_speaker and state.last_question:
        # Set up recognition target
        speaker_name = state.current_speaker.name
        for vp in session.participants:
            if vp.name == speaker_name:
                session.current_recognizing_oid = vp.entra_oid
                break

        session.phase = "standup"
        cm.update_voice_session(conn_id, session)

        # Speak the question
        await cm.speak_to_all(
            conn_id, state.last_question, operation_context="question"
        )
    else:
        # No more questions — summarize
        await _trigger_summary(conn_id)


async def _advance_to_next_participant(conn_id: str):
    """Check if standup is complete; if not, move to the next participant."""
    cm = get_call_manager()
    session = cm.get_voice_session(conn_id)
    if not session:
        return

    from app.services.firestore import load_state
    state_key = session.agent_state_key
    state_dict = await load_state(state_key)
    if not state_dict:
        return

    state = AgentState(**state_dict)

    if state.is_complete:
        await _trigger_summary(conn_id)
    else:
        await _ask_current_participant(conn_id)


async def _trigger_summary(conn_id: str):
    """Force the agent to generate a summary and speak it."""
    cm = get_call_manager()
    session = cm.get_voice_session(conn_id)
    if not session:
        return

    from app.services.firestore import load_state, save_state
    from app.agent.graph import run_standup_agent

    state_key = session.agent_state_key
    state_dict = await load_state(state_key)
    if not state_dict:
        return

    state = AgentState(**state_dict)
    state.is_complete = True

    # Run agent one more time to produce summary
    state, response_message = await run_standup_agent(state, "")
    await save_state(state_key, state.model_dump())

    session.phase = "summarizing"
    cm.update_voice_session(conn_id, session)

    summary_text = state.final_summary or "The standup is complete."
    full_text = VOICE_SUMMARY_INTRO + " " + summary_text
    await cm.speak_to_all(conn_id, full_text, operation_context="summary")


async def _finish_and_hangup(conn_id: str):
    """Save results, post summary to chat, and hang up."""
    cm = get_call_manager()
    session = cm.get_voice_session(conn_id)

    if session:
        session.phase = "complete"
        cm.update_voice_session(conn_id, session)

        # Post summary back to the original Teams chat
        try:
            await _post_summary_to_chat(conn_id)
        except Exception as e:
            logger.error(f"Failed to post summary to chat: {e}")

    # Say goodbye and hang up
    await cm.speak_to_all(
        conn_id,
        "Thanks everyone! The standup summary has been posted to the chat. Goodbye!",
        operation_context="farewell",
    )


async def _post_summary_to_chat(conn_id: str):
    """Post the voice standup summary as an Adaptive Card to the original Teams chat."""
    cm = get_call_manager()
    session = cm.get_voice_session(conn_id)
    if not session:
        return

    from app.services.firestore import load_state, get_conversation_reference
    from app.bot.adapter import bot_adapter, bot_handler
    from app.services.cards import create_voice_summary_card
    from botbuilder.core import TurnContext
    from botbuilder.schema import Activity, ActivityTypes

    state_key = session.agent_state_key
    state_dict = await load_state(state_key)
    summary = state_dict.get("final_summary", "Standup complete.") if state_dict else "Standup complete."

    attended = [vp.name for vp in session.participants if vp.completed or vp.joined]
    absent = [vp.name for vp in session.participants if not vp.joined]

    card = create_voice_summary_card(summary, attended, absent)

    # Retrieve the conversation reference for the original chat
    chat_conv_id = session.chat_conversation_id
    conv_ref = await get_conversation_reference(chat_conv_id)
    if not conv_ref:
        logger.warning(f"No conversation reference for {chat_conv_id} — cannot post summary")
        return

    async def send_summary(turn_context: TurnContext):
        await turn_context.send_activity(
            Activity(
                type=ActivityTypes.message,
                attachments=[card],
            )
        )

    try:
        await bot_adapter.continue_conversation(
            conv_ref, send_summary, settings.MICROSOFT_APP_ID
        )
        logger.info(f"Voice standup summary posted to chat {chat_conv_id}")
    except Exception as e:
        logger.error(f"Failed to send summary via proactive message: {e}")


# ══════════════════════════════════════════════════════════════════════
#  Silence Handling
# ══════════════════════════════════════════════════════════════════════

async def _handle_silence(conn_id: str):
    """Handle silence during a group voice standup."""
    cm = get_call_manager()
    session = cm.get_voice_session(conn_id)
    if not session:
        return

    current_oid = session.current_recognizing_oid
    current_vp = None
    for vp in session.participants:
        if vp.entra_oid == current_oid:
            current_vp = vp
            break

    if not current_vp:
        return

    current_vp.silence_retries += 1
    cm.update_voice_session(conn_id, session)

    if current_vp.silence_retries >= MAX_SILENCE_RETRIES:
        # Skip this participant
        current_vp.skipped = True
        cm.update_voice_session(conn_id, session)
        skip_msg = VOICE_SKIP_PARTICIPANT.format(name=current_vp.name)
        await cm.speak_to_all(conn_id, skip_msg, operation_context="skip")
    else:
        # Re-prompt
        reprompt = VOICE_SILENCE_REPROMPT.format(name=current_vp.name)
        await cm.speak_to_all(conn_id, reprompt, operation_context="question")


async def _handle_silence_legacy(conn_id: str):
    """Handle silence for legacy 1:1 calls."""
    cm = get_call_manager()
    retries = cm.increment_silence_retry(conn_id)

    if retries >= MAX_SILENCE_RETRIES:
        audio_url = await generate_and_cache_audio(
            "I haven't heard anything. Ending the call. You can message me anytime!"
        )
        if audio_url:
            await cm.play_audio(conn_id, audio_url)
    else:
        audio_url = await generate_and_cache_audio(
            "I didn't catch that. Could you repeat?"
        )
        if audio_url:
            await cm.play_audio(conn_id, audio_url)


# ══════════════════════════════════════════════════════════════════════
#  Utility: Get conversation reference from Firestore
# ══════════════════════════════════════════════════════════════════════

async def _get_conversation_ref_for_chat(chat_conversation_id: str):
    """Retrieve a stored conversation reference for proactive messaging."""
    from app.services.firestore import get_all_conversations

    conversations = await get_all_conversations()
    for conv in conversations:
        conv_id = conv.get("conversation", {}).get("id", "")
        if conv_id == chat_conversation_id:
            return conv
    return None
