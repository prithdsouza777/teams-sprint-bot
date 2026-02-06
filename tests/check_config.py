print("Starting config import check...", flush=True)
try:
    from app.config import settings
    print("Config imported success", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
