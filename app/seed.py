"""
Seeds demo accounts + data directly into MongoDB (real Atlas or the local
mongomock fallback) so the API is immediately explorable. Uses the same
dev-login identity scheme as app/routers/auth.py (`dev:<email>`) so these
accounts work with POST /auth/dev-login out of the box.

Chennai-area coordinates are used for patients/suppliers so the Google
Maps / Dijkstra routing endpoints have realistic geography to work with.
"""
from datetime import datetime

from . import database as db

DEMO_PASSWORD_NOTE = "Use POST /auth/dev-login with any of these emails (any password) to get a token."


def run():
    if db.doctor_profiles.count_documents({}) > 0:
        print("[seed] Data already present — skipping.")
        return

    # --- Doctor ---
    doc_user = db.users.insert_one({
        "firebase_uid": "dev:doctor@healsync.com", "email": "doctor@healsync.com", "name": "Dr. Meera Rao",
        "role": "doctor", "device_token": "", "location": None, "created_at": datetime.utcnow(),
    })
    doctor = db.doctor_profiles.insert_one({"user_id": doc_user.inserted_id, "specialty": "Orthopedic & Post-Surgical Care", "license_verified": True})

    # --- Suppliers (Chennai-area coordinates) ---
    sup1_user = db.users.insert_one({
        "firebase_uid": "dev:supplier@healsync.com", "email": "supplier@healsync.com", "name": "Apollo MedSupply Hub",
        "role": "supplier", "device_token": "", "location": {"lat": 13.0604, "lng": 80.2496}, "created_at": datetime.utcnow(),
    })
    apollo = db.supplier_profiles.insert_one({
        "user_id": sup1_user.inserted_id, "business_name": "Apollo MedSupply Hub",
        "location": {"lat": 13.0604, "lng": 80.2496}, "avg_item_cost": 5.10, "avg_dispatch_hours": 3.0,
    })

    sup2_user = db.users.insert_one({
        "firebase_uid": "dev:medplus@healsync.com", "email": "medplus@healsync.com", "name": "MedPlus Wholesale",
        "role": "supplier", "device_token": "", "location": {"lat": 13.0067, "lng": 80.2206}, "created_at": datetime.utcnow(),
    })
    medplus = db.supplier_profiles.insert_one({
        "user_id": sup2_user.inserted_id, "business_name": "MedPlus Wholesale",
        "location": {"lat": 13.0067, "lng": 80.2206}, "avg_item_cost": 5.40, "avg_dispatch_hours": 5.0,
    })

    for name, pct, price in [
        ("Amoxicillin 500mg", 82, 6.50), ("Ibuprofen 400mg", 15, 3.20),
        ("Compression Bandage", 64, 4.00), ("Walking Frame", 18, 45.00),
    ]:
        db.inventory_items.insert_one({"supplier_id": apollo.inserted_id, "name": name, "stock_pct": pct, "unit_price": price})
    for name, pct, price in [("Amoxicillin 500mg", 70, 6.80), ("Ibuprofen 400mg", 55, 3.10)]:
        db.inventory_items.insert_one({"supplier_id": medplus.inserted_id, "name": name, "stock_pct": pct, "unit_price": price})

    # --- Patients ---
    patients_data = [
        ("Karthik Subramanian", "karthik@healsync.com", "Knee surgery", 6, 14, 87, True, {"lat": 13.0350, "lng": 80.2450}),
        ("Anitha Nair", "anitha@healsync.com", "Appendectomy", 2, 10, 96, False, {"lat": 13.0700, "lng": 80.2200}),
        ("Ravi Verma", "ravi@healsync.com", "Hip replacement", 11, 21, 92, False, {"lat": 13.1000, "lng": 80.2900}),
        ("Sita Pillai", "sita@healsync.com", "C-section", 4, 14, 98, False, {"lat": 12.9900, "lng": 80.2350}),
    ]
    for name, email, surgery, day, total, score, flagged, loc in patients_data:
        u = db.users.insert_one({
            "firebase_uid": f"dev:{email}", "email": email, "name": name, "role": "patient",
            "device_token": "", "location": loc, "created_at": datetime.utcnow(),
        })
        p = db.patient_profiles.insert_one({
            "user_id": u.inserted_id, "doctor_id": doctor.inserted_id, "surgery_type": surgery,
            "recovery_day": day, "recovery_total_days": total, "confidence_score": score, "location": loc,
        })

        for time, title, desc, cat in [
            ("8:00 AM", "Amoxicillin 500mg", "1 capsule · with food", "medicine"),
            ("1:00 PM", "High-protein recovery meal", "Supports tissue healing", "meal"),
            ("5:00 PM", "Guided mobility exercise", "15 min gentle stretching", "exercise"),
            ("9:00 PM", "Ibuprofen 400mg", "1 tablet · as needed", "medicine"),
        ]:
            db.recovery_plan_items.insert_one({
                "patient_id": p.inserted_id, "day": day, "time": time, "title": title,
                "description": desc, "category": cat, "doctor_adjusted": False,
            })

        if flagged:
            db.alerts.insert_one({
                "patient_id": p.inserted_id, "severity": "warning",
                "message": "2 doses missed today — confidence score dropped to 87.",
                "resolved": False, "created_at": datetime.utcnow(),
            })

    print("[seed] Demo data created.")
    print(f"[seed] {DEMO_PASSWORD_NOTE}")
    print("[seed] Accounts: doctor@healsync.com, supplier@healsync.com, medplus@healsync.com,")
    print("[seed]           karthik@healsync.com, anitha@healsync.com, ravi@healsync.com, sita@healsync.com")
