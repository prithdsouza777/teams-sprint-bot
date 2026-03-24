from typing import Tuple
from loguru import logger

from app.agent.state import AgentState, Participant, Task, StandupResponse
from app.agent.prompts import SCRUM_MASTER_PROMPT, SUMMARY_PROMPT
from app.services.gemini import generate_response, analyze_standup_response
from app.services.database import get_tasks_for_user, update_task_status


async def identify_speaker(state: AgentState) -> AgentState:
    """Identify the next speaker in the standup."""
    if state.participant_index >= len(state.participants):
        state.is_complete = True
        state.current_speaker = None
        return state
    
    state.current_speaker = state.participants[state.participant_index]
    logger.info(f"Current speaker: {state.current_speaker.name}")
    return state


async def fetch_tasks(state: AgentState) -> AgentState:
    """Fetch tasks for the current speaker."""
    if not state.current_speaker:
        return state
    
    try:
        tasks = await get_tasks_for_user(state.current_speaker.id)
        state.current_tasks = [
            Task(id=str(t.get("_id", "")), title=t.get("title", ""), status=t.get("status", "TODO"))
            for t in tasks
        ]
        logger.info(f"Fetched {len(state.current_tasks)} tasks for {state.current_speaker.name}")
    except Exception as e:
        logger.warning(f"Could not fetch tasks: {e}")
        state.current_tasks = []
    return state


async def ask_question(state: AgentState) -> AgentState:
    """Generate a standup question for the current speaker, focusing on uncovered tasks."""
    if not state.current_speaker:
        return state
    
    # Filter to only uncovered tasks
    remaining_tasks = [t for t in state.current_tasks if t.id not in state.covered_task_ids]
    
    # Handle status as enum or string
    task_list = []
    for t in remaining_tasks:
        status = t.status.value if hasattr(t.status, 'value') else str(t.status)
        task_list.append(f"- {t.title} ({status})")
    task_list_str = "\n".join(task_list) or "No active tasks"
    
    # Check if this is a follow-up question
    is_followup = len(state.covered_task_ids) > 0
    
    if is_followup and remaining_tasks:
        # Generate targeted follow-up for specific remaining tasks
        task_names = [t.title for t in remaining_tasks]
        prompt = f"""You are an AI Scrum Master conducting a standup.

The user {state.current_speaker.name} has already provided updates on some tasks.
They still need to provide updates on these remaining tasks:
{task_list_str}

Generate a brief, friendly follow-up question asking specifically about these remaining tasks.
Keep it short and conversational."""
    else:
        # First question - ask about all tasks
        prompt = SCRUM_MASTER_PROMPT.format(
            participant_name=state.current_speaker.name,
            task_list=task_list_str
        )
    
    try:
        question = await generate_response(prompt)
        state.last_question = question or f"Hey {state.current_speaker.name}, how's your progress today?"
    except Exception as e:
        logger.warning(f"AI question generation failed: {e}")
        if is_followup and remaining_tasks:
            task_names = ", ".join([t.title for t in remaining_tasks])
            state.last_question = f"What about {task_names}?"
        else:
            state.last_question = f"Hey {state.current_speaker.name}, how's your progress today?"
    
    return state


async def process_answer(state: AgentState, user_response: str) -> AgentState:
    """Process the user's standup response and track which tasks were addressed."""
    if not state.current_speaker or not user_response:
        return state
    
    # Add to conversation history for context
    state.conversation_history.append(f"Bot: {state.last_question}")
    state.conversation_history.append(f"User: {user_response}")
    
    try:
        # Analyze response for task updates (handle status as enum or string)
        tasks_data = []
        for t in state.current_tasks:
            status = t.status.value if hasattr(t.status, 'value') else str(t.status)
            tasks_data.append({"id": t.id, "title": t.title, "status": status})
        
        analysis = await analyze_standup_response(
            user_response, 
            tasks_data,
            conversation_history=state.conversation_history
        )
        
        # Track which tasks were mentioned
        mentioned_ids = analysis.get("mentioned_task_ids", [])
        for task_id in mentioned_ids:
            if task_id not in state.covered_task_ids:
                state.covered_task_ids.append(task_id)
        
        # Apply task updates and log them - only log the specific reason, not full response
        for update in analysis.get("task_updates", []):
            task_id = update["task_id"]
            new_status = update["new_status"]
            # Use the specific reason for this task update, not the full response
            update_reason = update.get("reason", "")
            
            # Find original task for logging
            original_task = next((t for t in state.current_tasks if t.id == task_id), None)
            
            if await update_task_status(task_id, new_status, response_text=update_reason):
                if original_task:
                    logger.info(f"Updated task {task_id} to {new_status} with response")
        
        # Record the response
        response = StandupResponse(
            participant_id=state.current_speaker.id,
            response=user_response,
            blockers=analysis.get("blockers", []),
            task_updates=analysis.get("task_updates", [])
        )
        state.responses.append(response)
        
        # Check if all tasks have been addressed
        all_task_ids = [t.id for t in state.current_tasks]
        remaining_tasks = [t for t in state.current_tasks if t.id not in state.covered_task_ids]
        
        if remaining_tasks:
            # Ask about remaining tasks - don't move to next participant yet
            logger.info(f"{len(remaining_tasks)} tasks not yet addressed, will ask follow-up")
            state.last_question = None  # Will trigger ask_question to generate a new question
        else:
            # All tasks covered - move to next participant
            logger.info(f"All tasks addressed for {state.current_speaker.name}")
            state.participant_index += 1
            state.current_speaker = None
            state.current_tasks = []
            state.covered_task_ids = []  # Reset for next participant
            state.conversation_history = []
            state.last_question = None
            
    except Exception as e:
        logger.error(f"Error processing standup answer: {e}")
        # Still record basic response and move on
        state.responses.append(StandupResponse(
            participant_id=state.current_speaker.id,
            response=user_response,
            blockers=[],
            task_updates=[]
        ))
        state.participant_index += 1
        state.current_speaker = None
        state.current_tasks = []
        state.covered_task_ids = []
        state.last_question = None
    
    return state


async def summarize_meeting(state: AgentState) -> AgentState:
    """Generate meeting summary."""
    try:
        responses_text = "\n\n".join([
            f"**{state.participants[i].name if i < len(state.participants) else 'User'}**:\n{r.response}\nBlockers: {', '.join(r.blockers) or 'None'}"
            for i, r in enumerate(state.responses)
        ])
        
        prompt = SUMMARY_PROMPT.format(responses=responses_text)
        state.final_summary = await generate_response(prompt) or "Standup complete."
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        state.final_summary = "✅ Standup complete! Thanks for your updates."
    
    return state


async def run_standup_agent(state: AgentState, user_input: str) -> Tuple[AgentState, str]:
    """Main agent runner - processes one step at a time."""
    
    try:
        # If we have a pending question, process the answer
        if state.last_question and user_input:
            state = await process_answer(state, user_input)
        
        # Check if complete
        if state.is_complete:
            if not state.final_summary:
                state = await summarize_meeting(state)
            return state, state.final_summary or ""
        
        # Identify next speaker if needed
        if not state.current_speaker:
            state = await identify_speaker(state)
            
            if state.is_complete:
                state = await summarize_meeting(state)
                return state, state.final_summary or ""
        
        # Fetch tasks if needed
        if state.current_speaker and not state.current_tasks:
            state = await fetch_tasks(state)
        
        # Ask question if needed
        if state.current_speaker and not state.last_question:
            state = await ask_question(state)
            return state, state.last_question or ""
        
        return state, ""
    except Exception as e:
        logger.error(f"Agent error: {e}")
        return state, "Sorry, something went wrong. Please try again."
