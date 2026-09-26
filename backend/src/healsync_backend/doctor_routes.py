"""Doctor-owned patient roster endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from uuid import uuid5, NAMESPACE_URL

from .auth import current_claims
from .config import USE_FIRESTORE
from .repositories import user_repository
from .db.sqlite import SQLiteDatabase
from .db.firestore_data import collection, records
from .firebase import firestore_client

router = APIRouter(prefix="/api/v1/doctors", tags=["Doctors"])


def current_doctor(claims: dict = Depends(current_claims)):
    user = user_repository().get_by_firebase_uid(claims["uid"])
    if user is None or user.role != "doctor":
        raise HTTPException(status_code=403, detail="Doctor access required")
    return user


@router.get("/me/patients")
def list_patients(doctor=Depends(current_doctor)) -> list[dict]:
    if USE_FIRESTORE:
        client = firestore_client()
        doctor_profiles = records(client, "doctor_profiles", user_id=doctor.id)
        if not doctor_profiles:
            return []
        profiles = records(client, "patient_profiles", doctor_id=doctor_profiles[0]["id"])
        patients = []
        for profile in profiles:
            user_snapshot = collection(client, "users").document(profile["user_id"]).get()
            if not user_snapshot.exists:
                continue
            user = user_snapshot.to_dict()
            day = int(profile.get("recovery_day", 1))
            total_days = int(profile.get("recovery_total_days", 14))
            confidence = int(profile.get("confidence_score", 90))
            patients.append({
                "id": user_snapshot.id,
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "surgery_type": profile.get("surgery_type", ""),
                "recovery_day": day,
                "recovery_total_days": total_days,
                "recovery_percent": confidence,
                "fully_recovered": day >= total_days and confidence == 100,
            })
        patients.sort(key=lambda patient: (-patient["recovery_percent"], patient["name"].casefold()))
        return patients
    with SQLiteDatabase() as database:
        database.initialize()
        rows = database.execute(
            """
            SELECT u.id, u.name, u.email, p.surgery_type, p.recovery_day,
                   p.recovery_total_days, p.confidence_score
            FROM doctor_profiles d
            JOIN patient_profiles p ON p.doctor_id = d.id
            JOIN users u ON u.id = p.user_id
            WHERE d.user_id = ?
            ORDER BY p.confidence_score DESC, u.name COLLATE NOCASE
            """,
            (doctor.id,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "email": row["email"],
                "surgery_type": row["surgery_type"],
                "recovery_day": row["recovery_day"],
                "recovery_total_days": row["recovery_total_days"],
                "recovery_percent": row["confidence_score"],
                "fully_recovered": row["recovery_day"] >= row["recovery_total_days"] and row["confidence_score"] == 100,
            }
            for row in rows
        ]


@router.get("/me/alerts")
def list_alerts(doctor=Depends(current_doctor)) -> list[dict]:
    if USE_FIRESTORE:
        client = firestore_client()
        doctor_profiles = records(client, "doctor_profiles", user_id=doctor.id)
        if not doctor_profiles:
            return []
        profile_rows = records(client, "patient_profiles", doctor_id=doctor_profiles[0]["id"])
        patient_ids = {profile["id"] for profile in profile_rows}
        stored = []
        for row in records(client, "alerts"):
            if row.get("patient_id") not in patient_ids:
                continue
            profile = next(item for item in profile_rows if item["id"] == row["patient_id"])
            patient_user = collection(client, "users").document(profile["user_id"]).get()
            patient_name = patient_user.to_dict().get("name", "") if patient_user.exists else ""
            stored.append({
                "id": row["id"],
                "patient_id": row["patient_id"],
                "patient_name": patient_name,
                "severity": row.get("severity", "info"),
                "message": row.get("message", ""),
                "resolved": bool(row.get("resolved", False)),
                "created_at": row.get("created_at", ""),
            })
        known = {(alert["patient_id"], alert["message"]) for alert in stored}
        now = datetime.now(timezone.utc).isoformat()
        for profile in profile_rows:
            score = int(profile.get("confidence_score", 90))
            if score >= 100:
                continue
            patient_user = collection(client, "users").document(profile["user_id"]).get()
            name = patient_user.to_dict().get("name", "Patient") if patient_user.exists else "Patient"
            message = f"{name} is at {score}% recovery confidence (day {profile.get('recovery_day', 1)} of {profile.get('recovery_total_days', 14)})."
            if (profile["id"], message) not in known:
                stored.append({
                    "id": str(uuid5(NAMESPACE_URL, f"healsync-doctor-alert:{profile['id']}")),
                    "patient_id": profile["id"],
                    "patient_name": name,
                    "severity": "warning" if score < 70 else "info",
                    "message": message,
                    "resolved": False,
                    "created_at": now,
                })
        stored.sort(key=lambda alert: (alert["resolved"], alert["created_at"]), reverse=False)
        return stored
    with SQLiteDatabase() as database:
        database.initialize()
        rows = database.execute(
            """
            SELECT p.id AS patient_id, u.name AS patient_name, p.recovery_day,
                   p.recovery_total_days, p.confidence_score
            FROM doctor_profiles d
            JOIN patient_profiles p ON p.doctor_id = d.id
            JOIN users u ON u.id = p.user_id
            WHERE d.user_id = ?
            ORDER BY p.confidence_score ASC, u.name COLLATE NOCASE
            """,
            (doctor.id,),
        ).fetchall()
        stored = database.execute(
            """
            SELECT a.id, a.patient_id, u.name AS patient_name, a.severity,
                   a.message, a.resolved, a.created_at
            FROM alerts a
            JOIN patient_profiles p ON p.id = a.patient_id
            JOIN users u ON u.id = p.user_id
            JOIN doctor_profiles d ON d.id = p.doctor_id
            WHERE d.user_id = ?
            ORDER BY a.resolved ASC, a.created_at DESC
            """,
            (doctor.id,),
        ).fetchall()

    alerts = [
        {
            "id": row["id"],
            "patient_id": row["patient_id"],
            "patient_name": row["patient_name"],
            "severity": row["severity"],
            "message": row["message"],
            "resolved": bool(row["resolved"]),
            "created_at": row["created_at"],
        }
        for row in stored
    ]
    known = {(item["patient_id"], item["message"]) for item in alerts}
    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        if row["confidence_score"] < 100:
            message = (
                f"{row['patient_name']} is at {row['confidence_score']}% recovery confidence "
                f"(day {row['recovery_day']} of {row['recovery_total_days']})."
            )
            if (row["patient_id"], message) not in known:
                alerts.append({
                    "id": str(uuid5(NAMESPACE_URL, f"healsync-doctor-alert:{row['patient_id']}")),
                    "patient_id": row["patient_id"],
                    "patient_name": row["patient_name"],
                    "severity": "warning" if row["confidence_score"] < 70 else "info",
                    "message": message,
                    "resolved": False,
                    "created_at": now,
                })
    return alerts