import asyncio
import sys
from loguru import logger
from unittest.mock import MagicMock, AsyncMock

# 1. Setup Service Mocks BEFORE importing agent code
# Database Mock
db_mock = MagicMock()
# Configure async functions on the mock
db_mock.get_tasks_for_user = AsyncMock()
db_mock.update_task_status = AsyncMock(return_value=True)
sys.modules["app.services.database"] = db_mock

# Gemini Mock
gemini_mock = MagicMock()
gemini_mock.generate_response = AsyncMock(return_value="What did you do yesterday?")
gemini_mock.analyze_standup_response = AsyncMock(return_value={
    "task_updates": [{"task_id": "task_abc", "new_status": "DONE"}],
    "blockers": [],
    "summary": "Fixed the API bug."
})
sys.modules["app.services.gemini"] = gemini_mock

# Config Mock
config_mock = MagicMock()
sys.modules["app.config"] = config_mock

# 2. Import Agent Logic (will use the mocks above)
from app.agent.state import AgentState, Participant, Task
from app.agent.graph import identify_speaker, fetch_tasks, process_answer

async def run_verification():
    logger.info("Starting Agent Logic Verification...")

    # Setup specific test data
    alice = Participant(id="user_123", teams_id="teams_alice", name="Alice")
    task_1 = {"_id": "task_abc", "title": "Fix API bug", "status": "TODO"}
    
    # Configure the specific return value for this test run
    # (Pre-configured mocks above are fine, but specific data here)
    db_mock.get_tasks_for_user.return_value = [task_1]

    # Initialize State
    state = AgentState(
        meeting_id="meeting_1",
        thread_id="thread_1",
        participants=[alice]
    )

    # Test: Identify Speaker
    state = await identify_speaker(state)
    assert state.current_speaker == alice, "Speaker identification failed"
    logger.success("Step 1: Identify Speaker - PASSED")

    # Test: Fetch Tasks
    state = await fetch_tasks(state)
    assert len(state.current_tasks) == 1, "Task fetching failed"
    assert state.current_tasks[0].title == "Fix API bug", "Task title mismatch"
    logger.success("Step 2: Fetch Tasks - PASSED")

    # Test: Process Answer
    user_response = "I fixed the API bug."
    state = await process_answer(state, user_response)
    
    # Verify DB update call
    db_mock.update_task_status.assert_called_with("task_abc", "DONE")
    logger.success("Step 3: Process Answer (DB Update) - PASSED")

    # Verify Response Recording
    assert len(state.responses) == 1, "Response recording failed"
    assert state.responses[0].response == user_response, "Response content mismatch"
    logger.success("Step 4: Response Recording - PASSED")

    logger.info("Verification Complete!")

if __name__ == "__main__":
    asyncio.run(run_verification())
