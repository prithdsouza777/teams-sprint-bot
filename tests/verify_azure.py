import asyncio
import aiohttp
from dotenv import load_dotenv
from loguru import logger
from app.config import settings

# Load environment variables
load_dotenv()

TOKEN_ENDPOINT_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

async def verify_azure_bot_credentials():
    logger.info("Verifying Azure Bot Credentials...")
    
    app_id = settings.MICROSOFT_APP_ID
    app_password = settings.MICROSOFT_APP_PASSWORD
    tenant_id = settings.MICROSOFT_TENANT_ID
    
    if not app_id or not app_password:
        logger.error("❌ Missing MICROSOFT_APP_ID or MICROSOFT_APP_PASSWORD in environment")
        return False

    # Determine endpoint based on Tenant ID (Critical for Single Tenant)
    if not tenant_id:
        logger.warning("⚠️ MICROSOFT_TENANT_ID not set. Using 'botframework.com' (Multi-Tenant default).")
        # Default for multi-tenant if no tenant specified (though often 'common' is used)
        token_endpoint = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
    else:
        logger.info(f"ℹ️ Using specific Tenant ID: {tenant_id}")
        token_endpoint = TOKEN_ENDPOINT_TEMPLATE.format(tenant_id=tenant_id)

    data = {
        "grant_type": "client_credentials",
        "client_id": app_id,
        "client_secret": app_password,
        "scope": "https://api.botframework.com/.default"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(token_endpoint, data=data) as response:
                if response.status == 200:
                    token_data = await response.json()
                    if "access_token" in token_data:
                        logger.success("✅ Azure Bot Authentication Successful (Token Acquired)")
                        return True
                    else:
                        logger.error("❌ Authentication succeeded but no access token returned")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Azure Bot Authentication Failed: HTTP {response.status}")
                    logger.error(f"Response: {error_text}")
                    return False
    except Exception as e:
        logger.error(f"❌ Azure Verification Error: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(verify_azure_bot_credentials())
