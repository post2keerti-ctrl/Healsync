"""
Firebase Authentication.

Production flow (the real architecture):
  1. The Flutter mobile app signs the user in directly against Firebase Auth
     (email/password, Google, phone OTP, etc.) using the Firebase client SDK.
  2. Firebase gives the app an ID token.
  3. The app sends that ID token to this backend as:
         Authorization: Bearer <firebase_id_token>
  4. This backend verifies the token with the Firebase Admin SDK
     (`verify_id_token`) — it never sees passwords.

Local development fallback:
  Verifying a real Firebase ID token requires reaching Google's servers,
  which this sandbox cannot do and a fresh clone of this repo can't do
  either without a real Firebase project. So when no service-account
  credentials are configured, `/auth/dev-login` (see routers/auth.py)
  issues a locally-signed token with the exact same claim shape
  (`uid`, `email`), and `verify_token()` below verifies it locally.
  Swap in real Firebase by dropping a service-account JSON at the path
  in FIREBASE_CREDENTIALS_PATH — no other code changes needed.
"""
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt

from . import config

_firebase_app = None

if config.USE_REAL_FIREBASE:
    import firebase_admin
    from firebase_admin import auth as firebase_auth, credentials

    cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
    _firebase_app = firebase_admin.initialize_app(cred)
    print("[firebase_auth] Real Firebase Admin SDK initialized.")
else:
    print("[firebase_auth] No FIREBASE_CREDENTIALS_PATH configured — using local dev-login fallback.")


def issue_dev_token(uid: str, email: str) -> str:
    """DEV ONLY. Mint a locally-signed token shaped like a Firebase ID token's claims."""
    payload = {"uid": uid, "email": email, "exp": datetime.utcnow() + timedelta(hours=12)}
    return jwt.encode(payload, config.DEV_JWT_SECRET, algorithm="HS256")


def verify_token(id_token: str) -> Optional[dict]:
    """
    Returns {"uid": ..., "email": ...} for a valid token, or None if invalid.
    Uses real Firebase verification when configured, else the dev fallback.
    """
    if config.USE_REAL_FIREBASE:
        try:
            decoded = firebase_auth.verify_id_token(id_token)
            return {"uid": decoded["uid"], "email": decoded.get("email", "")}
        except Exception:
            return None
    else:
        try:
            payload = jwt.decode(id_token, config.DEV_JWT_SECRET, algorithms=["HS256"])
            return {"uid": payload["uid"], "email": payload["email"]}
        except JWTError:
            return None
