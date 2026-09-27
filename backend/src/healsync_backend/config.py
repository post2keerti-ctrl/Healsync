"""Environment settings for local and Firebase-hosted backend runs."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]
LOCAL_DEV_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$" if ENVIRONMENT == "development" else None
FIRESTORE_COLLECTION_PREFIX = os.getenv("FIRESTORE_COLLECTION_PREFIX", "healsync")
USE_FIRESTORE = os.getenv("USE_FIRESTORE", "false").lower() == "true"
ENABLE_DEV_AUTH = (
    ENVIRONMENT in {"development", "demo"}
    and os.getenv("ENABLE_DEV_AUTH", "true" if ENVIRONMENT == "development" else "false").lower() == "true"
)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
