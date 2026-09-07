"""
Central configuration. Every external integration (MongoDB Atlas, Firebase,
Google Maps, Llama 3) is switched on purely by setting its environment
variable — nothing else in the code needs to change. If a variable is
missing, that integration automatically falls back to a local stand-in so
the whole app still runs for development/demo purposes.

Copy `.env.example` to `.env` and fill in real values when you're ready
to go live.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# ---- MongoDB Atlas ----
MONGODB_URI = os.getenv("MONGODB_URI", "")          # e.g. mongodb+srv://user:pass@cluster.mongodb.net
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "healsync")
USE_REAL_MONGO = bool(MONGODB_URI)

# ---- Firebase Authentication ----
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "")  # path to service-account.json
USE_REAL_FIREBASE = bool(FIREBASE_CREDENTIALS_PATH) and os.path.exists(FIREBASE_CREDENTIALS_PATH)
DEV_JWT_SECRET = os.getenv("DEV_JWT_SECRET", "dev-only-secret-change-me")

# Firebase Web SDK settings are public client configuration, not service-account secrets.
FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY", "")
FIREBASE_WEB_AUTH_DOMAIN = os.getenv("FIREBASE_WEB_AUTH_DOMAIN", "")
FIREBASE_WEB_PROJECT_ID = os.getenv("FIREBASE_WEB_PROJECT_ID", "")
FIREBASE_WEB_STORAGE_BUCKET = os.getenv("FIREBASE_WEB_STORAGE_BUCKET", "")
FIREBASE_WEB_MESSAGING_SENDER_ID = os.getenv("FIREBASE_WEB_MESSAGING_SENDER_ID", "")
FIREBASE_WEB_APP_ID = os.getenv("FIREBASE_WEB_APP_ID", "")
USE_REAL_FIREBASE_WEB = bool(FIREBASE_WEB_API_KEY and FIREBASE_WEB_PROJECT_ID)

# ---- Google Maps ----
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
USE_REAL_MAPS = bool(GOOGLE_MAPS_API_KEY)

# ---- Llama 3 (via a local/self-hosted Ollama server, or any OpenAI-compatible endpoint) ----
LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "")     # e.g. http://localhost:11434
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "llama3")
USE_REAL_LLM = bool(LLAMA_BASE_URL)

# ---- scispaCy medical NER model ----
SCISPACY_MODEL_NAME = os.getenv("SCISPACY_MODEL_NAME", "en_core_sci_sm")
