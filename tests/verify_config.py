import os
import asyncio
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def check_env_var(name):
    original_val = os.getenv(name)
    val = original_val.strip() if original_val else None
    
    if not val:
        print(f"[-] {name}: MISSING")
        return False
    
    # Check for placeholder values from .env.example
    placeholders = [
        "your_microsoft_app_id", "your_microsoft_app_password",
        "your_google_project_id", "your_gemini_api_key",
        "mongodb://localhost:27017/aiscrumbot", "your_access_key_id"
    ]
    if val in placeholders:
        print(f"[!] {name}: SET TO DEFAULT PLACEHOLDER (Update this!)")
        return False
        
    print(f"[+] {name}: Present")
    return True

async def verify_gemini():
    print("\n--- Testing Gemini Connectivity ---")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Skipping Gemini test: Key missing.")
        return

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        print("Sending request to Gemini 2.0 Flash...")
        response = await model.generate_content_async("Say hello!")
        
        print(f"[+] Gemini Response: {response.text}")
        print("[+] Gemini Integration Verified!")
    except Exception as e:
        print(f"[-] Gemini Verification Failed: {e}")

async def main():
    print("--- Checking Environment Variables ---")
    
    # Azure
    azure_ok = check_env_var("MICROSOFT_APP_ID") and check_env_var("MICROSOFT_APP_PASSWORD")
    
    # Google
    google_ok = check_env_var("GEMINI_API_KEY")
    check_env_var("GOOGLE_PROJECT_ID")
    
    # Mongo
    check_env_var("MONGODB_URL")
    
    # AWS
    check_env_var("AWS_ACCESS_KEY_ID")

    # Run active validtation
    if google_ok:
        await verify_gemini()
    else:
        print("\nSkipping Gemini test (Missing Keys)")

if __name__ == "__main__":
    asyncio.run(main())
