from botbuilder.core import ActivityHandler, TurnContext, MessageFactory
from botbuilder.schema import Activity, ActivityTypes
from loguru import logger

from app.services.firestore import save_state, load_state
from app.services.cards import create_question_card, create_summary_card
from app.agent.state import AgentState, Participant


class TeamsBot(ActivityHandler):
    """Handles incoming Teams activities and orchestrates the standup flow."""

    async def on_message_activity(self, turn_context: TurnContext):
        text = turn_context.activity.text or ""
        user_id = turn_context.activity.from_property.id
        user_name = turn_context.activity.from_property.name or "User"
        conversation_id = turn_context.activity.conversation.id

        logger.info(f"Message from {user_name}: {text}")

        # Handle Adaptive Card quick replies
        if turn_context.activity.value:
            card_data = turn_context.activity.value
            if card_data.get("quickReply") == "on_track":
                text = "Everything is on track, no blockers."
            elif card_data.get("quickReply") == "blocked":
                text = "I'm blocked and need help."

        # 1. Load or Initialize State
        state_dict = await load_state(conversation_id)
        
        if state_dict:
            state = AgentState(**state_dict)
        else:
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

        # 2. Run LangGraph agent
        from app.agent.graph import run_standup_agent
        
        state, response_message = await run_standup_agent(state, text)

        # 3. Send response
        if response_message:
            if state.current_speaker and state.last_question:
                # Send Adaptive Card with tasks
                card = create_question_card(
                    state.current_speaker.name,
                    state.last_question,
                    [{"id": t.id, "title": t.title, "status": t.status} 
                     for t in state.current_tasks]
                )
                await turn_context.send_activity(Activity(
                    type=ActivityTypes.message,
                    attachments=[card]
                ))
            elif state.final_summary:
                # Send summary card
                card = create_summary_card(state.final_summary, [], [])
                await turn_context.send_activity(Activity(
                    type=ActivityTypes.message,
                    attachments=[card]
                ))
            else:
                await turn_context.send_activity(MessageFactory.text(response_message))

        # 4. Save State
        await save_state(conversation_id, state.model_dump())

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    MessageFactory.text("👋 Hi! I'm your AI Scrum Master. Say 'start standup' to begin!")
                )
