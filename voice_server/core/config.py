
# Settings class to replace app.core.config
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
    # Determine DB Path relative to the project root (c:\docai_calling_agent\chroma_db_new)
    # We assume this file ends up in voice_server/core/config.py
    # So root is ../../
    # But wait, we are placing this in voice_server/core/config.py
    
    # Let's handle path dynamically
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DB_PATH = os.path.join(BASE_DIR, "chroma_db_new")

    # Twilio
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

settings = Settings()
