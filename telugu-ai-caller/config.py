"""
Configuration manager for Telugu AI Caller.
Loads environment variables from .env and provides sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Database & Redis Settings
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/leadcloser")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Use an absolute, configurable location so the app works from any launch folder.
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "leads_crm.db"))).expanduser()

# Sarvam AI Credentials & Settings
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_BASE_URL = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai")
SARVAM_TTS_ENDPOINT = f"{SARVAM_BASE_URL}/text-to-speech"
SARVAM_STT_ENDPOINT = f"{SARVAM_BASE_URL}/speech-to-text"
SARVAM_CHAT_ENDPOINT = f"{SARVAM_BASE_URL}/v1/chat/completions"

# Voice & Model Defaults
DEFAULT_TTS_MODEL = os.getenv("DEFAULT_TTS_MODEL", "bulbul:v4-flash")
DEFAULT_TTS_SPEAKER = os.getenv("DEFAULT_TTS_SPEAKER", "kavitha_te_conversation")
DEFAULT_STT_MODEL = os.getenv("DEFAULT_STT_MODEL", "saaras:v3")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "sarvam-105b-conversations")

# Telephony (Twilio / Exotel - Optional for direct phone calls)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

# Dialer & Telephony Provider (Vobiz / Exotel / Fake)
DIALER_PROVIDER = os.getenv("DIALER_PROVIDER", "fake")
VOBIZ_AUTH_ID = os.getenv("VOBIZ_AUTH_ID", "")
VOBIZ_AUTH_TOKEN = os.getenv("VOBIZ_AUTH_TOKEN", "")
VOBIZ_CALLER_ID = os.getenv("VOBIZ_CALLER_ID", "")
VOICE_PUBLIC_BASE_URL = os.getenv("VOICE_PUBLIC_BASE_URL", "")

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    if origin.strip()
]

