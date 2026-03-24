# Verification Scripts

This directory contains standalone scripts to verify the configuration and connectivity of external services associated with the Teams Sprint Bot.

## Prerequisite
Ensure your `.env` file is configured in the project root.

## Usage

Run these scripts from the project root using the python from your virtual environment:

```bash
# Verify AWS Polly (TTS)
python tests/verify_polly.py

# Verify Azure Bot Authentication
python tests/verify_azure.py

# Verify Agent Logic (Mocked)
python tests/verify_agent.py

# Verify Gemini API and MongoDB Connection
python tests/verify_services.py
```
