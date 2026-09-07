"""
Authentication & profile endpoints.

Real flow (Flutter app + Firebase Auth):
  1. App signs the user in with the Firebase client SDK -> gets an ID token.
  2. App calls POST /auth/sync-profile once (Authorization: Bearer <id_token>)
     to create/update this user's role + profile in MongoDB.
  3. Every other request just sends the same ID token in the Authorization header.

Dev flow (no Firebase project configured, e.g. this sandbox):
  1. POST /auth/dev-login with an email+password -> returns a locally-signed
     token with the same shape as a Firebase ID token.
  2. Use it exactly like a real token from here on. Disabled automatically
     the moment real Firebase credentials are configured.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .. import config, database as db, firebase_auth, schemas

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer()


@router.get("/firebase-config", response_model=dict)
def firebase_config():
    """Return only the public Firebase Web SDK configuration to the frontend."""
    return {
        "enabled": config.USE_REAL_FIREBASE_WEB,
        "apiKey": config.FIREBASE_WEB_API_KEY,
        "authDomain": config.FIREBASE_WEB_AUTH_DOMAIN,
        "projectId": config.FIREBASE_WEB_PROJECT_ID,
        "storageBucket": config.FIREBASE_WEB_STORAGE_BUCKET,
        "messagingSenderId": config.FIREBASE_WEB_MESSAGING_SENDER_ID,
        "appId": config.FIREBASE_WEB_APP_ID,
    }


@router.post("/dev-login", response_model=dict)
def dev_login(payload: schemas.DevLoginRequest):
    """DEV ONLY — mints a local token. Disabled once real Firebase is configured."""
    if config.USE_REAL_FIREBASE:
        raise HTTPException(status_code=403, detail="Real Firebase is configured — use the Firebase client SDK to sign in instead.")
    uid = f"dev:{payload.email}"
    token = firebase_auth.issue_dev_token(uid, payload.email)
    return {"id_token": token, "note": "DEV token — behaves like a Firebase ID token for this API."}


def get_current_firebase_claims(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    claims = firebase_auth.verify_token(creds.credentials)
    if not claims:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return claims


@router.post("/sync-profile", response_model=schemas.UserOut)
def sync_profile(payload: schemas.SyncProfileRequest, claims: dict = Depends(get_current_firebase_claims)):
    """Create the local profile the first time a Firebase-authenticated user calls the API, or update it."""
    existing = db.users.find_one({"firebase_uid": claims["uid"]})

    doc = {
        "firebase_uid": claims["uid"], "email": claims["email"], "name": payload.name,
        "role": payload.role, "device_token": payload.device_token or "",
        "location": payload.location.dict() if payload.location else None,
    }

    if existing:
        db.users.update_one({"_id": existing["_id"]}, {"$set": doc})
        user_id = existing["_id"]
    else:
        doc["created_at"] = datetime.utcnow()
        result = db.users.insert_one(doc)
        user_id = result.inserted_id

        if payload.role == "patient":
            db.patient_profiles.insert_one({
                "user_id": user_id, "doctor_id": None, "surgery_type": "", "recovery_day": 1,
                "recovery_total_days": 14, "confidence_score": 90,
                "location": doc["location"] or {"lat": 13.0827, "lng": 80.2707},
            })
        elif payload.role == "doctor":
            db.doctor_profiles.insert_one({"user_id": user_id, "specialty": "", "license_verified": True})
        elif payload.role == "supplier":
            db.supplier_profiles.insert_one({
                "user_id": user_id, "business_name": payload.name,
                "location": doc["location"] or {"lat": 13.0827, "lng": 80.2707},
                "avg_item_cost": 6.0, "avg_dispatch_hours": 4.0,
            })

    doc["_id"] = user_id
    return schemas.UserOut(id=str(user_id), firebase_uid=doc["firebase_uid"], name=doc["name"], email=doc["email"], role=doc["role"])


def get_current_user(claims: dict = Depends(get_current_firebase_claims)) -> dict:
    user = db.users.find_one({"firebase_uid": claims["uid"]})
    if not user:
        raise HTTPException(status_code=404, detail="No local profile yet — call POST /auth/sync-profile first")
    return user


def require_role(role: str):
    def _checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] != role:
            raise HTTPException(status_code=403, detail=f"This endpoint requires role '{role}'")
        return user
    return _checker


@router.get("/me", response_model=schemas.UserOut)
def get_me(user: dict = Depends(get_current_user)):
    return schemas.UserOut(id=str(user["_id"]), firebase_uid=user["firebase_uid"], name=user["name"], email=user["email"], role=user["role"])
