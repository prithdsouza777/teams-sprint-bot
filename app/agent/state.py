from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    DONE = "DONE"


class UserRole(str, Enum):
    """User roles - cannot be modified through the bot interface."""
    MEMBER = "Member"
    SCRUM_MASTER = "Scrum Master"


class StandupMode(str, Enum):
    """How the standup is being conducted."""
    TEXT = "text"
    VOICE = "voice"


class Task(BaseModel):
    id: str
    title: str
    status: TaskStatus = TaskStatus.TODO
    description: str = ""


class Participant(BaseModel):
    id: str
    teams_id: str
    name: str
    entra_oid: str = ""


class StandupResponse(BaseModel):
    participant_id: str
    response: str
    blockers: List[str] = Field(default_factory=list)
    task_updates: List[dict] = Field(default_factory=list)


class VoiceParticipantState(BaseModel):
    """Tracks per-participant state during a voice standup call."""
    entra_oid: str
    name: str
    joined: bool = False
    completed: bool = False
    skipped: bool = False
    silence_retries: int = 0
    acs_comm_id: str = ""  # ACS Communication User ID (for browser-joined participants)


class VoiceStandupSession(BaseModel):
    """Tracks the logistics of a voice standup call (separate from AgentState)."""
    call_connection_id: str
    meeting_id: str
    join_web_url: str
    chat_conversation_id: str
    participants: List[VoiceParticipantState] = Field(default_factory=list)
    current_recognizing_oid: Optional[str] = None
    phase: str = "waiting"  # waiting | greeting | standup | summarizing | complete
    started_at: str = ""
    scrum_master_entra_oid: str = ""
    agent_state_key: str = ""


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
    covered_task_ids: List[str] = Field(default_factory=list)  # Tasks that have been addressed

    # Conversation
    last_question: Optional[str] = None
    responses: List[StandupResponse] = Field(default_factory=list)
    messages: List[str] = Field(default_factory=list)
    conversation_history: List[str] = Field(default_factory=list)  # Full context for Gemini

    # Completion
    final_summary: Optional[str] = None
    is_complete: bool = False

    # Interaction State
    last_interactive_card_id: Optional[str] = None

    # Voice mode
    mode: StandupMode = StandupMode.TEXT
    call_connection_id: Optional[str] = None
