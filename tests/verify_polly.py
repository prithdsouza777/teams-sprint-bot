import asyncio
import os
from dotenv import load_dotenv
from app.services.polly import text_to_speech

# Load environment variables
load_dotenv()

async def main():
    print("Testing AWS Polly Integration...")
    
    text = "Hello! This is a test of the AWS Polly integration for the Teams Sprint Bot."
    print(f"Creating audio for: '{text}'")
    
    audio_data = await text_to_speech(text)
    
    if audio_data:
        filename = "verify_speech.mp3"
        with open(filename, "wb") as f:
            f.write(audio_data)
        print(f"Success! Audio saved to {filename}")
        print("Please play this file to verify the audio content.")
        
        # Determine absolute path for clarity
        abs_path = os.path.abspath(filename)
        print(f"File location: {abs_path}")
    else:
        print("Error: Failed to generate audio. Check your AWS credentials in .env")

if __name__ == "__main__":
    asyncio.run(main())
