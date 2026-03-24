# Verification Scripts

This directory contains standalone scripts to verify the configuration and connectivity of external services associated with the Teams Sprint Bot.

## Prerequisite
Ensure your `.env` file is configured in the project root.

## Usage

Run these scripts from the project root using the python from your virtual environment:

```bash
# Verify AWS Polly (TTS)
python -m tests.verify_polly

# Verify Azure Bot Authentication
python -m tests.verify_azure

# Verify Agent Logic (Mocked)
python -m tests.verify_agent

# Verify Gemini API and MongoDB Connection
python -m tests.verify_services

# Verify Environment Variables + Gemini + MongoDB Ping
python -m tests.verify_config

# Verify Proactive Messaging (Mocked)
python -m tests.verify_proactive
```
