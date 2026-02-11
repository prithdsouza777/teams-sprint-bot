"""
AWS Polly Text-to-Speech service.

Supports both plain text and SSML input.
Neural voices provide more natural-sounding speech.
"""

import boto3
import re
from loguru import logger
from typing import Optional

from app.config import settings

# AWS Polly client (singleton)
_polly_client = None


def get_polly_client():
    """Lazy-init the Polly client."""
    global _polly_client
    if _polly_client is None:
        kwargs = {"region_name": settings.AWS_REGION}

        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

        _polly_client = boto3.client("polly", **kwargs)
    return _polly_client


def _sanitize_for_ssml(text: str) -> str:
    """Escape characters that break SSML markup."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&apos;")
    return text


async def text_to_speech(
    text: str,
    voice_id: str = "Matthew",
    use_ssml: bool = False,
) -> Optional[bytes]:
    """
    Convert text to speech using AWS Polly neural voice.

    Args:
        text:      The text (or SSML) to synthesize.
        voice_id:  Polly voice ID (default: Matthew – male US English neural).
        use_ssml:  If True, wrap text in <speak> tags with a natural prosody.

    Returns:
        MP3 audio bytes, or None on failure.
    """
    if not text or not text.strip():
        return None

    try:
        client = get_polly_client()

        if use_ssml:
            safe = _sanitize_for_ssml(text)
            ssml_text = (
                '<speak>'
                '<prosody rate="medium" pitch="medium">'
                f'{safe}'
                '</prosody>'
                '</speak>'
            )
            response = client.synthesize_speech(
                Text=ssml_text,
                TextType="ssml",
                OutputFormat="mp3",
                VoiceId=voice_id,
                Engine="neural",
            )
        else:
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
