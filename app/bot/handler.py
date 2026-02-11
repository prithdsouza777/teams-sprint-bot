from botbuilder.core import ActivityHandler, TurnContext, MessageFactory
from botbuilder.schema import Activity, ActivityTypes, Attachment
from loguru import logger
from datetime import datetime, timedelta
import json

from app.services.firestore import save_state, load_state, save_conversation_reference, clear_state
from app.services.cards import (
    create_question_card, create_summary_card, create_audio_card,
    create_scrum_master_menu_card, create_task_assignment_prompt_card,
    create_task_assignment_confirmation_card, create_new_tasks_notification_card,
    create_completed_menu_card, create_completed_task_prompt_card,
    create_completed_question_card
)
from app.services.database import (
    get_user_by_name, get_user_by_teams_id, register_user,
    get_user_role, create_task_for_user, get_pending_assigned_tasks,
    mark_tasks_as_notified, get_all_users
)
from app.agent.state import AgentState, Participant
from app.agent.prompts import TASK_ASSIGNMENT_PROMPT
from app.services.gemini import generate_response
from app.config import settings
import urllib.parse

# Simple deduplication cache to prevent Azure retries
_processed_messages: dict[str, datetime] = {}
DEDUPE_WINDOW = timedelta(seconds=10)

# Greeting deduplication cache to prevent duplicate welcome messages
# Both on_members_added_activity and on_message_activity can fire on first contact
_greeted_conversations: dict[str, datetime] = {}
GREETING_DEDUPE_WINDOW = timedelta(seconds=30)


def _cleanup_dedup_cache() -> None:
    """Remove expired entries to prevent unbounded memory growth."""
    now = datetime.now()
    expired = [k for k, v in _processed_messages.items() if now - v > DEDUPE_WINDOW]
    for k in expired:
        del _processed_messages[k]


class TeamsBot(ActivityHandler):

    """Handles incoming Teams activities and orchestrates the standup flow."""

    async def _replace_card(self, turn_context: TurnContext, new_card: Attachment):
        """Replace the original interactive card with a completed read-only version."""
        try:
            reply_id = turn_context.activity.reply_to_id
            if reply_id:
                updated = Activity(
                    type=ActivityTypes.message,
                    id=reply_id,
                    attachments=[new_card]
                )
                await turn_context.update_activity(updated)
        except Exception as e:
            logger.debug(f"Could not update card (expected in some channels): {e}")

    async def on_message_activity(self, turn_context: TurnContext):
        try:
            text = (turn_context.activity.text or "").strip()
            user_id = turn_context.activity.from_property.id
            user_name = turn_context.activity.from_property.name or "User"
            conversation_id = turn_context.activity.conversation.id
            activity_id = turn_context.activity.id or ""

            # Deduplicate retried messages
            _cleanup_dedup_cache()
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

            # Handle Adaptive Card actions
            if turn_context.activity.value:
                card_data = turn_context.activity.value
                action = card_data.get("action")
                
                # Handle Scrum Master menu actions
                if action == "start_standup":
                    await self._replace_card(turn_context, create_completed_menu_card(user_name, "Start Standup"))
                    await self._start_standup(turn_context, conversation_id, user_id, user_name)
                    return
                elif action == "assign_task":
                    await self._replace_card(turn_context, create_completed_menu_card(user_name, "Assign Task"))
                    # Show task assignment prompt card
                    card = create_task_assignment_prompt_card()
                    await turn_context.send_activity(Activity(
                        type=ActivityTypes.message,
                        attachments=[card]
                    ))
                    return
                elif action == "submit_task_assignment":
                    await self._replace_card(turn_context, create_completed_task_prompt_card("Task submitted"))
                    # Process task assignment from card
                    task_description = card_data.get("taskDescription", "")
                    await self._process_task_assignment(turn_context, user_id, user_name, task_description)
                    return
                elif action == "cancel_assignment":
                    await self._replace_card(turn_context, create_completed_task_prompt_card("Cancelled"))
                    await turn_context.send_activity(
                        MessageFactory.text("Task assignment cancelled. What else can I help you with?")
                    )
                    return
                
                # Handle standup quick replies
                if card_data.get("quickReply") == "on_track":
                    text = "Everything is on track, no blockers."
                    await self._replace_card(turn_context, create_completed_task_prompt_card("✅ On Track"))
                elif card_data.get("quickReply") == "blocked":
                    text = "I'm blocked and need help."
                    await self._replace_card(turn_context, create_completed_task_prompt_card("🔴 Blocked"))
                elif card_data.get("userResponse"):
                    text = card_data.get("userResponse")

            # Check for standup commands
            text_lower = text.lower()
            
            if text_lower in ["start standup", "standup", "start"]:
                await self._start_standup(turn_context, conversation_id, user_id, user_name)
                return
            
            # Check for assign task command (Scrum Master only)
            if text_lower in ["assign task", "assign", "new task"]:
                await self._handle_assign_task_command(turn_context, user_id, user_name)
                return

            # Check if we have an active standup
            state_dict = await load_state(conversation_id)
            
            # Check for pending registration
            if state_dict and state_dict.get("pending_registration"):
                teams_id = state_dict.get("teams_id", user_id)
                # Extract actual name from phrases like "my name is X", "I'm X", etc.
                import re
                name_input = text.strip()
                name_patterns = [
                    r"(?i)^(?:my\s+name\s+is|i'?\s*am|i'm|call\s+me|it'?\s*s|this\s+is)\s+(.+)$",
                ]
                for pattern in name_patterns:
                    match = re.match(pattern, name_input)
                    if match:
                        name_input = match.group(1).strip().rstrip(".")
                        break
                user = await register_user(teams_id, name_input)
                if user:
                    await turn_context.send_activity(
                        MessageFactory.text(f"✅ Got it, {user.get('name')}! You're now registered. Type **start standup** to begin.")
                    )
                    # Clear pending state
                    await save_state(conversation_id, {})
                else:
                    await turn_context.send_activity(
                        MessageFactory.text(f"I couldn't link you to '{text}'. Please ensure your name matches the project roster and isn't already registered.")
                    )
                return
            
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
        # Try to identify the user
        user = await get_user_by_teams_id(user_id)
        
        if not user:
            # Try name-based lookup
            user = await get_user_by_name(user_name)
            if user:
                # Link Teams ID to existing user
                await register_user(user_id, user_name)
                logger.info(f"Linked Teams ID to user by name: {user_name}")
        
        if not user:
            # User not found - prompt for registration
            await turn_context.send_activity(
                MessageFactory.text(
                    f"👋 Hi {user_name}! I don't have you in my records yet.\n\n"
                    f"Please tell me your name as it appears in the system (e.g., 'Pritham', 'Mukund', etc.) "
                    f"so I can find your tasks."
                )
            )
            # Save pending registration state
            await save_state(conversation_id, {"pending_registration": True, "teams_id": user_id})
            return
        
        # Use the user's name from database for consistency
        display_name = user.get("name", user_name)
        
        participant = Participant(
            id=display_name,  # Use name as ID for task matching
            teams_id=user_id,
            name=display_name,
        )
        state = AgentState(
            meeting_id=conversation_id,
            thread_id=conversation_id,
            participants=[participant],
        )
        
        # Check for newly assigned tasks and notify the user
        pending_tasks = await get_pending_assigned_tasks(display_name)
        if pending_tasks:
            # Show notification card for new tasks
            notification_card = create_new_tasks_notification_card(pending_tasks)
            await turn_context.send_activity(Activity(
                type=ActivityTypes.message,
                attachments=[notification_card]
            ))
            
            # Mark these tasks as notified
            task_ids = [str(t.get("_id", "")) for t in pending_tasks]
            await mark_tasks_as_notified(task_ids)
            logger.info(f"Notified {display_name} of {len(pending_tasks)} new assigned tasks")
        
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
            audio_url = f"{settings.BASE_URL}/api/speak?text={encoded_text}"
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
            audio_url = f"{settings.BASE_URL}/api/speak?text={encoded_text}"
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
            audio_url = f"{settings.BASE_URL}/api/speak?text={encoded_text}"
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
                MessageFactory.text("👋 Hi! I'm your AI Scrum Master. Say **start standup** to begin.")
            )
            return

        user_id = turn_context.activity.from_property.id
        user_name = turn_context.activity.from_property.name or "User"
        conversation_id = turn_context.activity.conversation.id

        text_lower = text.lower()
        # Check for greeting to trigger auto-start logic
        if any(greet in text_lower for greet in ["hi", "hello", "hey", "hola"]):
             await self._send_greeting(turn_context, user_id, user_name, conversation_id)
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
                audio_url = f"{settings.BASE_URL}/api/speak?text={encoded_text}"
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

    async def _handle_assign_task_command(self, turn_context: TurnContext, user_id: str, user_name: str):
        """Handle the assign task command - only for Scrum Masters."""
        # Check user's role
        user_role = await get_user_role(user_id)
        
        if user_role != "Scrum Master":
            await turn_context.send_activity(
                MessageFactory.text(
                    "⚠️ Sorry, only **Scrum Masters** can assign tasks to team members.\n\n"
                    "If you need a task assigned, please contact your Scrum Master."
                )
            )
            return
        
        # Show task assignment prompt card
        card = create_task_assignment_prompt_card()
        await turn_context.send_activity(Activity(
            type=ActivityTypes.message,
            attachments=[card]
        ))

    async def _process_task_assignment(
        self, 
        turn_context: TurnContext, 
        user_id: str, 
        user_name: str, 
        task_description: str
    ):
        """Process a task assignment request using AI to parse natural language."""
        if not task_description.strip():
            await turn_context.send_activity(
                MessageFactory.text("Please provide a task description. For example: 'Give John the task to fix the login bug'")
            )
            return
        
        # Get assigner's name from database
        assigner = await get_user_by_teams_id(user_id)
        assigner_name = assigner.get("name", user_name) if assigner else user_name
        
        # Verify user is a Scrum Master
        user_role = assigner.get("role", "Member") if assigner else "Member"
        if user_role != "Scrum Master":
            await turn_context.send_activity(
                MessageFactory.text("⚠️ Sorry, only **Scrum Masters** can assign tasks.")
            )
            return
        
        # Get all team members for context
        all_users = await get_all_users()
        team_members = [u.get("name") for u in all_users if u.get("name")]
        
        # Use AI to parse the task assignment
        prompt = TASK_ASSIGNMENT_PROMPT.format(
            user_input=task_description,
            team_members=", ".join(team_members)
        )
        
        try:
            ai_response = await generate_response(prompt)
            
            # Parse the JSON response
            if ai_response:
                # Clean up the response - remove markdown code blocks if present
                cleaned = ai_response.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                    cleaned = cleaned.rsplit("```", 1)[0] if "```" in cleaned else cleaned
                
                parsed = json.loads(cleaned)
                logger.info(f"AI Parsed Task Assignment: {parsed}")
                
                assignee_name = parsed.get("assignee_name", "").strip()
                task_title = parsed.get("task_title", "").strip()
                task_desc = parsed.get("task_description", "").strip()
                
                if not assignee_name or not task_title:
                    await turn_context.send_activity(
                        MessageFactory.text(
                            "I couldn't understand that task assignment. Please be more specific.\n\n"
                            f"Available team members: {', '.join(team_members)}\n\n"
                            "Example: 'Give Pritham the task to fix the login bug'"
                        )
                    )
                    return
                
                # Verify assignee exists
                assignee = await get_user_by_name(assignee_name)
                if not assignee:
                    await turn_context.send_activity(
                        MessageFactory.text(
                            f"I couldn't find a team member named '{assignee_name}'.\n\n"
                            f"Available team members: {', '.join(team_members)}"
                        )
                    )
                    return
                
                # Create the task
                task, error_msg = await create_task_for_user(
                    assignee_name=assignee_name,
                    title=task_title,
                    assigned_by=assigner_name,
                    description=task_desc
                )
                
                if task:
                    # Send confirmation card
                    card = create_task_assignment_confirmation_card(
                        assignee=assignee_name,
                        task_title=task_title,
                        assigned_by=assigner_name
                    )
                    await turn_context.send_activity(Activity(
                        type=ActivityTypes.message,
                        attachments=[card]
                    ))
                else:
                    msg = error_msg if error_msg else "Failed to create the task. Please try again."
                    await turn_context.send_activity(
                        MessageFactory.text(f"❌ {msg}")
                    )
                    
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            await turn_context.send_activity(
                MessageFactory.text(
                    "I had trouble understanding that. Please try again with a clearer description.\n\n"
                    "Example: 'Assign the API documentation task to Mukund'"
                )
            )
        except Exception as e:
            logger.error(f"Task assignment error: {e}")
            await turn_context.send_activity(
                MessageFactory.text("❌ Something went wrong. Please try again.")
            )



    async def _send_greeting(self, turn_context: TurnContext, user_id: str, user_name: str, conversation_id: str):
        """Send role-based greeting."""
        # Deduplicate greetings: both on_members_added and on_message can trigger this
        now = datetime.now()
        greeting_key = f"{conversation_id}:{user_id}"
        if greeting_key in _greeted_conversations:
            if now - _greeted_conversations[greeting_key] < GREETING_DEDUPE_WINDOW:
                logger.debug(f"Skipping duplicate greeting for {user_name} in {conversation_id}")
                return
        _greeted_conversations[greeting_key] = now
        # Cleanup old greeting entries
        expired = [k for k, v in _greeted_conversations.items() if now - v > GREETING_DEDUPE_WINDOW]
        for k in expired:
            del _greeted_conversations[k]

        # Try to identify the user
        user = await get_user_by_teams_id(user_id)
        if not user:
            # Fallback to name check
            user = await get_user_by_name(user_name)
        
        if user:
            display_name = user.get("name", user_name)
            user_role = user.get("role", "Member")
            
            if user_role == "Scrum Master":
                # Scenario 2: Scrum Master
                await turn_context.send_activity(
                    MessageFactory.text(f"👋 Hi {display_name}! I'm your AI Scrum Master. Say **start standup** to begin or **assign a task** to a member.")
                )
                # Show Menu Card
                card = create_scrum_master_menu_card(display_name)
                await turn_context.send_activity(Activity(
                    type=ActivityTypes.message,
                    attachments=[card]
                ))
            else:
                # Scenario 1: Member
                await turn_context.send_activity(
                    MessageFactory.text(f"👋 Hi {display_name}! I'm your AI Scrum Master. Let's get started with your daily standup.")
                )
                await self._start_standup(turn_context, conversation_id, user_id, user_name)
        else:
            # Scenario 3: Unknown User
            await turn_context.send_activity(
                MessageFactory.text(
                    f"👋 Hi! I'm your AI Scrum Master. Please provide your name (e.g., 'My name is {user_name}')."
                )
            )
            # Save pending registration state
            await save_state(conversation_id, {"pending_registration": True, "teams_id": user_id})

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        conversation_id = turn_context.activity.conversation.id
        
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await self._send_greeting(turn_context, member.id, member.name or "User", conversation_id)

