from botbuilder.core import TurnContext
from botbuilder.schema import Activity, ActivityTypes
from loguru import logger

from app.bot.adapter import bot_adapter
from app.config import settings
from app.services.firestore import get_all_conversations

async def notify_all_teams():
    """Fail-safe notification to all stored conversations."""
    conversations = await get_all_conversations()
    logger.info(f"Checking {len(conversations)} conversations for proactive messaging.")

    for ref in conversations:
        try:
            # reference is a dict, need to use it to continue conversation
            reference = ref 
            
            async def callback(turn_context: TurnContext):
                await turn_context.send_activity("Time for standup! Say 'start' to begin.")

            # Ensure we have the necessary fields for continue_conversation
            if "service_url" not in reference:
                logger.warning(f"Skipping conversation {reference.get('conversation', {}).get('id')} - missing service_url")
                continue

            # Need to ensure proper casting if using strongly defined schemas
            # But adapter handles dicts gracefully usually.
            await bot_adapter.continue_conversation(
                reference,
                callback,
                settings.MICROSOFT_APP_ID
            )
            
        except Exception as e:
            logger.error(f"Failed to notify conversation: {e}")
