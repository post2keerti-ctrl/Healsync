"""Firestore collection helpers and deterministic starter records."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from ..config import FIRESTORE_COLLECTION_PREFIX


def collection(client, name: str):
    prefix = FIRESTORE_COLLECTION_PREFIX.strip()
    return client.collection(f"{prefix}_{name}" if prefix else name)


def records(client, name: str, **filters) -> list[dict]:
    query = collection(client, name)
    for key, value in filters.items():
        query = query.where(key, "==", value)
    return [{"id": snapshot.id, **snapshot.to_dict()} for snapshot in query.stream()]


def record(client, name: str, document_id: str) -> dict | None:
    snapshot = collection(client, name).document(document_id).get()
    return {"id": snapshot.id, **snapshot.to_dict()} if snapshot.exists else None


def seed_firestore(client) -> None:
    now = datetime.now(timezone.utc).isoformat()
    demo_users = [
        ("karthik@healsync.com", "Karthik Subramanian", "patient"),
        ("doctor@healsync.com", "Dr. Meera Rao", "doctor"),
        ("supplier@healsync.com", "Apollo MedSupply", "supplier"),
        ("patient1@healsync.com", "Asha Patel", "patient"),
        ("patient2@healsync.com", "Ravi Kumar", "patient"),
        ("patient3@healsync.com", "Meera Singh", "patient"),
    ]
    user_ids = {email: str(uuid5(NAMESPACE_URL, f"healsync-user:{email}")) for email, _, _ in demo_users}
    doctor_id = str(uuid5(NAMESPACE_URL, "healsync-doctor-profile"))
    supplier_id = str(uuid5(NAMESPACE_URL, "healsync-supplier-profile"))
    users = collection(client, "users")

    for email, name, role in demo_users:
        user_id = user_ids[email]
        ref = users.document(user_id)
        if not ref.get().exists:
            ref.set({"firebase_uid": f"seed:{email}", "email": email, "name": name, "role": role})

    doctor_ref = collection(client, "doctor_profiles").document(doctor_id)
    if not doctor_ref.get().exists:
        doctor_ref.set({"user_id": user_ids["doctor@healsync.com"], "specialty": "Orthopedic Surgery", "license_verified": True})
    supplier_ref = collection(client, "supplier_profiles").document(supplier_id)
    if not supplier_ref.get().exists:
        supplier_ref.set({"user_id": user_ids["supplier@healsync.com"], "business_name": "Apollo MedSupply"})

    patients = [
        ("karthik@healsync.com", "Knee surgery", 14, 14, 100),
        ("patient1@healsync.com", "Knee surgery", 7, 14, 70),
        ("patient2@healsync.com", "Hip replacement", 7, 14, 60),
        ("patient3@healsync.com", "Shoulder surgery", 10, 14, 75),
    ]
    for email, surgery, day, total_days, score in patients:
        user_id = user_ids[email]
        patient_id = str(uuid5(NAMESPACE_URL, f"healsync-patient-profile:{email}"))
        profile = collection(client, "patient_profiles").document(patient_id)
        if not profile.get().exists:
            profile.set({
                "user_id": user_id,
                "doctor_id": doctor_id,
                "surgery_type": surgery,
                "recovery_day": day,
                "recovery_total_days": total_days,
                "confidence_score": score,
                "location_lat": 13.0350,
                "location_lng": 80.2450,
            })

    patient_ids = {
        email: str(uuid5(NAMESPACE_URL, f"healsync-patient-profile:{email}"))
        for email, *_ in patients
    }
    plan = collection(client, "recovery_plan_items")
    for time, title, description, category in [
        ("08:00 AM", "Amoxicillin 500mg", "1 capsule with food", "medicine"),
        ("01:00 PM", "High-protein recovery meal", "Supports tissue healing", "meal"),
        ("05:00 PM", "Guided mobility exercise", "15 min gentle stretching", "exercise"),
    ]:
        item_id = str(uuid5(NAMESPACE_URL, f"healsync-plan:{time}:{title}"))
        plan_ref = plan.document(item_id)
        if not plan_ref.get().exists:
            plan_ref.set({
                "patient_id": patient_ids["karthik@healsync.com"],
                "day": 14,
                "time": time,
                "title": title,
                "description": description,
                "category": category,
                "doctor_adjusted": False,
            })

    inventory = collection(client, "inventory_items")
    stock = [
        ("Paracetamol 500mg", 85, 0.8),
        ("Amoxicillin 500mg", 70, 1.2),
        ("Bandage sterile", 90, 0.5),
        ("Pain relief gel", 60, 2.5),
        ("Surgical dressing", 45, 3.0),
    ]
    for name, stock_pct, price in stock:
        item_id = str(uuid5(NAMESPACE_URL, f"healsync-inventory:{name}"))
        item_ref = inventory.document(item_id)
        if not item_ref.get().exists:
            item_ref.set({"supplier_id": supplier_id, "name": name, "stock_pct": stock_pct, "unit_price": price})

    orders = collection(client, "orders")
    for index, (email, *_rest) in enumerate(patients, 1):
        reference = f"ORD-{index:04d}"
        order_id = str(uuid5(NAMESPACE_URL, f"healsync-order:{reference}"))
        order_ref = orders.document(order_id)
        if not order_ref.get().exists:
            order_ref.set({
                "reference": reference,
                "patient_id": patient_ids[email],
                "supplier_id": supplier_id,
                "items": [{"name": "Paracetamol 500mg", "qty": 30}, {"name": "Bandage sterile", "qty": 10}],
                "total_amount": 29.0,
                "status": "shipped" if index == 1 else "processing" if index == 2 else "delivered",
                "match_score": 0.92,
                "distance_km": 3.5 + index,
                "created_at": now,
            })

    alerts = collection(client, "alerts")
    seed_alerts = [
        ("karthik@healsync.com", "warning", "2 doses missed today - review your plan.", False),
        ("karthik@healsync.com", "info", "Recovery plan completed. Patient reached 100% recovery milestone.", True),
    ]
    for email, severity, message, resolved in seed_alerts:
        alert_id = str(uuid5(NAMESPACE_URL, f"healsync-alert:{email}:{message}"))
        alert_ref = alerts.document(alert_id)
        if not alert_ref.get().exists:
            alert_ref.set({
                "patient_id": patient_ids[email],
                "severity": severity,
                "message": message,
                "resolved": resolved,
                "created_at": now,
            })
