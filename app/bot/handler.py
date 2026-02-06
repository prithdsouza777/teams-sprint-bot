from botbuilder.core import ActivityHandler, TurnContext, MessageFactory
from botbuilder.schema import Activity, ActivityTypes
from loguru import logger
from datetime import datetime, timedelta

from app.services.firestore import save_state, load_state, save_conversation_reference
from app.services.cards import create_question_card, create_summary_card, create_audio_card
from app.agent.state import AgentState, Participant
from app.services.gemini import generate_response
import urllib.parse

# Simple deduplication cache to prevent Azure retries
_processed_messages: dict[str, datetime] = {}
DEDUPE_WINDOW = timedelta(seconds=10)

# TODO: Move to config
BASE_URL = "https://scrum-bot-536066708327.us-central1.run.app"


class TeamsBot(ActivityHandler):

    """Handles incoming Teams activities and orchestrates the standup flow."""

    async def on_message_activity(self, turn_context: TurnContext):
        try:
            text = (turn_context.activity.text or "").strip()
            user_id = turn_context.activity.from_property.id
            user_name = turn_context.activity.from_property.name or "User"
            conversation_id = turn_context.activity.conversation.id
            activity_id = turn_context.activity.id or ""

            # Deduplicate retried messages
            message_key = f"{conversation_id}:{activity_id}:{text[:50]}"
            now = datetime.now()
            if message_key in _processed_messages:
                if now - _processed_messages[message_key] < DEDUPE_WINDOW:
                    logger.debug(f"Ignoring duplicate message: {message_key}")
                    return
            _processed_messages[message_key] = now
            
            # Cleanup old entries
            cutoff = now - DEDUPE_WINDOW * 6
            _processed_messages.clear()  # Simple: clear all periodically

            logger.info(f"Message from {user_name}: {text}")


            # Capture conversation reference for proactive messaging
            try:
                conversation_reference = TurnContext.get_conversation_reference(turn_context.activity)
                await save_conversation_reference(conversation_reference.as_dict())
            except Exception as e:
                logger.warning(f"Could not save conversation reference: {e}")

            # Handle Adaptive Card quick replies
            if turn_context.activity.value:
                card_data = turn_context.activity.value
                if card_data.get("quickReply") == "on_track":
                    text = "Everything is on track, no blockers."
                elif card_data.get("quickReply") == "blocked":
                    text = "I'm blocked and need help."
                elif card_data.get("userResponse"):
                    text = card_data.get("userResponse")

            # Check for standup commands
            text_lower = text.lower()
            
            if text_lower in ["start standup", "standup", "start"]:
                await self._start_standup(turn_context, conversation_id, user_id, user_name)
                return

            # Check if we have an active standup
            state_dict = await load_state(conversation_id)
            
            if state_dict and state_dict.get("last_question"):
                await self._continue_standup(turn_context, conversation_id, text, state_dict)
                return

            # No active standup - use conversational AI
            await self._conversational_reply(turn_context, text)
            
        except Exception as e:
            logger.error(f"Error in message handler: {e}")
            await turn_context.send_activity(
                MessageFactory.text("Sorry, something went wrong. Please try again.")
            )

    async def _start_standup(self, turn_context: TurnContext, conversation_id: str, user_id: str, user_name: str):
        """Start a new standup session."""
        participant = Participant(
            id="user_123",
            teams_id=user_id,
            name=user_name,
        )
        state = AgentState(
            meeting_id=conversation_id,
            thread_id=conversation_id,
            participants=[participant],
        )
        
        from app.agent.graph import run_standup_agent
        state, response_message = await run_standup_agent(state, "")
        
        # Save state for follow-up messages
        await save_state(conversation_id, state.model_dump())
        logger.info(f"Standup started, state saved for {conversation_id}")
        
        # Send the standup card
        if state.current_speaker and state.last_question:
            card = create_question_card(
                state.current_speaker.name,
                state.last_question,
                [{"id": t.id, "title": t.title, "status": t.status.value if hasattr(t.status, 'value') else str(t.status)} 
                 for t in state.current_tasks]
            )
            
            # Generate audio card
            encoded_text = urllib.parse.quote(state.last_question)
            audio_url = f"{BASE_URL}/api/speak?text={encoded_text}"
            audio_card = create_audio_card(state.last_question, audio_url)

            await turn_context.send_activity(Activity(
                type=ActivityTypes.message,
                attachments=[card, audio_card]
            ))
        else:
            await turn_context.send_activity(MessageFactory.text(response_message or "Standup started!"))

    async def _continue_standup(self, turn_context: TurnContext, conversation_id: str, text: str, state_dict: dict):
        """Continue an active standup session."""
        logger.info(f"Continuing standup for {conversation_id}, user said: {text}")
        state = AgentState(**state_dict)
        
        from app.agent.graph import run_standup_agent
        state, response_message = await run_standup_agent(state, text)
        
        # Save updated state
        await save_state(conversation_id, state.model_dump())
        logger.info(f"Standup state updated for {conversation_id}, is_complete={state.is_complete}")
        
        # Send appropriate response
        if state.final_summary:
            card = create_summary_card(state.final_summary, [], [])
            
            # Generate audio card for summary
            encoded_text = urllib.parse.quote("Standup meeting complete. Here is the summary.")
            audio_url = f"{BASE_URL}/api/speak?text={encoded_text}"
            audio_card = create_audio_card("Daily Standup Summary", audio_url)
            
            await turn_context.send_activity(Activity(
                type=ActivityTypes.message,
                attachments=[card, audio_card]
            ))
            # Clear state to prevent duplicate summaries on retry
            from app.services.firestore import clear_state
            await clear_state(conversation_id)
            logger.info(f"Standup completed and state cleared for {conversation_id}")

        elif state.current_speaker and state.last_question:
            # Next participant's turn
            card = create_question_card(
                state.current_speaker.name,
                state.last_question,
                [{"id": t.id, "title": t.title, "status": t.status.value if hasattr(t.status, 'value') else str(t.status)} 
                 for t in state.current_tasks]
            )
            
            # Generate audio card
            encoded_text = urllib.parse.quote(state.last_question)
            audio_url = f"{BASE_URL}/api/speak?text={encoded_text}"
            audio_card = create_audio_card(state.last_question, audio_url)
            
            await turn_context.send_activity(Activity(
                type=ActivityTypes.message,
                attachments=[card, audio_card]
            ))
        else:
            await turn_context.send_activity(
                MessageFactory.text("✅ Thanks for the update! Standup complete.")
            )

    async def _conversational_reply(self, turn_context: TurnContext, text: str):
        """Handle general conversation with AI."""
        if not text:
            await turn_context.send_activity(
                MessageFactory.text("👋 Hi! I'm your AI Scrum Master. Say **start standup** to begin your daily standup!")
            )
            return
            
        try:
            prompt = f"""You are a helpful AI Scrum Master assistant. The user said: "{text}"
            
Respond helpfully and conversationally. If they seem to want to start a standup, 
remind them to say "start standup".

Keep your response brief and friendly."""

            ai_response = await generate_response(prompt)
            if ai_response:
                # Generate audio card for conversational response
                encoded_text = urllib.parse.quote(ai_response)
                audio_url = f"{BASE_URL}/api/speak?text={encoded_text}"
                audio_card = create_audio_card(ai_response, audio_url)
                
                await turn_context.send_activity(Activity(
                    type=ActivityTypes.message,
                    text=ai_response,
                    attachments=[audio_card]
                ))
            else:
                await turn_context.send_activity(
                    MessageFactory.text("👋 Hi! I'm your AI Scrum Master. Say **start standup** to begin your daily standup!")
                )
        except Exception as e:
            logger.error(f"AI response failed: {e}")
            await turn_context.send_activity(
                MessageFactory.text("👋 Hi! I'm your AI Scrum Master. Say **start standup** to begin your daily standup!")
            )


    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    MessageFactory.text("👋 Hi! I'm your AI Scrum Master. Say **start standup** to begin!")
                )
