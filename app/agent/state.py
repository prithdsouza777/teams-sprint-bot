from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    DONE = "DONE"


class Task(BaseModel):
    id: str
    title: str
    status: TaskStatus = TaskStatus.TODO
    description: str = ""


class Participant(BaseModel):
    id: str
    teams_id: str
    name: str


class StandupResponse(BaseModel):
    participant_id: str
    response: str
    blockers: List[str] = Field(default_factory=list)
    task_updates: List[dict] = Field(default_factory=list)


class AgentState(BaseModel):
    """State for the standup agent."""
    # Meeting context
    meeting_id: str
    thread_id: str
    
    # Participants
    participants: List[Participant] = Field(default_factory=list)
    participant_index: int = 0
    current_speaker: Optional[Participant] = None
    
    # Tasks
    current_tasks: List[Task] = Field(default_factory=list)
    
    # Conversation
    last_question: Optional[str] = None
    responses: List[StandupResponse] = Field(default_factory=list)
    messages: List[str] = Field(default_factory=list)
    
    # Completion
    final_summary: Optional[str] = None
    is_complete: bool = False
