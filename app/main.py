from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse, ORJSONResponse
from loguru import logger
import sys

from app.config import settings
from app.bot.adapter import bot_adapter, bot_handler

# Configure logging
logger.remove()
logger.add(sys.stdout, format="{time} | {level} | {message}", level="INFO")

app = FastAPI(
    title="AI Scrum Bot",
    description="Microsoft Teams bot for automated scrum standups",
    version="2.0.0",
    default_response_class=ORJSONResponse
)



# from app.voice.routes import router as voice_router

@app.get("/")
async def root():
    return {"status": "running", "service": "ai-scrum-bot", "version": "2.0.0"}

# app.include_router(voice_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Wrapper to make FastAPI Request compatible with aiohttp-based CloudAdapter
class AiohttpRequestWrapper:
    def __init__(self, request: Request):
        self._request = request
        self._body = None
    
    async def json(self):
        return await self._request.json()

    async def read(self):
        if self._body is None:
            self._body = await self._request.body()
        return self._body
        
    async def text(self):
        return (await self.read()).decode('utf-8')
        
    @property
    def headers(self):
        return self._request.headers
        
    @property
    def content_type(self):
        return self._request.headers.get("content-type")
        
    @property
    def method(self):
        return self._request.method
        
    @property
    def path(self):
        return self._request.url.path

    @property
    def rel_url(self):
        return self._request.url

    @property
    def query(self):
        return self._request.query_params


@app.post("/api/messages")
async def messages(request: Request):
    """Bot Framework messaging endpoint."""
    shimmed_request = AiohttpRequestWrapper(request)
    response = await bot_adapter.process(shimmed_request, bot_handler)
    
    if response:
        return Response(
            content=response.body, 
            status_code=response.status, 
            media_type="application/json"
        )
    return Response(status_code=201)


@app.get("/api/speak")
async def speak(text: str, voice_id: str = "Matthew"):
    """Convert text to speech."""
    from app.services.polly import text_to_speech
    
    audio_data = await text_to_speech(text, voice_id)
    if not audio_data:
        return JSONResponse({"error": "Failed to generate speech"}, status_code=500)
        
    return Response(content=audio_data, media_type="audio/mpeg")


@app.post("/api/scheduled-standup")
@app.get("/api/scheduled-standup")  # Allow GET for easy testing
async def scheduled_standup():
    """Cloud Scheduler endpoint for proactive standups."""
    logger.info("Scheduled standup triggered")
    
    from app.services.proactive import notify_all_teams
    
    try:
        await notify_all_teams()
        return {"success": True, "message": "Proactive standup messages sent"}
    except Exception as e:
        logger.error(f"Scheduled standup failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/conversations")
async def list_conversations():
    """Debug endpoint to see stored conversation references."""
    from app.services.firestore import get_all_conversations
    conversations = await get_all_conversations()
    return {
        "count": len(conversations),
        "conversations": [
            {"id": c.get("conversation", {}).get("id", "unknown")[:30] + "...", 
             "has_service_url": "service_url" in c}
            for c in conversations
        ]
    }


@app.get("/privacy", response_class=HTMLResponse)
async def privacy():
    return """
    <html>
        <head><title>Privacy Policy</title></head>
        <body>
            <h1>Privacy Policy</h1>
            <p>This app does not store any personal data beyond what is needed for the standup functionality.</p>
        </body>
    </html>
    """


@app.get("/terms", response_class=HTMLResponse)
async def terms():
    return """
    <html>
        <head><title>Terms of Use</title></head>
        <body>
            <h1>Terms of Use</h1>
            <p>By using this bot, you agree to participate in automated daily standups.</p>
        </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)

