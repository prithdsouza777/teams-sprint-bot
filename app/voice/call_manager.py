"""
Azure Communication Services Call Manager.

Handles call lifecycle: create, play audio, recognize speech, and hangup.
Tracks active call sessions for state management across webhook events.
Supports both 1:1 calls and group meeting joins for voice standups.
"""

from loguru import logger
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from app.config import settings

# Lazy imports – only loaded when ACS is actually configured.
_acs_imports_loaded = False
_CallAutomationClient = None
_MicrosoftTeamsUserIdentifier = None
_CallInvite = None
_FileSource = None
_TextSource = None
_RecognizeInputType = None


def _load_acs_imports():
    """Lazy-load ACS SDK to avoid import errors when ACS is not configured."""
    global _acs_imports_loaded, _CallAutomationClient
    global _MicrosoftTeamsUserIdentifier, _CallInvite, _FileSource
    global _TextSource, _RecognizeInputType

    if _acs_imports_loaded:
        return True
    try:
        from azure.communication.callautomation import (
            CallAutomationClient,
            CallInvite,
            FileSource,
            TextSource,
        )
        from azure.communication.callautomation import (
            MicrosoftTeamsUserIdentifier,
        )
        from azure.communication.callautomation import (
            RecognizeInputType,
        )

        _CallAutomationClient = CallAutomationClient
        _MicrosoftTeamsUserIdentifier = MicrosoftTeamsUserIdentifier
        _CallInvite = CallInvite
        _FileSource = FileSource
        _TextSource = TextSource
        _RecognizeInputType = RecognizeInputType
        _acs_imports_loaded = True
        return True
    except ImportError:
        logger.warning("azure-communication-callautomation not installed. Voice features disabled.")
        return False


# ── Active Call Sessions ──────────────────────────────────────────────
# Maps call_connection_id -> session metadata (for 1:1 calls).
_active_sessions: Dict[str, Dict[str, Any]] = {}

# ── Voice Standup Sessions ────────────────────────────────────────────
# Maps call_connection_id -> VoiceStandupSession (for group meeting calls).
_voice_sessions: Dict[str, Any] = {}


class CallManager:
    """Manages ACS call lifecycle and active session registry."""

    def __init__(self):
        self.client = None
        self._enabled = False

        if not settings.ACS_CONNECTION_STRING:
            logger.debug("ACS_CONNECTION_STRING not set – voice features disabled")
            return

        if not _load_acs_imports():
            return

        try:
            self.client = _CallAutomationClient.from_connection_string(
                settings.ACS_CONNECTION_STRING
            )
            self._enabled = True
            logger.info("ACS CallAutomationClient initialized")
        except Exception as e:
            logger.error(f"Failed to init ACS client: {e}")

    @property
    def enabled(self) -> bool:
        return self._enabled and self.client is not None

    # ── Session Registry (1:1 calls) ─────────────────────────────────

    def register_session(
        self, call_connection_id: str, user_id: str = "", user_name: str = ""
    ) -> None:
        """Track a new active call session."""
        _active_sessions[call_connection_id] = {
            "user_id": user_id,
            "user_name": user_name,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "silence_retries": 0,
        }
        logger.info(f"Session registered: {call_connection_id} ({user_name})")

    def get_session(self, call_connection_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session metadata for a call."""
        return _active_sessions.get(call_connection_id)

    def remove_session(self, call_connection_id: str) -> None:
        """Clean up a disconnected call session."""
        removed = _active_sessions.pop(call_connection_id, None)
        if removed:
            logger.info(f"Session removed: {call_connection_id}")

    def increment_silence_retry(self, call_connection_id: str) -> int:
        """Increment and return the silence-retry counter for a session."""
        session = _active_sessions.get(call_connection_id)
        if session:
            session["silence_retries"] = session.get("silence_retries", 0) + 1
            return session["silence_retries"]
        return 0

    def reset_silence_retry(self, call_connection_id: str) -> None:
        """Reset silence retries (called after successful recognition)."""
        session = _active_sessions.get(call_connection_id)
        if session:
            session["silence_retries"] = 0

    # ── Voice Standup Session Registry (group meetings) ──────────────

    def register_voice_session(self, call_connection_id: str, session) -> None:
        """Register a VoiceStandupSession for a group meeting call."""
        _voice_sessions[call_connection_id] = session
        logger.info(f"Voice session registered: {call_connection_id}")

    def get_voice_session(self, call_connection_id: str):
        """Retrieve the VoiceStandupSession for a call."""
        return _voice_sessions.get(call_connection_id)

    def update_voice_session(self, call_connection_id: str, session) -> None:
        """Update a VoiceStandupSession in the registry."""
        _voice_sessions[call_connection_id] = session

    def remove_voice_session(self, call_connection_id: str) -> None:
        """Clean up a voice standup session."""
        removed = _voice_sessions.pop(call_connection_id, None)
        if removed:
            logger.info(f"Voice session removed: {call_connection_id}")

    # ── Call Actions (1:1 — backward compatible) ─────────────────────

    async def create_call(
        self, teams_user_oid: str, callback_url: str
    ) -> Optional[Any]:
        """Initiate a VoIP call to a Teams user by their Entra Object ID."""
        if not self.enabled:
            logger.warning("Cannot create call – ACS not enabled")
            return None

        target = _MicrosoftTeamsUserIdentifier(user_id=teams_user_oid)
        invite = _CallInvite(target=target)

        try:
            result = self.client.create_call(invite, callback_url=callback_url)
            logger.info(f"Call initiated to {teams_user_oid}")
            return result
        except Exception as e:
            logger.error(f"create_call failed: {e}")
            return None

    async def play_audio(self, call_connection_id: str, audio_url: str) -> bool:
        """Play an audio file into the call from a public URL."""
        if not self.enabled:
            return False

        try:
            conn = self.client.get_call_connection(call_connection_id)
            source = _FileSource(url=audio_url)
            conn.play_media_to_all(source)
            logger.debug(f"Playing audio: {audio_url[:60]}...")
            return True
        except Exception as e:
            logger.error(f"play_audio failed: {e}")
            return False

    async def start_recognizing(
        self, call_connection_id: str, end_silence_timeout: int = 3
    ) -> bool:
        """Start speech recognition on the call."""
        if not self.enabled:
            return False

        try:
            conn = self.client.get_call_connection(call_connection_id)
            conn.start_recognizing_media(
                input_type="speech",
                end_silence_timeout=end_silence_timeout,
            )
            logger.debug(f"Recognition started on {call_connection_id}")
            return True
        except Exception as e:
            logger.error(f"start_recognizing failed: {e}")
            return False

    async def hangup(self, call_connection_id: str) -> bool:
        """End a call and clean up the session."""
        if not self.enabled:
            return False

        try:
            conn = self.client.get_call_connection(call_connection_id)
            conn.hang_up(is_for_everyone=True)
            self.remove_session(call_connection_id)
            self.remove_voice_session(call_connection_id)
            logger.info(f"Call hung up: {call_connection_id}")
            return True
        except Exception as e:
            logger.error(f"hangup failed: {e}")
            self.remove_session(call_connection_id)
            self.remove_voice_session(call_connection_id)
            return False

    # ── Group Meeting Actions (voice standup) ────────────────────────

    async def create_group_call_to_teams_users(
        self,
        teams_user_oids: list,
        callback_url: str,
        cognitive_services_endpoint: str = "",
    ) -> Optional[str]:
        """
        Create a group call to multiple Teams users by their Entra OIDs.

        ACS Call Automation does not support joining existing Teams meetings.
        Instead, the bot creates an ACS-managed group call and rings each
        participant directly via Teams.

        Returns the call_connection_id or None on failure.
        """
        if not self.enabled:
            logger.warning("Cannot create group call – ACS not enabled")
            return None

        if not teams_user_oids:
            logger.error("No Teams user OIDs provided for group call")
            return None

        cog_endpoint = cognitive_services_endpoint or settings.AZURE_COGNITIVE_SERVICES_ENDPOINT

        try:
            targets = [
                _MicrosoftTeamsUserIdentifier(user_id=oid)
                for oid in teams_user_oids
            ]
            result = self.client.create_call(
                target_participant=targets,
                callback_url=callback_url,
                cognitive_services_endpoint=cog_endpoint if cog_endpoint else None,
            )
            conn_id = result.call_connection_id
            logger.info(f"Group call created, conn_id={conn_id}, participants={len(teams_user_oids)}")
            return conn_id
        except Exception as e:
            logger.error(f"create_group_call_to_teams_users failed: {e}")
            return None

    async def speak_to_all(
        self,
        call_connection_id: str,
        text: str,
        voice_name: str = "en-US-NancyNeural",
        operation_context: str = "",
    ) -> bool:
        """
        Speak text into the call using ACS TextSource (built-in TTS).

        No external TTS service needed — ACS uses Cognitive Services directly.
        """
        if not self.enabled:
            return False

        try:
            conn = self.client.get_call_connection(call_connection_id)
            source = _TextSource(text=text, voice_name=voice_name)
            conn.get_call_media().play_media_to_all(
                play_source=source,
                operation_context=operation_context,
            )
            logger.debug(f"Speaking to all: {text[:60]}... (ctx={operation_context})")
            return True
        except Exception as e:
            logger.error(f"speak_to_all failed: {e}")
            return False

    async def start_recognizing_participant(
        self,
        call_connection_id: str,
        target_entra_oid: str,
        end_silence_timeout: int = 0,
        initial_silence_timeout: int = 0,
        operation_context: str = "",
    ) -> bool:
        """
        Start speech recognition targeting a specific participant.

        Per-participant targeting prevents crosstalk in group calls.
        """
        if not self.enabled:
            return False

        end_timeout = end_silence_timeout or settings.VOICE_STANDUP_SILENCE_TIMEOUT
        init_timeout = initial_silence_timeout or settings.VOICE_STANDUP_WAIT_SECONDS

        try:
            conn = self.client.get_call_connection(call_connection_id)
            target = _MicrosoftTeamsUserIdentifier(user_id=target_entra_oid)
            conn.get_call_media().start_recognizing_media(
                input_type=_RecognizeInputType.SPEECH,
                target_participant=target,
                end_silence_timeout_in_seconds=end_timeout,
                initial_silence_timeout_in_seconds=init_timeout,
                operation_context=operation_context,
            )
            logger.debug(
                f"Recognition started for {target_entra_oid[:12]}... "
                f"(ctx={operation_context})"
            )
            return True
        except Exception as e:
            logger.error(f"start_recognizing_participant failed: {e}")
            return False

    async def list_call_participants(
        self, call_connection_id: str
    ) -> list:
        """List participants currently in the call."""
        if not self.enabled:
            return []

        try:
            conn = self.client.get_call_connection(call_connection_id)
            participants = conn.list_participants()
            return list(participants) if participants else []
        except Exception as e:
            logger.error(f"list_call_participants failed: {e}")
            return []

    async def add_participant(
        self, call_connection_id: str, teams_user_oid: str
    ) -> bool:
        """Add a Teams user to an existing call."""
        if not self.enabled:
            return False

        try:
            conn = self.client.get_call_connection(call_connection_id)
            target = _MicrosoftTeamsUserIdentifier(user_id=teams_user_oid)
            invite = _CallInvite(target=target)
            conn.add_participant(invite)
            logger.info(f"Added participant {teams_user_oid} to {call_connection_id}")
            return True
        except Exception as e:
            logger.error(f"add_participant failed: {e}")
            return False
