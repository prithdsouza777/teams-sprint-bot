# Teams Sprint Bot

A Microsoft Teams bot that automates daily standup meetings using Gemini AI, FastAPI, and Azure Communication Services for voice standups.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Server | FastAPI + Uvicorn |
| Bot SDK | botbuilder-python |
| AI | Gemini 3 Flash Preview (structured output) |
| Database | MongoDB (Motor/PyMongo) |
| Session | Firestore (three-tier fallback) |
| TTS | AWS Polly (Neural, Matthew voice) |
| Voice Calls | Azure Communication Services |
| Cards | Adaptive Cards 1.5 |
| Deploy | GCP Cloud Run + Cloud Build |
| Runtime | Python 3.13 |

## Quick Start

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Setup environment
copy .env.example .env
# Fill in your credentials

# Run locally
uvicorn app.main:app --reload --port 8000
```

## Project Structure

```
app/
├── main.py              # FastAPI server + AiohttpRequestWrapper shim
├── config.py            # pydantic-settings BaseSettings
├── bot/
│   ├── adapter.py       # Bot Framework CloudAdapter
│   └── handler.py       # Message handler + voice standup triggers
├── agent/
│   ├── state.py         # Pydantic models (AgentState, VoiceStandupSession)
│   ├── prompts.py       # Prompt templates
│   └── graph.py         # Standup state machine
├── services/
│   ├── gemini.py        # Gemini AI (text, structured JSON, audio transcription)
│   ├── polly.py         # AWS Polly neural TTS
│   ├── database.py      # MongoDB CRUD (users, tasks, standups)
│   ├── firestore.py     # Three-tier state: memory -> Firestore -> file
│   ├── cards.py         # 12 Adaptive Card factory functions
│   └── proactive.py     # Cloud Scheduler proactive messaging
└── voice/
    ├── routes.py        # ACS webhook callbacks + voice standup orchestration
    ├── call_manager.py  # ACS CallAutomationClient + session registry
    └── static/          # ACS SDK bundle for browser join
```

## Deployment (GCP Cloud Run)

```bash
# Build and deploy
gcloud builds submit --tag gcr.io/PROJECT_ID/teams-sprint-bot
gcloud run deploy teams-sprint-bot --image gcr.io/PROJECT_ID/teams-sprint-bot --platform managed
```

## Verification

Standalone verification scripts (no test framework):

```bash
python -m tests.verify_services    # Gemini + MongoDB connectivity
python -m tests.verify_azure       # Azure Bot credentials (OAuth token)
python -m tests.verify_polly       # AWS Polly TTS (saves verify_speech.mp3)
python -m tests.verify_agent       # Agent pipeline with mocked DB + Gemini
python -m tests.verify_config      # Env vars + Gemini + MongoDB ping
python -m tests.verify_proactive   # Proactive messaging mock test
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MICROSOFT_APP_ID` | Azure Bot ID |
| `MICROSOFT_APP_PASSWORD` | Azure Bot password |
| `GEMINI_API_KEY` | Google AI Studio key |
| `MONGODB_URL` | MongoDB connection string |
| `AWS_ACCESS_KEY_ID` | AWS for Polly |
| `AWS_SECRET_ACCESS_KEY` | AWS for Polly |
| `ACS_CONNECTION_STRING` | Azure Communication Services |
| `ACS_CALLBACK_URL` | ACS webhook callback URL |
| `AZURE_COGNITIVE_SERVICES_ENDPOINT` | Speech recognition for voice calls |

## License

MIT
