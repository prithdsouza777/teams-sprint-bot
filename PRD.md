# Product Requirements Document (PRD)

## Teams Sprint Bot v2.0

**Last Updated:** 2026-05-05
**Status:** In Production
**Platform:** Microsoft Teams (via Azure Bot Framework)
**Deployment:** GCP Cloud Run

---

## 1. Problem Statement

Agile teams using Microsoft Teams lack an integrated, intelligent standup automation tool. Daily standups are often skipped, poorly documented, or consume excessive meeting time. Team leads have no structured way to track task progress across sprints without switching to external tools.

## 2. Product Vision

Teams Sprint Bot automates daily standup meetings directly within Microsoft Teams — via text chat or voice calls — using AI-driven conversation to collect updates, track task completion, and surface blockers to Scrum Masters in real time.

## 3. Target Users

| Role | Description |
|:---|:---|
| **Scrum Master** | Configures standups, assigns tasks, views summaries, initiates voice standups |
| **Team Member** | Reports status on assigned tasks, raises blockers, participates in text or voice standup |

## 4. Core Features

### 4.1 Text-Based Standup (MVP)

- Bot initiates standup via proactive message or on-demand trigger
- AI agent asks each participant about their assigned tasks one by one
- Ensures full task coverage — unmentioned tasks trigger follow-up questions
- Updates task status in MongoDB based on participant responses
- Generates a summary card upon standup completion

### 4.2 Voice-Based Standup

- Scrum Master triggers voice standup from the menu card
- Bot creates an Azure Communication Services (ACS) group call
- Participants join via browser link
- Speech recognition captures responses; AWS Polly provides TTS prompts
- Same agent state machine drives the conversation; summary posted to Teams chat

### 4.3 Task Management

- Scrum Masters assign tasks via natural language input on an Adaptive Card form
- Gemini AI parses free-text into structured task data (assignee, title, priority, sprint)
- Tasks appear in assignee's next standup automatically
- Task status lifecycle: `pending` → `in_progress` → `done` / `blocked`

### 4.4 Proactive Scheduled Standups

- Cloud Scheduler triggers standup reminders at 9:30 AM IST, Monday–Friday
- Bot sends proactive messages to all registered team channels
- No manual intervention required for recurring standups

### 4.5 User Registration

- Unknown users are prompted with a registration flow
- Links a Teams identity to a pre-existing MongoDB user record
- No auto-creation — users must be pre-seeded in the database

## 5. Non-Functional Requirements

| Requirement | Target |
|:---|:---|
| Availability | 99.5% (Cloud Run auto-scaling) |
| Latency | < 3s response for text standup turns |
| Concurrency | Multiple simultaneous standups across teams |
| State durability | Three-tier fallback: Memory → Firestore → filesystem |
| Security | Azure JWT auth on webhook, GCP Secret Manager for credentials |
| Deduplication | 10s message dedup + 30s greeting dedup to handle retries |

## 6. Technical Architecture

### 6.1 Tech Stack

| Layer | Technology |
|:---|:---|
| Runtime | Python 3.13, async (FastAPI + uvicorn) |
| Bot Framework | botbuilder-python (CloudAdapter) |
| AI | Google Gemini (`gemini-3-flash-preview`, structured output) |
| Database | MongoDB (tasks, users) |
| State Store | Google Cloud Firestore (conversation state) |
| TTS | AWS Polly |
| Voice Calls | Azure Communication Services |
| Deployment | Docker → GCP Cloud Run |
| Scheduling | GCP Cloud Scheduler |
| Logging | Loguru |

### 6.2 Key Integrations

- **Microsoft Teams** — Adaptive Cards for rich UI, proactive messaging for scheduled standups
- **Azure Bot Service** — OAuth, channel registration, messaging endpoint
- **Google Gemini** — NLU for standup responses, structured output for task parsing
- **Azure Communication Services** — Group calls, speech recognition, call automation webhooks
- **AWS Polly** — Text-to-speech for voice standup prompts
- **GCP Cloud Scheduler** — Cron trigger for recurring standups

## 7. User Flows

### 7.1 Scrum Master Flow

1. Bot greets with a **Menu Card** (Start Standup, Assign Task, Voice Standup)
2. "Start Standup" → bot runs text standup for all team members
3. "Assign Task" → form card → natural language input → Gemini parses → task created
4. "Voice Standup" → ACS call created → participants join → AI-driven voice Q&A → summary

### 7.2 Team Member Flow

1. Bot greets → immediately starts standup (no menu)
2. Bot asks about each pending task sequentially
3. Member responds naturally; AI updates task status
4. Unanswered tasks trigger follow-up questions
5. Once all tasks covered → "thank you" message, standup ends

### 7.3 Registration Flow

1. Unknown user messages bot
2. Bot prompts for name selection from existing user list
3. User selects → Teams ID linked to MongoDB record
4. Future messages route through normal Scrum Master / Member flow

## 8. Success Metrics

| Metric | Definition |
|:---|:---|
| Standup completion rate | % of scheduled standups fully completed (all participants responded) |
| Task coverage | % of assigned tasks discussed per standup |
| Time saved | Avg standup duration vs. manual meeting baseline |
| Adoption | # of active teams / registered users over time |

## 9. Constraints & Assumptions

- Users must be pre-seeded in MongoDB before they can register
- Bot requires Azure Bot registration with correct messaging endpoint
- Voice standups require ACS resource provisioned in Azure
- GCP Cloud Run cold starts may add ~2s latency on first request after idle
- Single-tenant deployment (one bot instance per organization)

## 10. Future Considerations

- Sprint velocity dashboards and burndown charts
- Jira / Azure DevOps integration for bi-directional task sync
- Multi-language support (TTS + NLU)
- Automated blocker escalation to Scrum Master via priority notification
- Meeting transcript storage and searchable standup history
- Auto user provisioning from Teams directory (Microsoft Graph)

---

## Appendix: API Surface

| Method | Path | Purpose |
|:---|:---|:---|
| POST | `/api/messages` | Bot Framework webhook |
| GET | `/api/speak` | TTS audio generation |
| POST/GET | `/api/scheduled-standup` | Proactive standup trigger |
| POST | `/api/voice/token` | ACS token issuance |
| POST | `/api/voice/bot-connect/{id}` | Bot joins call |
| POST | `/api/voice/callbacks` | ACS event webhooks |
| GET | `/voice/join/{id}` | Browser join page |
| GET | `/health` | Health probe |
