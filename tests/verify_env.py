import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.config import settings

print(f"App ID: '{settings.MICROSOFT_APP_ID}'")
print(f"Password: '{settings.MICROSOFT_APP_PASSWORD}'") # Only printing to verify it's not empty, user sees this locally
print(f"Tenant ID: '{settings.MICROSOFT_TENANT_ID}'")

if not settings.MICROSOFT_APP_ID:
    print("ERROR: App ID is empty!")
else:
    print("SUCCESS: App ID is loaded.")
