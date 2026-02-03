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
    
    tasks = await get_tasks_for_user(state.current_speaker.id)
    state.current_tasks = [
        Task(id=str(t.get("_id", "")), title=t.get("title", ""), status=t.get("status", "TODO"))
        for t in tasks
    ]
    logger.info(f"Fetched {len(state.current_tasks)} tasks for {state.current_speaker.name}")
    return state


async def ask_question(state: AgentState) -> AgentState:
    """Generate a standup question for the current speaker."""
    if not state.current_speaker:
        return state
    
    task_list = "\n".join([f"- {t.title} ({t.status})" for t in state.current_tasks]) or "No active tasks"
    
    prompt = SCRUM_MASTER_PROMPT.format(
        participant_name=state.current_speaker.name,
        task_list=task_list
    )
    
    question = await generate_response(prompt)
    state.last_question = question or f"Hey {state.current_speaker.name}, how's your progress today?"
    
    return state


async def process_answer(state: AgentState, user_response: str) -> AgentState:
    """Process the user's standup response."""
    if not state.current_speaker or not user_response:
        return state
    
    # Analyze response for task updates
    analysis = await analyze_standup_response(
        user_response,
        [{"id": t.id, "title": t.title, "status": t.status.value} for t in state.current_tasks]
    )
    
    # Apply task updates
    for update in analysis.get("task_updates", []):
        await update_task_status(update["task_id"], update["new_status"])
    
    # Record the response
    response = StandupResponse(
        participant_id=state.current_speaker.id,
        response=user_response,
        blockers=analysis.get("blockers", []),
        task_updates=analysis.get("task_updates", [])
    )
    state.responses.append(response)
    
    # Move to next participant
    state.participant_index += 1
    state.current_speaker = None
    state.current_tasks = []
    state.last_question = None
    
    return state


async def summarize_meeting(state: AgentState) -> AgentState:
    """Generate meeting summary."""
    responses_text = "\n\n".join([
        f"**{state.participants[i].name if i < len(state.participants) else 'User'}**:\n{r.response}\nBlockers: {', '.join(r.blockers) or 'None'}"
        for i, r in enumerate(state.responses)
    ])
    
    prompt = SUMMARY_PROMPT.format(responses=responses_text)
    state.final_summary = await generate_response(prompt) or "Standup complete."
    
    return state


async def run_standup_agent(state: AgentState, user_input: str) -> Tuple[AgentState, str]:
    """Main agent runner - processes one step at a time."""
    
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
