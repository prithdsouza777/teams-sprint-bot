"""
Verification script for voice meeting functionality.

Tests:
1. Graph SDK + ACS SDK imports
2. New state model creation (VoiceStandupSession, VoiceParticipantState)
3. Voice prompt existence and validity
4. Graph client initialization (optional, skipped without credentials)
5. ACS client initialization (optional, skipped without connection string)
6. CallManager new method availability

Usage:
    python -m tests.verify_voice_meeting
    python -m tests.verify_voice_meeting --dry-run  # Skip API calls
"""

import asyncio
import sys

from loguru import logger


async def verify():
    dry_run = "--dry-run" in sys.argv
    passed = 0
    failed = 0
    skipped = 0

    def _pass(msg):
        nonlocal passed
        passed += 1
        logger.success(f"  PASS: {msg}")

    def _fail(msg):
        nonlocal failed
        failed += 1
        logger.error(f"  FAIL: {msg}")

    def _skip(msg):
        nonlocal skipped
        skipped += 1
        logger.info(f"  SKIP: {msg}")

    logger.info("=" * 60)
    logger.info("Voice Meeting Verification")
    logger.info("=" * 60)

    # ── Step 1: SDK Imports ──────────────────────────────────────────
    logger.info("\nStep 1: SDK Imports")

    try:
        from azure.identity import ClientSecretCredential
        _pass("azure-identity (ClientSecretCredential)")
    except ImportError as e:
        _fail(f"azure-identity: {e}")

    try:
        from msgraph import GraphServiceClient
        _pass("msgraph-sdk (GraphServiceClient)")
    except ImportError as e:
        _fail(f"msgraph-sdk: {e}")

    try:
        from azure.communication.callautomation import (
            CallAutomationClient,
            TextSource,
            FileSource,
            MicrosoftTeamsUserIdentifier,
        )
        _pass("azure-communication-callautomation (core classes)")
    except ImportError as e:
        _fail(f"azure-communication-callautomation: {e}")

    try:
        from azure.communication.callautomation import RecognizeInputType
        _pass("RecognizeInputType enum")
    except ImportError:
        _skip("RecognizeInputType not available (string fallback will be used)")

    # ── Step 2: State Models ─────────────────────────────────────────
    logger.info("\nStep 2: State Models")

    try:
        from app.agent.state import (
            VoiceStandupSession,
            VoiceParticipantState,
            StandupMode,
            Participant,
            AgentState,
        )

        session = VoiceStandupSession(
            call_connection_id="test-conn-id",
            meeting_id="test-meeting-id",
            join_web_url="https://teams.microsoft.com/l/meetup-join/test",
            chat_conversation_id="test-conv-id",
        )
        assert session.phase == "waiting"
        assert session.participants == []
        _pass("VoiceStandupSession creation")

        vp = VoiceParticipantState(entra_oid="test-oid", name="Test User")
        assert vp.joined is False
        assert vp.skipped is False
        assert vp.silence_retries == 0
        _pass("VoiceParticipantState creation")

        assert StandupMode.TEXT == "text"
        assert StandupMode.VOICE == "voice"
        _pass("StandupMode enum")

        p = Participant(id="1", teams_id="t1", name="Test", entra_oid="oid-123")
        assert p.entra_oid == "oid-123"
        _pass("Participant.entra_oid field")

        state = AgentState(
            meeting_id="m1",
            thread_id="t1",
            mode=StandupMode.VOICE,
            call_connection_id="conn-1",
        )
        assert state.mode == StandupMode.VOICE
        assert state.call_connection_id == "conn-1"
        _pass("AgentState voice mode fields")

    except Exception as e:
        _fail(f"State models: {e}")

    # ── Step 3: Voice Prompts ────────────────────────────────────────
    logger.info("\nStep 3: Voice Prompts")

    try:
        from app.agent.prompts import (
            VOICE_GREETING,
            VOICE_PARTICIPANT_INTRO,
            VOICE_FOLLOWUP,
            VOICE_NEXT_PARTICIPANT,
            VOICE_SKIP_PARTICIPANT,
            VOICE_SILENCE_REPROMPT,
            VOICE_SUMMARY_INTRO,
            VOICE_STANDUP_QUESTION_PROMPT,
            VOICE_SUMMARY_PROMPT,
        )

        assert len(VOICE_GREETING) > 10
        assert "{name}" in VOICE_PARTICIPANT_INTRO
        assert "{tasks}" in VOICE_FOLLOWUP
        assert "{prev_name}" in VOICE_NEXT_PARTICIPANT
        assert "{name}" in VOICE_SKIP_PARTICIPANT
        assert "{name}" in VOICE_SILENCE_REPROMPT
        assert len(VOICE_SUMMARY_INTRO) > 5
        assert "{participant_name}" in VOICE_STANDUP_QUESTION_PROMPT
        assert "{responses}" in VOICE_SUMMARY_PROMPT
        _pass("All voice prompts present and valid")

    except ImportError as e:
        _fail(f"Voice prompts import: {e}")
    except AssertionError as e:
        _fail(f"Voice prompt validation: {e}")

    # ── Step 4: Graph Client ─────────────────────────────────────────
    logger.info("\nStep 4: Graph Client")

    if dry_run:
        _skip("Graph client (dry-run mode)")
    else:
        try:
            from app.services.graph import _get_graph_client
            client = _get_graph_client()
            if client:
                _pass("Graph client initialized")
            else:
                _skip("Graph client not configured (missing credentials)")
        except Exception as e:
            _skip(f"Graph client: {e}")

    # ── Step 5: ACS Client ───────────────────────────────────────────
    logger.info("\nStep 5: ACS Client")

    if dry_run:
        _skip("ACS client (dry-run mode)")
    else:
        try:
            from app.voice.call_manager import CallManager
            cm = CallManager()
            if cm.enabled:
                _pass("ACS CallManager enabled")
            else:
                _skip("ACS CallManager not configured (missing connection string)")
        except Exception as e:
            _skip(f"ACS client: {e}")

    # ── Step 6: CallManager Methods ──────────────────────────────────
    logger.info("\nStep 6: CallManager Methods")

    try:
        from app.voice.call_manager import CallManager
        cm = CallManager()

        methods = [
            "join_meeting",
            "speak_to_all",
            "start_recognizing_participant",
            "list_call_participants",
            "add_participant",
            "register_voice_session",
            "get_voice_session",
            "update_voice_session",
            "remove_voice_session",
        ]

        for method in methods:
            assert hasattr(cm, method), f"Missing method: {method}"

        _pass(f"All {len(methods)} new CallManager methods present")

    except Exception as e:
        _fail(f"CallManager methods: {e}")

    # ── Step 7: Cards ────────────────────────────────────────────────
    logger.info("\nStep 7: Cards")

    try:
        from app.services.cards import (
            create_meeting_join_card,
            create_voice_summary_card,
        )

        card1 = create_meeting_join_card(
            meeting_url="https://teams.microsoft.com/l/meetup-join/test",
            subject="Daily Standup",
            participant_names=["Alice", "Bob"],
        )
        assert card1.content_type == "application/vnd.microsoft.card.adaptive"
        _pass("create_meeting_join_card")

        card2 = create_voice_summary_card(
            summary="Test summary",
            participants_attended=["Alice"],
            participants_absent=["Bob"],
        )
        assert card2.content_type == "application/vnd.microsoft.card.adaptive"
        _pass("create_voice_summary_card")

    except Exception as e:
        _fail(f"Cards: {e}")

    # ── Step 8: Database Functions ───────────────────────────────────
    logger.info("\nStep 8: Database Functions")

    try:
        from app.services.database import (
            update_user_entra_oid,
            get_user_entra_oid,
            get_users_with_entra_oids,
        )
        _pass("Entra OID database functions importable")
    except ImportError as e:
        _fail(f"Database functions: {e}")

    # ── Step 9: Voice Routes ─────────────────────────────────────────
    logger.info("\nStep 9: Voice Routes")

    try:
        from app.voice.routes import router, get_call_manager
        routes = [r.path for r in router.routes]
        assert "/api/voice/callbacks" in routes or any("callbacks" in r for r in routes)
        _pass("Voice webhook route registered")
    except Exception as e:
        _fail(f"Voice routes: {e}")

    # ── Summary ──────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    logger.info("=" * 60)

    if failed > 0:
        logger.error("Some checks failed. See above for details.")
        sys.exit(1)
    else:
        logger.success("All checks passed!")


if __name__ == "__main__":
    asyncio.run(verify())
