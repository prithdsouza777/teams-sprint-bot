from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Server
    PORT: int = 8000
    ENV: str = "development"

    # Microsoft Bot
    MICROSOFT_APP_ID: str = ""
    MICROSOFT_APP_PASSWORD: str = ""
    MICROSOFT_TENANT_ID: str = ""

    # Google / Gemini
    GOOGLE_PROJECT_ID: str = ""
    GEMINI_API_KEY: str = ""

    # MongoDB
    MONGODB_URL: str = ""

    # AWS
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"

    # Application
    BASE_URL: str = ""  # e.g. https://scrum-bot-....run.app

    # Azure Communication Services
    ACS_CONNECTION_STRING: str = ""
    ACS_CALLBACK_URL: str = ""

    # Azure Cognitive Services (for speech recognition in ACS calls)
    AZURE_COGNITIVE_SERVICES_ENDPOINT: str = ""

    # Voice Standup Settings
    VOICE_STANDUP_WAIT_SECONDS: int = 30
    VOICE_STANDUP_SILENCE_TIMEOUT: int = 3
    VOICE_STANDUP_MAX_SILENCE_RETRIES: int = 2


    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
