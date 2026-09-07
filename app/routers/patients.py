"""
Patient-facing endpoints. This is where the whole pipeline comes together:

  POST /patients/me/documents:
      Tesseract OCR  ->  spaCy/scispaCy medical NER  ->  Llama 3
      (image bytes)      (structured medicines)          (day-by-day plan JSON)

  POST /patients/me/orders:
      weighted matching algorithm (matching_service) using real distance
      from routing_service (Google Maps / haversine) -> creates an order
      with the best supplier, plus a live ETA.
"""
import random
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from bson import ObjectId

from .. import database as db, schemas
from ..services import llm_service, matching_service, nlp_service, notification_service, ocr_service, routing_service
from .auth import require_role

router = APIRouter(prefix="/patients", tags=["Patient App"])


def _profile(user: dict) -> dict:
    p = db.patient_profiles.find_one({"user_id": user["_id"]})
    if not p:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return p


def _loc_tuple(loc: dict):
    return (loc["lat"], loc["lng"])


@router.get("/me/dashboard", response_model=schemas.DashboardOut)
def get_dashboard(user: dict = Depends(require_role("patient"))):
    profile = _profile(user)
    today_items = list(db.recovery_plan_items.find({
        "patient_id": profile["_id"], "day": profile["recovery_day"],
    }).sort("time", 1))

    doctor_name = None
    if profile.get("doctor_id"):
        doc_profile = db.doctor_profiles.find_one({"_id": profile["doctor_id"]})
        if doc_profile:
            doc_user = db.users.find_one({"_id": doc_profile["user_id"]})
            doctor_name = doc_user["name"] if doc_user else None

    active_order = db.orders.find_one(
        {"patient_id": profile["_id"], "status": {"$in": ["new", "accepted", "dispatched"]}},
        sort=[("created_at", -1)],
    )

    return schemas.DashboardOut(
        patient_name=user["name"], recovery_day=profile["recovery_day"],
        recovery_total_days=profile["recovery_total_days"], confidence_score=profile["confidence_score"],
        doctor_name=doctor_name,
        today_items=[_plan_item_out(i) for i in today_items],
        active_order_reference=active_order["reference"] if active_order else None,
    )


def _plan_item_out(i: dict) -> schemas.RecoveryPlanItemOut:
    return schemas.RecoveryPlanItemOut(
        id=str(i["_id"]), day=i["day"], time=i["time"], title=i["title"],
        description=i["description"], category=i["category"], doctor_adjusted=i.get("doctor_adjusted", False),
    )


@router.get("/me/recovery-plan", response_model=List[schemas.RecoveryPlanItemOut])
def get_recovery_plan(day: Optional[int] = None, user: dict = Depends(require_role("patient"))):
    profile = _profile(user)
    query = {"patient_id": profile["_id"]}
    if day is not None:
        query["day"] = day
    items = db.recovery_plan_items.find(query).sort([("day", 1), ("time", 1)])
    return [_plan_item_out(i) for i in items]


@router.post("/me/documents", response_model=schemas.DocumentOut, status_code=201)
async def upload_discharge_summary(file: UploadFile = File(...), user: dict = Depends(require_role("patient"))):
    """Full pipeline: OCR -> medical NER -> Llama 3 plan generation -> saved recovery plan."""
    profile = _profile(user)
    raw_bytes = await file.read()

    # 1) OCR (Tesseract)
    try:
        ocr_text = ocr_service.extract_text(raw_bytes)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read image: {exc}")

    # 2) NLP / medical NER (spaCy / scispaCy)
    medicines = nlp_service.extract_medicines(ocr_text)

    # 3) LLM structuring (Llama 3)
    plan_items = llm_service.generate_recovery_plan(medicines, recovery_day=profile["recovery_day"])

    for item in plan_items:
        db.recovery_plan_items.insert_one({
            "patient_id": profile["_id"], "day": item["day"], "time": item["time"],
            "title": item["title"], "description": item["description"],
            "category": item["category"], "doctor_adjusted": False,
        })

    doc = {
        "patient_id": profile["_id"], "filename": file.filename, "ocr_text": ocr_text,
        "nlp_pipeline_mode": nlp_service.pipeline_mode(), "extracted_medicines": medicines,
        "uploaded_at": datetime.utcnow(),
    }
    result = db.documents.insert_one(doc)

    notification_service.send(str(user["_id"]), "Recovery plan ready",
                               f"Your discharge summary was processed — {len(plan_items)} plan items added.",
                               device_token=user.get("device_token", ""))

    return schemas.DocumentOut(
        id=str(result.inserted_id), filename=doc["filename"], ocr_text=ocr_text,
        nlp_pipeline_mode=doc["nlp_pipeline_mode"], extracted_medicines=medicines,
        generated_plan_items=len(plan_items), uploaded_at=doc["uploaded_at"],
    )


_CART_CATALOG = {
    "Amoxicillin 500mg": (21, 6.50), "Ibuprofen 400mg": (10, 3.20),
    "Compression Bandage": (4, 4.00), "Walking Frame": (1, 45.00),
}


@router.get("/me/cart", response_model=schemas.CartOut)
def get_cart(user: dict = Depends(require_role("patient"))):
    items, total = [], 0.0
    for name, (qty, price) in _CART_CATALOG.items():
        subtotal = round(qty * price, 2)
        items.append(schemas.CartItemOut(name=name, category="medicine", qty=qty, unit_price=price, subtotal=subtotal))
        total += subtotal
    return schemas.CartOut(items=items, total_amount=round(total, 2))


@router.post("/me/orders", response_model=schemas.OrderOut, status_code=201)
def place_order(user: dict = Depends(require_role("patient"))):
    """Runs the weighted matching algorithm (with real distance) and creates the order."""
    profile = _profile(user)
    patient_loc = _loc_tuple(profile.get("location") or {"lat": 13.0827, "lng": 80.2707})
    cart = get_cart(user=user)

    suppliers = list(db.supplier_profiles.find({}))
    if not suppliers:
        raise HTTPException(status_code=503, detail="No suppliers available to match this order")

    candidates = []
    for s in suppliers:
        inv = list(db.inventory_items.find({"supplier_id": s["_id"]}))
        avg_stock = sum(i["stock_pct"] for i in inv) / len(inv) if inv else 100.0
        candidates.append({
            "id": str(s["_id"]), "name": s["business_name"],
            "location": _loc_tuple(s.get("location") or {"lat": 13.0827, "lng": 80.2707}),
            "avg_stock_pct": avg_stock, "avg_item_cost": s.get("avg_item_cost", 6.0),
            "avg_dispatch_hours": s.get("avg_dispatch_hours", 4.0),
        })

    ranked = matching_service.rank_suppliers(candidates, patient_loc)
    best = ranked[0]
    reference = f"HS-{random.randint(100000, 999999)}"

    order_doc = {
        "reference": reference, "patient_id": profile["_id"], "supplier_id": ObjectId(best["id"]),
        "items": [i.dict() for i in cart.items], "total_amount": cart.total_amount,
        "status": "new", "match_score": best["score"], "distance_km": best["distance_km"],
        "created_at": datetime.utcnow(),
    }
    result = db.orders.insert_one(order_doc)

    eta = routing_service.eta_minutes(_loc_tuple(next(s for s in suppliers if str(s["_id"]) == best["id"]).get("location") or {"lat": 13.0827, "lng": 80.2707}), patient_loc)

    return schemas.OrderOut(
        id=str(result.inserted_id), reference=reference, status="new", items=order_doc["items"],
        total_amount=cart.total_amount, supplier_name=best["name"], match_score=best["score"],
        distance_km=best["distance_km"], eta_minutes=eta, created_at=order_doc["created_at"],
    )


@router.get("/me/orders", response_model=List[schemas.OrderOut])
def list_orders(user: dict = Depends(require_role("patient"))):
    profile = _profile(user)
    orders = db.orders.find({"patient_id": profile["_id"]}).sort("created_at", -1)
    out = []
    for o in orders:
        supplier = db.supplier_profiles.find_one({"_id": o["supplier_id"]}) if o.get("supplier_id") else None
        out.append(schemas.OrderOut(
            id=str(o["_id"]), reference=o["reference"], status=o["status"], items=o["items"],
            total_amount=o["total_amount"], supplier_name=supplier["business_name"] if supplier else None,
            match_score=o["match_score"], distance_km=o.get("distance_km"), created_at=o["created_at"],
        ))
    return out


@router.get("/me/alerts", response_model=List[schemas.AlertOut])
def get_alerts(user: dict = Depends(require_role("patient"))):
    profile = _profile(user)
    alerts = db.alerts.find({"patient_id": profile["_id"]}).sort("created_at", -1)
    return [
        schemas.AlertOut(id=str(a["_id"]), severity=a["severity"], message=a["message"],
                          resolved=a["resolved"], created_at=a["created_at"])
        for a in alerts
    ]
