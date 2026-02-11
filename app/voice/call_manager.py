"""
Azure Communication Services Call Manager.

Handles call lifecycle: create, play audio, recognize speech, and hangup.
Tracks active call sessions for state management across webhook events.
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


def _load_acs_imports():
    """Lazy-load ACS SDK to avoid import errors when ACS is not configured."""
    global _acs_imports_loaded, _CallAutomationClient
    global _MicrosoftTeamsUserIdentifier, _CallInvite, _FileSource

    if _acs_imports_loaded:
        return True
    try:
        from azure.communication.callautomation import (
            CallAutomationClient,
            CallInvite,
            FileSource,
        )
        from azure.communication.callautomation import (
            MicrosoftTeamsUserIdentifier,
        )

        _CallAutomationClient = CallAutomationClient
        _MicrosoftTeamsUserIdentifier = MicrosoftTeamsUserIdentifier
        _CallInvite = CallInvite
        _FileSource = FileSource
        _acs_imports_loaded = True
        return True
    except ImportError:
        logger.warning("azure-communication-callautomation not installed. Voice features disabled.")
        return False


# ── Active Call Sessions ──────────────────────────────────────────────
# Maps call_connection_id -> session metadata.
# This allows the webhook handler to correlate events with user context.
_active_sessions: Dict[str, Dict[str, Any]] = {}


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

    # ── Session Registry ──────────────────────────────────────────────

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

    # ── Call Actions ──────────────────────────────────────────────────

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
            logger.info(f"Call hung up: {call_connection_id}")
            return True
        except Exception as e:
            logger.error(f"hangup failed: {e}")
            self.remove_session(call_connection_id)
            return False
