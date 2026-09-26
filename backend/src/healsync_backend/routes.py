"""First migrated API route using the database-independent boundary."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
import json
from datetime import datetime, timezone

from .auth import current_claims, issue_dev_token
from .config import ENABLE_DEV_AUTH, USE_FIRESTORE
from .contracts import UserRecord
from .repositories import user_repository
from .db.sqlite import SQLiteDatabase

router = APIRouter(prefix="/api/v1", tags=["Core"])

DEV_ACCOUNTS = {
    "karthik@healsync.com": ("patient", "Karthik Subramanian"),
    "doctor@healsync.com": ("doctor", "Dr. Meera Rao"),
    "supplier@healsync.com": ("supplier", "Apollo MedSupply"),
    "patient1@healsync.com": ("patient", "Asha Patel"),
    "patient2@healsync.com": ("patient", "Ravi Kumar"),
    "patient3@healsync.com": ("patient", "Meera Singh"),
}


@router.post("/auth/dev-login")
def dev_login(payload: dict) -> dict:
    if not ENABLE_DEV_AUTH:
        raise HTTPException(status_code=403, detail="Dev auth is disabled")

    email = str(payload.get("email", "")).strip().lower()
    password = payload.get("password")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    if password != "demo":
        raise HTTPException(status_code=401, detail="Incorrect password for this local demo account.")
    account = DEV_ACCOUNTS.get(email)
    if account is None:
        raise HTTPException(status_code=401, detail="No demo account is registered for that name.")
    requested_role, account_name = account
    supplied_role = str(payload.get("role", "")).strip().lower()
    if supplied_role and supplied_role != requested_role:
        raise HTTPException(status_code=403, detail=f"This account belongs to {requested_role.title()} login.")

    uid = f"dev:{email}"
    repository = user_repository()
    existing = repository.get_by_firebase_uid(uid)
    if existing is None:
        repository.create_or_update(UserRecord(
            id="",
            firebase_uid=uid,
            email=email,
            name=account_name,
            role=requested_role,
        ))
    elif existing.role != requested_role:
        raise HTTPException(
            status_code=403,
            detail=f"This account is registered as {existing.role}. Choose the {existing.role} login.",
        )

    token = issue_dev_token(uid, email)
    return {"id_token": token, "role": requested_role, "note": "DEV token — behaves like a Firebase ID token for local development."}


@router.get("/auth/me")
def get_current_profile(claims: dict = Depends(current_claims)) -> dict:
    repository = user_repository()
    user = repository.get_by_firebase_uid(claims["uid"])
    if user is None:
        user = repository.create_or_update(UserRecord(
            id="",
            firebase_uid=claims["uid"],
            email=claims.get("email", ""),
            name=claims.get("name") or claims.get("email", "").split("@")[0],
            role="patient",
        ))
    return {"id": user.id, "firebase_uid": user.firebase_uid, "name": user.name, "email": user.email, "role": user.role}


@router.get("/me")
def get_profile_alias(claims: dict = Depends(current_claims)) -> dict:
    return get_current_profile(claims)


@router.get("/suppliers/me/orders")
def supplier_orders(claims: dict = Depends(current_claims)):
    if USE_FIRESTORE:
        raise HTTPException(status_code=501, detail="Supplier orders are not available for Firestore yet")
    repository = user_repository()
    user = repository.get_by_firebase_uid(claims["uid"])
    if user is None or user.role != "supplier":
        raise HTTPException(status_code=403, detail="Supplier access required")
    with SQLiteDatabase() as database:
        database.initialize()
        supplier = database.execute("SELECT id FROM supplier_profiles WHERE user_id = ?", (user.id,)).fetchone()
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier profile not found")
        rows = database.execute(
            "SELECT id, reference, patient_id, items_json, total_amount, status, match_score, distance_km, created_at FROM orders WHERE supplier_id = ? ORDER BY created_at DESC",
            (supplier["id"],),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "reference": row["reference"],
                "patient_id": row["patient_id"],
                "items": json.loads(row["items_json"]),
                "total_amount": row["total_amount"],
                "status": row["status"],
                "match_score": row["match_score"],
                "distance_km": row["distance_km"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]


@router.get("/suppliers/me/inventory")
def supplier_inventory(claims: dict = Depends(current_claims)):
    if USE_FIRESTORE:
        raise HTTPException(status_code=501, detail="Supplier inventory is not available for Firestore yet")
    repository = user_repository()
    user = repository.get_by_firebase_uid(claims["uid"])
    if user is None or user.role != "supplier":
        raise HTTPException(status_code=403, detail="Supplier access required")
    with SQLiteDatabase() as database:
        database.initialize()
        supplier = database.execute("SELECT id FROM supplier_profiles WHERE user_id = ?", (user.id,)).fetchone()
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier profile not found")
        rows = database.execute(
            "SELECT id, name, stock_pct, unit_price FROM inventory_items WHERE supplier_id = ? ORDER BY name",
            (supplier["id"],),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "stock_pct": row["stock_pct"],
                "unit_price": row["unit_price"],
            }
            for row in rows
        ]
