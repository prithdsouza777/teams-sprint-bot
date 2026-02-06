import boto3
from loguru import logger
from typing import Optional

from app.config import settings

# AWS Polly client
_polly_client = None


def get_polly_client():
    global _polly_client
    if _polly_client is None:
        kwargs = {"region_name": settings.AWS_REGION}
        
        # Only pass credentials if they are provided in valid format
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
            
        _polly_client = boto3.client("polly", **kwargs)
    return _polly_client


async def text_to_speech(text: str, voice_id: str = "Matthew") -> Optional[bytes]:
    """Convert text to speech using AWS Polly neural voice."""
    try:
        client = get_polly_client()
        response = client.synthesize_speech(
            Text=text,
            OutputFormat="mp3",
            VoiceId=voice_id,
            Engine="neural",
        )
        return response["AudioStream"].read()
    except Exception as e:
        logger.error(f"Polly TTS error: {e}")
        return None
