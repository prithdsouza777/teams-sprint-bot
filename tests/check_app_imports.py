print("1. Importing app.config...", flush=True)
try:
    from app.config import settings
    print(f"2. Config loaded. App ID: {settings.MICROSOFT_APP_ID[:4]}...", flush=True)
except Exception as e:
    print(f"Config import failed: {e}", flush=True)

print("3. Importing app.bot.adapter...", flush=True)
try:
    from app.bot.adapter import bot_adapter
    print("4. Adapter imported", flush=True)
except Exception as e:
    print(f"Adapter import failed: {e}", flush=True)

print("5. Done checking app imports", flush=True)
