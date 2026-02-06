
import asyncio
from unittest.mock import AsyncMock, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def verify_proactive_messaging():
    print("Starting Proactive Messaging Verification...")
    
    # Mock Firestore dependencies
    mock_conversations = [
        {
            "conversation": {"id": "conv_123"},
            "service_url": "https://smba.trafficmanager.net/amer/",
            "channel_id": "msteams"
        }
    ]
    
    # Mock database functions
    import app.services.firestore
    app.services.firestore.get_all_conversations = AsyncMock(return_value=mock_conversations)
    
    # Mock Bot Adapter
    import app.bot.adapter
    app.bot.adapter.bot_adapter = MagicMock()
    app.bot.adapter.bot_adapter.continue_conversation = AsyncMock()
    
    # Import the service to test
    from app.services.proactive import notify_all_teams
    
    try:
        await notify_all_teams()
        
        # Verify call arguments
        app.bot.adapter.bot_adapter.continue_conversation.assert_called_once()
        print("SUCCESS: continue_conversation was called on the adapter.")
        
        call_args = app.bot.adapter.bot_adapter.continue_conversation.call_args
        reference = call_args[0][0]
        print(f"Verified Reference ID: {reference['conversation']['id']}")
        
    except Exception as e:
        print(f"FAILURE: {e}")

if __name__ == "__main__":
    asyncio.run(verify_proactive_messaging())
