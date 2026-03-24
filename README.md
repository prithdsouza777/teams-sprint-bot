# Teams Sprint Bot 🤖

A Microsoft Teams bot that automates daily standup meetings using Gemini AI and FastAPI.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Server | FastAPI + Uvicorn |
| Bot SDK | botbuilder-python |
| AI | Gemini 1.5 Flash |
| Database | MongoDB (Motor) |
| Session | Firestore |
| TTS | AWS Polly |

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
uvicorn app.main:app --reload
```

## Project Structure

```
app/
├── main.py           # FastAPI server
├── config.py         # Settings
├── bot/
│   ├── adapter.py    # Bot Framework
│   └── handler.py    # Message handler
├── agent/
│   ├── state.py      # State models
│   ├── prompts.py    # Prompt templates
│   └── graph.py      # Agent logic
└── services/
    ├── gemini.py     # LLM + STT
    ├── polly.py      # TTS
    ├── database.py   # MongoDB
    ├── firestore.py  # Session
    └── cards.py      # Adaptive Cards
```

## Deployment (GCP Cloud Run)

```bash
# Build and deploy
gcloud builds submit --tag gcr.io/PROJECT_ID/teams-sprint-bot
gcloud run deploy teams-sprint-bot --image gcr.io/PROJECT_ID/teams-sprint-bot --platform managed
```

## Verification

To verify your environment setup, use the scripts in the `tests/` directory:

```bash
# Verify all cloud services (Polly, Azure, Gemini, Mongo)
python tests/verify_services.py
python tests/verify_azure.py
python tests/verify_polly.py
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MICROSOFT_APP_ID` | Azure Bot ID |
| `MICROSOFT_APP_PASSWORD` | Azure Bot password |
| `GEMINI_API_KEY` | Google AI Studio key |
| `MONGODB_URL` | MongoDB connection |
| `AWS_ACCESS_KEY_ID` | AWS for Polly |

## License

MIT
