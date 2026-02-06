from botbuilder.integration.aiohttp import CloudAdapter, ConfigurationBotFrameworkAuthentication
from botbuilder.core import TurnContext
from loguru import logger
from app.config import settings
from app.bot.handler import TeamsBot


# Configure Bot Framework Authentication using a config class
# The SDK expects attributes named APP_ID, APP_PASSWORD, APP_TENANTID, APP_TYPE
class BotConfig:
    def __init__(self):
        self.APP_ID = settings.MICROSOFT_APP_ID.strip() if settings.MICROSOFT_APP_ID else ""
        self.APP_PASSWORD = settings.MICROSOFT_APP_PASSWORD.strip() if settings.MICROSOFT_APP_PASSWORD else ""
        self.APP_TYPE = "SingleTenant"
        self.APP_TENANTID = settings.MICROSOFT_TENANT_ID.strip() if settings.MICROSOFT_TENANT_ID else ""

bot_config = BotConfig()
bot_framework_authentication = ConfigurationBotFrameworkAuthentication(bot_config)

# Create Cloud Adapter
bot_adapter = CloudAdapter(bot_framework_authentication)


# Error handler
async def on_error(context: TurnContext, error: Exception):
    logger.error(f"Bot error: {error}")
    await context.send_activity("Sorry, something went wrong. Please try again.")


bot_adapter.on_turn_error = on_error

# Create bot instance
bot_handler = TeamsBot()
