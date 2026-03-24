# Teams Sprint Bot Project

## Overview

Teams Sprint Bot is a standup meeting assistant built using Gemini AI and FastAPI.
It facilitates standup meetings (text and voice), tracks state, and summarizes discussions.

---

## Local Setup

### 1. Create an Azure Bot
Create an Azure Bot through the Azure Cloud Console.

---

### 2. Get Gemini API Credentials
Log in to Google AI Studio and obtain:
- Gemini API key
- Project ID

Warning: The API key may not have credits. Coordinate with the team if needed.

---

### 3. Configure Environment Variables
Create a password and update the Azure environment variables.

Verify credentials:

```bash
python -m tests.verify_azure
```

---

### 4. Start MongoDB with Docker

Install Docker, then run:

```bash
docker run -p 27017:27017 --name scrumai-mongo -d mongo:latest
```

To view your local database:
- Install MongoDB Compass
- Connect to: `localhost:27017`

For subsequent starts:

```bash
docker start scrumai-mongo
```

---

### 5. Setup ngrok

- Create an ngrok account
- Install ngrok
- Run the server using the provided uvicorn command
- Open a new terminal (do not close the server terminal)
- Run:

```bash
ngrok http 8000
```

---

### 6. Configure Azure Messaging Endpoint

In Azure Cloud Console:
- Go to Bot -> Settings -> Configuration
- Set the Messaging Endpoint to:

```
https://<your-ngrok-url>/api/messages
```

---

### 7. Test the Bot

Use the Azure Testing window to test the bot.

---

## MongoDB Setup

Create a database:

```
scrum_bot
```

Create a collection:

```
users
```

Insert a test document:

```json
{
  "name": "YourTestName"
}
```

---

## Application Flow

Main logic for handling messages lives in:

```
app/bot/handler.py
```

### Flow:

1. Save turn context locally and attempt Firestore save
2. If Quick Reply cards are used, populate user text manually
3. If user text contains `"start standup"`, call `start_standup`
4. Load user state (standup active or not)
5. If in standup -> continue standup flow
6. Otherwise -> respond conversationally

### Voice Standup Flow:

1. Scrum Master clicks "Voice Standup" from the menu card
2. Bot creates an ACS group call via `call_manager.py`
3. Participants join via a browser link or Teams
4. ACS webhooks (`/api/voice/callbacks`) drive the call state machine:
   greeting -> standup questions -> speech recognition -> processing -> summary
5. Voice summary card sent back to Teams chat

---

## Agent Logic

Behavior is determined by the `AgentState` object (supports `TEXT` and `VOICE` modes).

Gemini is called through:

- `ask_question` — generate standup questions with task context
- `process_answer` / `analyze_standup_response` — extract task updates, blockers, mentioned tasks
- `summarize_meeting` — generate meeting summary
- `_process_task_assignment` — parse natural language into structured task JSON

Context is stored in MongoDB.

---

## Services Folder

### services/gemini.py
- Implements lazy-loaded Gemini client
- Uses `gemini-3-flash-preview` model with structured JSON output
- Supports text generation, standup analysis (JSON schema), and audio transcription

### services/database.py
- Handles MongoDB interactions and state storage

### services/polly.py
- Handles neural speech synthesis (Matthew voice, MP3)

### services/cards.py
- 12 Adaptive Card factory functions (question, summary, menu, assignment, voice summary, meeting join, etc.)

### services/proactive.py
- Proactive messaging via stored Firestore conversation references
- Triggered by Cloud Scheduler at 9:30 AM IST Mon-Fri

---

## Voice Module (`app/voice/`)

### voice/routes.py
- ACS webhook callbacks for call events (CallConnected, PlayCompleted, RecognizeCompleted, etc.)
- Voice standup orchestration: greeting -> per-participant Q&A -> summary
- Serves cached Polly audio files

### voice/call_manager.py
- Lazy-loads ACS CallAutomationClient
- Registry for active call sessions and group voice standup sessions
- Methods for play audio, recognize speech, hang up calls

---

## Tech Stack

| Component | Technology |
|------------|------------|
| Server | FastAPI + Uvicorn |
| Bot SDK | botbuilder-python |
| AI | Gemini 3 Flash Preview (structured output) |
| Database | MongoDB (PyMongo) |
| Session State | Firestore (three-tier fallback) |
| TTS | AWS Polly (Neural, Matthew voice) |
| Voice Calls | Azure Communication Services |
| Cards | Adaptive Cards 1.5 (12 card types) |
| Graph API | msgraph-sdk (meeting creation) |
| Deploy | GCP Cloud Run + Cloud Build |
| Runtime | Python 3.13 |
