# Teams Sprint Bot — Project Context

**Date:** 2026-03-24
**Type:** Project Context & Architecture
**Version:** 2.0.0
**Status:** Production

---

## Project Overview
A Microsoft Teams bot that automates daily standup meetings (text and voice). Uses **Gemini AI** (`gemini-3-flash-preview`, structured output) for intelligence, **FastAPI** for the backend, **MongoDB** for persistent data, **Firestore** for session state, **AWS Polly** for neural TTS, and **Azure Communication Services** for voice standups. Deployed on **GCP Cloud Run**.

### Tech Stack

| Layer | Technology | File |
|:---|:---|:---|
| Server | FastAPI + Uvicorn | `app/main.py` |
| Bot SDK | botbuilder-python (CloudAdapter, SingleTenant) | `app/bot/adapter.py` |
| AI Model | Google Gemini (`gemini-3-flash-preview`) via `google-genai` | `app/services/gemini.py` |
| Task DB | MongoDB (PyMongo, `scrum_bot` database) | `app/services/database.py` |
| Session State | Firestore + File system + Memory (three-tier fallback) | `app/services/firestore.py` |
| TTS | AWS Polly (Neural, voice: Matthew) | `app/services/polly.py` |
| Cards | Adaptive Cards 1.5 (12 card types) | `app/services/cards.py` |
| Voice Calls | Azure Communication Services (CallAutomation) | `app/voice/call_manager.py` |
| Voice Routes | ACS webhooks + browser join | `app/voice/routes.py` |
| Graph API | msgraph-sdk (meeting creation) | `app/bot/handler.py` |
| Proactive | Cloud Scheduler → `proactive.py` → Firestore refs | `app/services/proactive.py` |
| Deploy | GCP Cloud Run + Cloud Build | `cloudbuild.yaml`, `Dockerfile` |
| Runtime | Python 3.13 | `Dockerfile` |

---

## Agent Architecture

The core logic resides in `app/agent/graph.py` as a **custom state machine** (not LangGraph). Each call to `run_standup_agent(state, user_input)` advances one step and returns `(state, response_string)`.

### State Management (`app/agent/state.py`)
The `AgentState` Pydantic model persists the full meeting context:
- **Participants:** `participants[]` list + `participant_index` (advances per participant)
- **Current Context:** `current_speaker`, `current_tasks[]`
- **Coverage Tracking:** `covered_task_ids[]` — tracks which tasks have been discussed. Resets per participant.
- **Conversation:** `conversation_history[]` — `"Bot: ..."` / `"User: ..."` pairs for context-aware follow-ups. Resets per participant.
- **Output:** `responses[]` (list of `StandupResponse`), `final_summary`
- **Completion:** `is_complete` flag
- **UI State:** `last_interactive_card_id` — tracks active card for lifecycle management

Supporting models: `Task` (id, title, status, description), `Participant` (id, teams_id, name), `StandupResponse` (participant_id, response, blockers, task_updates), `TaskStatus` enum (TODO, IN_PROGRESS, BLOCKED, DONE), `UserRole` enum (MEMBER, SCRUM_MASTER).

### Workflow Logic (`run_standup_agent`)
The agent follows a cyclic process for each participant:

1. **Identify Speaker** (`identify_speaker`)
   - Selects next user by `participant_index`
   - If past last participant → `is_complete = True`

2. **Fetch Tasks** (`fetch_tasks`)
   - Queries MongoDB for `TODO`/`IN_PROGRESS`/`BLOCKED` tasks
   - Populates `current_tasks[]`

3. **Ask Question** (`ask_question`)
   - **Initial:** Uses `SCRUM_MASTER_PROMPT` with participant name + full task list
   - **Follow-up:** Filters by `covered_task_ids`, generates targeted question about remaining tasks only
   - Falls back to hardcoded question on Gemini failure

4. **Process Answer** (`process_answer`)
   - Calls `analyze_standup_response()` → extracts `mentioned_task_ids`, `task_updates` [{task_id, new_status, reason}], `blockers`
   - Updates task statuses in MongoDB via `update_task_status()`
   - Adds mentioned IDs to `covered_task_ids`
   - **Key logic:** If tasks remain uncovered → sets `last_question = None` → triggers follow-up (does NOT advance). Only advances `participant_index` when ALL tasks are covered.

5. **Summarize** (`summarize_meeting`)
   - Compiles all `StandupResponse` entries
   - Generates summary via `SUMMARY_PROMPT` (accomplishments, blockers, action items)

---

## Bot Handler (`app/bot/handler.py`, ~670 lines)

The largest file. `TeamsBot(ActivityHandler)` routes all incoming messages:

### Message Routing
1. **Dedup check** — 10s `_processed_messages` cache (Azure retry handling)
2. **Card action?** → Route button clicks (Scrum Master menu, quick replies, task form)
3. **Text command?** → "start standup" / "assign task"
4. **Pending registration?** → Process name linking
5. **Active standup?** → `_continue_standup()` → pass to agent
6. **Fallback** → `_conversational_reply()` via Gemini

### Key Features
- **Role-based greeting:** Scrum Masters get menu card, Members get standup prompt, unknowns get registration
- **Task assignment:** Natural language → Gemini JSON extraction → MongoDB create (Scrum Masters only)
- **Card lifecycle:** `last_interactive_card_id` + cleanup/replace prevents stale button clicks
- **Dual dedup:** 10s message cache + 30s greeting cache
- **Proactive messaging:** Conversation references stored for Cloud Scheduler triggers

---

## Prompts (`app/agent/prompts.py`)

| Prompt | Used By | Purpose |
|:---|:---|:---|
| `SCRUM_MASTER_PROMPT` | `ask_question()` | Initial standup question with task list |
| `SUMMARY_PROMPT` | `summarize_meeting()` | Meeting summary format |
| `TASK_ASSIGNMENT_PROMPT` | `_process_task_assignment()` | NL → JSON `{assignee_name, task_title, task_description, confidence}` |
| `MEMBER_GREETING` | `_send_greeting()` | Role-based welcome text |
| `NEW_TASK_NOTIFICATION` | `_start_standup()` | New task notification text |

---

## Database Schema

### MongoDB (`scrum_bot` database)

**users**: `{name, teams_id, role, email}` — `register_user()` only links Teams ID to existing user, does NOT create new users. `get_user_by_name()` is case-insensitive.

**tasks**: `{title, description, assignee_id (name), assigned_by, status (TODO|IN_PROGRESS|BLOCKED|DONE), created_at, notified (bool), responses[] ({text, timestamp, new_status})}` — `create_task_for_user()` checks duplicates. `update_task_status()` appends to `responses[]`.

**standups**: `{meeting_id, summary, timestamp}`

### Firestore
**scrum_states**: Serialized `AgentState` JSON, part of three-tier storage (memory → Firestore → file)
**conversations**: Conversation references for proactive messaging

---

## API Endpoints

### Main (`app/main.py`)

| Method | Path | Purpose |
|:---|:---|:---|
| `POST` | `/api/messages` | Bot Framework webhook (Azure JWT auth) |
| `GET` | `/api/speak?text=&voice_id=` | TTS via Polly (returns MP3) |
| `POST`/`GET` | `/api/scheduled-standup` | Cloud Scheduler proactive trigger |
| `GET` | `/api/conversations` | Debug: list conversation refs |
| `GET` | `/` | Service status |
| `GET` | `/health` | Health probe |
| `GET` | `/privacy` | Privacy policy HTML |
| `GET` | `/terms` | Terms of use HTML |

### Voice (`app/voice/routes.py`)

| Method | Path | Purpose |
|:---|:---|:---|
| `GET` | `/api/voice/audio/{id}.mp3` | Serve cached Polly audio |
| `GET` | `/api/voice/acs_bundle.js` | Serve ACS SDK bundle |
| `GET` | `/voice/join/{group_call_id}` | Browser join page for voice calls |
| `POST` | `/api/voice/token` | ACS communication token |
| `POST` | `/api/voice/bot-connect/{id}` | Bot joins ACS group call |
| `POST` | `/api/voice/callbacks` | ACS webhook for call events |

**Note:** `AiohttpRequestWrapper` (main.py:37-76) shims FastAPI Request → aiohttp interface for CloudAdapter.

---

## Project Structure

```
app/
├── main.py              # FastAPI server + AiohttpRequestWrapper shim
├── config.py            # pydantic-settings BaseSettings (@lru_cache singleton)
├── agent/
│   ├── graph.py         # State machine: 5 steps + run_standup_agent()
│   ├── state.py         # Pydantic: AgentState, Task, Participant, StandupResponse,
│   │                    #   StandupMode, VoiceParticipantState, VoiceStandupSession
│   └── prompts.py       # SCRUM_MASTER_PROMPT, SUMMARY_PROMPT, TASK_ASSIGNMENT_PROMPT
├── bot/
│   ├── handler.py       # TeamsBot(ActivityHandler) — routing, dedup, cards, voice trigger (~766 lines)
│   └── adapter.py       # CloudAdapter, SingleTenant auth, error handler
├── services/
│   ├── gemini.py        # generate_response(), analyze_standup_response(), transcribe_audio()
│   ├── database.py      # MongoDB CRUD: users, tasks, standups collections
│   ├── firestore.py     # Three-tier state: memory → Firestore → .state/*.json files
│   ├── polly.py         # AWS Polly neural TTS (Matthew voice, MP3)
│   ├── cards.py         # 12 Adaptive Card factory functions
│   └── proactive.py     # notify_all_teams() via stored conversation refs
└── voice/
    ├── routes.py        # ACS webhook callbacks + voice standup orchestration (~1068 lines)
    ├── call_manager.py  # ACS CallAutomationClient + session registry (~511 lines)
    └── static/          # ACS SDK bundle for browser join
```

---

## Verification & Testing

No pytest framework. Standalone verification scripts in `tests/`:

| Script | Verifies |
|:---|:---|
| `tests/verify_services.py` | Gemini API + MongoDB connectivity |
| `tests/verify_azure.py` | Azure Bot credentials (OAuth token) |
| `tests/verify_polly.py` | AWS Polly TTS (saves `verify_speech.mp3`) |
| `tests/verify_agent.py` | Agent pipeline with mocked DB + Gemini |
| `tests/verify_config.py` | Environment vars + Gemini + MongoDB ping |
| `tests/verify_proactive.py` | Proactive messaging mock test |

### Database Utilities
| Script | Purpose |
|:---|:---|
| `scripts/seed_db.py` | Clear + seed MongoDB (5 users, 10 tasks) |
| `scripts/update_db_data.py` | Migration: rename Ragavan→Raghavan, add Palak + tasks |
| `add_user.py` | Add single user |
| `check_user.py` | List all users |

---

## Deployment

- **Docker:** Multi-stage build, `python:3.13-slim`, venv at `/opt/venv`, port 8080
- **Cloud Build:** `cloudbuild.yaml` — build → push GCR → deploy Cloud Run (us-central1)
- **Cloud Scheduler:** 9:30 AM IST Mon-Fri → `GET /api/scheduled-standup`
- **Teams Manifest:** Bot ID `52551cf1-2cfd-4c7b-94fc-abcbf1f2f6fb`, scopes: personal/team/groupChat, supportsCalling: true
- **Scripts:** `deploy.bat`, `setup-scheduler.bat`, `setup-secrets.bat`
