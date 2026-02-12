# AI Scrum Bot Project

## Overview

AI Scrum Bot is a standup meeting assistant built using Gemini AI and FastAPI.  
It facilitates standup meetings, tracks state, and summarizes discussions.

---

## Local Setup

### 1. Create an Azure Bot
Create an Azure Bot through the Azure Cloud Console.

---

### 2. Get Gemini API Credentials
Log in to Google AI Studio and obtain:
- Gemini API key
- Project ID

⚠️ Note: The API key may not have credits. Coordinate with the team if needed.

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
- Go to Bot → Settings → Configuration
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
5. If in standup → continue standup flow
6. Otherwise → respond conversationally

---

## Agent Logic

Behavior is determined by the `AGENT_STATE` object.

Gemini is only called through:

- `summarize_meeting`
- `ask_question`

Context is stored in MongoDB.

---

## Services Folder

### services/gemini.py
- Implements lazy-loaded Gemini client
- Uses singleton-style `_get_client_`
- Initializes Gemini 1.5 Flash model only when required

### services/database.py
- Handles MongoDB interactions and state storage

### services/polly.py
- Handles speech synthesis functionality

---

## Tech Stack

| Component | Technology |
|------------|------------|
| Server | FastAPI + Uvicorn |
| Bot SDK | botbuilder-python |
| AI | Gemini 1.5 Flash |
| Database | MongoDB (Motor) |
| Secondary Storage | Firestore |
| Speech | Polly |