"""Doctor-facing endpoints — patient roster, plan review & approval."""
from typing import List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from .. import database as db, schemas
from ..services import notification_service
from .auth import require_role
from .patients import _plan_item_out

router = APIRouter(prefix="/doctors", tags=["Doctor App"])

FLAG_THRESHOLD = 90


def _profile(user: dict) -> dict:
    p = db.doctor_profiles.find_one({"user_id": user["_id"]})
    if not p:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return p


@router.get("/me/patients", response_model=List[schemas.PatientSummaryOut])
def list_patients(user: dict = Depends(require_role("doctor"))):
    doctor = _profile(user)
    patients = db.patient_profiles.find({"doctor_id": doctor["_id"]})
    out = []
    for p in patients:
        pu = db.users.find_one({"_id": p["user_id"]})
        out.append(schemas.PatientSummaryOut(
            id=str(p["_id"]), name=pu["name"] if pu else "Unknown", surgery_type=p.get("surgery_type", ""),
            recovery_day=p["recovery_day"], confidence_score=p["confidence_score"],
            flagged=p["confidence_score"] < FLAG_THRESHOLD,
        ))
    return out


@router.get("/patients/{patient_id}/plan", response_model=List[schemas.RecoveryPlanItemOut])
def get_patient_plan(patient_id: str, user: dict = Depends(require_role("doctor"))):
    doctor = _profile(user)
    patient = db.patient_profiles.find_one({"_id": ObjectId(patient_id), "doctor_id": doctor["_id"]})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found under your care")
    items = db.recovery_plan_items.find({"patient_id": patient["_id"], "day": patient["recovery_day"]}).sort("time", 1)
    return [_plan_item_out(i) for i in items]


@router.put("/patients/{patient_id}/plan", response_model=List[schemas.RecoveryPlanItemOut])
def review_patient_plan(patient_id: str, review: schemas.PlanReview, user: dict = Depends(require_role("doctor"))):
    doctor = _profile(user)
    patient = db.patient_profiles.find_one({"_id": ObjectId(patient_id), "doctor_id": doctor["_id"]})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found under your care")

    for adj in review.adjustments:
        update = {"doctor_adjusted": True}
        if adj.time is not None:
            update["time"] = adj.time
        if adj.title is not None:
            update["title"] = adj.title
        if adj.description is not None:
            update["description"] = adj.description
        db.recovery_plan_items.update_one(
            {"_id": ObjectId(adj.item_id), "patient_id": patient["_id"]}, {"$set": update},
        )

    if review.approve:
        new_score = min(100, patient["confidence_score"] + 5)
        db.patient_profiles.update_one({"_id": patient["_id"]}, {"$set": {"confidence_score": new_score}})
        db.alerts.update_many({"patient_id": patient["_id"], "resolved": False}, {"$set": {"resolved": True}})

        patient_user = db.users.find_one({"_id": patient["user_id"]})
        if patient_user:
            notification_service.send(
                str(patient_user["_id"]), "Recovery plan updated",
                f"Dr. {user['name']} approved your updated recovery plan.",
                device_token=patient_user.get("device_token", ""),
            )

    items = db.recovery_plan_items.find({"patient_id": patient["_id"], "day": patient["recovery_day"]}).sort("time", 1)
    return [_plan_item_out(i) for i in items]
