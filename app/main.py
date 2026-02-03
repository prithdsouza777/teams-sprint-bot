from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
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
    version="2.0.0"
)


@app.get("/")
async def root():
    return {"status": "running", "service": "ai-scrum-bot", "version": "2.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/messages")
async def messages(request: Request):
    """Bot Framework messaging endpoint."""
    try:
        body = await request.json()
        auth_header = request.headers.get("Authorization", "")
        
        response = await bot_adapter.process_activity(
            body,
            auth_header,
            bot_handler.on_turn
        )
        
        if response:
            return JSONResponse(content=response.body, status_code=response.status)
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return Response(status_code=500)


@app.post("/api/scheduled-standup")
async def scheduled_standup():
    """Cloud Scheduler endpoint for proactive standups."""
    logger.info("Scheduled standup triggered")
    # TODO: Implement proactive messaging
    return {"success": True, "message": "Standup triggered"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
