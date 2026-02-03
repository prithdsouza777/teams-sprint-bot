from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from loguru import logger

from app.config import settings
from app.bot.handler import TeamsBot


# Configure Bot Framework adapter
adapter_settings = BotFrameworkAdapterSettings(
    app_id=settings.MICROSOFT_APP_ID,
    app_password=settings.MICROSOFT_APP_PASSWORD,
)

bot_adapter = BotFrameworkAdapter(adapter_settings)


# Error handler
async def on_error(context: TurnContext, error: Exception):
    logger.error(f"Bot error: {error}")
    await context.send_activity("Sorry, something went wrong. Please try again.")


bot_adapter.on_turn_error = on_error

# Create bot instance
bot_handler = TeamsBot()
