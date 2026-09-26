"""Idempotent local demo identities and sample clinical records."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .db.sqlite import SQLiteDatabase


def seed_sqlite(database: SQLiteDatabase) -> None:
    now = datetime.now(timezone.utc).isoformat()
    accounts = [
        ("dev:karthik@healsync.com", "karthik@healsync.com", "Karthik Subramanian", "patient"),
        ("dev:doctor@healsync.com", "doctor@healsync.com", "Dr. Meera Rao", "doctor"),
        ("dev:supplier@healsync.com", "supplier@healsync.com", "Apollo MedSupply", "supplier"),
    ]
    patient_accounts = [
        ("dev:patient1@healsync.com", "patient1@healsync.com", "Asha Patel", "patient", "Knee surgery", 14, 14, 100),
        ("dev:patient2@healsync.com", "patient2@healsync.com", "Ravi Kumar", "patient", "Hip replacement", 7, 14, 60),
        ("dev:patient3@healsync.com", "patient3@healsync.com", "Meera Singh", "patient", "Shoulder surgery", 10, 14, 75),
    ]
    user_ids: dict[str, str] = {}
    for uid, email, name, role in accounts:
        row = database.execute("SELECT id, role FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            database.execute(
                "UPDATE users SET firebase_uid = ?, name = ?, role = ? WHERE id = ?",
                (uid, name, role, row["id"]),
            )
            user_ids[email] = row["id"]
            continue
        user_id = str(uuid4())
        database.execute(
            "INSERT INTO users (id, firebase_uid, email, name, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, uid, email, name, role, now),
        )
        user_ids[email] = user_id
    for uid, email, name, role, surgery, day, total, confidence in patient_accounts:
        row = database.execute("SELECT id, role FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            database.execute(
                "UPDATE users SET firebase_uid = ?, name = ?, role = ? WHERE id = ?",
                (uid, name, role, row["id"]),
            )
            user_ids[email] = row["id"]
            continue
        user_id = str(uuid4())
        database.execute(
            "INSERT INTO users (id, firebase_uid, email, name, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, uid, email, name, role, now),
        )
        user_ids[email] = user_id

    doctor_id = user_ids["doctor@healsync.com"]
    doctor_profile = database.execute("SELECT id FROM doctor_profiles WHERE user_id = ?", (doctor_id,)).fetchone()
    if doctor_profile:
        doctor_profile_id = doctor_profile["id"]
    else:
        doctor_profile_id = str(uuid4())
        database.execute(
            "INSERT INTO doctor_profiles (id, user_id, specialty, license_verified) VALUES (?, ?, ?, 1)",
            (doctor_profile_id, doctor_id, "Orthopedic Surgery"),
        )

    patient_user_id = user_ids["karthik@healsync.com"]
    profile = database.execute("SELECT id FROM patient_profiles WHERE user_id = ?", (patient_user_id,)).fetchone()
    if profile:
        patient_id = profile["id"]
        database.execute(
            "UPDATE patient_profiles SET doctor_id = ?, surgery_type = ?, recovery_day = 14, recovery_total_days = 14, confidence_score = 100, location_lat = 13.0350, location_lng = 80.2450 WHERE id = ?",
            (doctor_profile_id, "Knee surgery", patient_id),
        )
    else:
        patient_id = str(uuid4())
        database.execute(
            """
            INSERT INTO patient_profiles
            (id, user_id, doctor_id, surgery_type, recovery_day, recovery_total_days, confidence_score, location_lat, location_lng)
            VALUES (?, ?, ?, 'Knee surgery', 14, 14, 100, 13.0350, 80.2450)
            """,
            (patient_id, patient_user_id, doctor_profile_id),
        )
    for uid, email, name, role, surgery, day, total, confidence in patient_accounts:
        user_id = user_ids[email]
        profile = database.execute("SELECT id FROM patient_profiles WHERE user_id = ?", (user_id,)).fetchone()
        if profile:
            patient_id2 = profile["id"]
            database.execute(
                "UPDATE patient_profiles SET doctor_id = ?, surgery_type = ?, recovery_day = ?, recovery_total_days = ?, confidence_score = ?, location_lat = ?, location_lng = ? WHERE id = ?",
                (doctor_profile_id, surgery, day, total, confidence, 13.0350 + (hash(email) % 100) / 10000, 80.2450 + (hash(email) % 100) / 10000, patient_id2),
            )
        else:
            patient_id2 = str(uuid4())
            database.execute(
                """
                INSERT INTO patient_profiles
                (id, user_id, doctor_id, surgery_type, recovery_day, recovery_total_days, confidence_score, location_lat, location_lng)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (patient_id2, user_id, doctor_profile_id, surgery, day, total, confidence, 13.0350 + (hash(email) % 100) / 10000, 80.2450 + (hash(email) % 100) / 10000),
            )

    if not database.execute("SELECT 1 FROM recovery_plan_items WHERE patient_id = ? LIMIT 1", (patient_id,)).fetchone():
        for time, title, description, category in [
            ("08:00 AM", "Amoxicillin 500mg", "1 capsule with food", "medicine"),
            ("01:00 PM", "High-protein recovery meal", "Supports tissue healing", "meal"),
            ("05:00 PM", "Guided mobility exercise", "15 min gentle stretching", "exercise"),
        ]:
            database.execute(
                """
                INSERT INTO recovery_plan_items (id, patient_id, day, time, title, description, category)
                VALUES (?, ?, 14, ?, ?, ?, ?)
                """,
                (str(uuid4()), patient_id, time, title, description, category),
            )
    database.execute(
        "UPDATE recovery_plan_items SET day = 14 WHERE patient_id = ? AND day < 14 AND title IN (?, ?, ?)",
        (patient_id, "Amoxicillin 500mg", "High-protein recovery meal", "Guided mobility exercise"),
    )

    if not database.execute("SELECT 1 FROM alerts WHERE patient_id = ? LIMIT 1", (patient_id,)).fetchone():
        database.execute(
            "INSERT INTO alerts (id, patient_id, severity, message, resolved, created_at) VALUES (?, ?, 'info', ?, 1, ?)",
            (str(uuid4()), patient_id, "Recovery plan completed. Patient reached 100% recovery milestone.", now),
        )

    supplier_user_id = user_ids["supplier@healsync.com"]
    if not database.execute("SELECT 1 FROM supplier_profiles WHERE user_id = ?", (supplier_user_id,)).fetchone():
        database.execute(
            "INSERT INTO supplier_profiles (id, user_id, business_name, location_lat, location_lng) VALUES (?, ?, ?, ?, ?)",
            (str(uuid4()), supplier_user_id, "Apollo MedSupply", 13.0604, 80.2496),
        )
    supplier_profile = database.execute("SELECT id FROM supplier_profiles WHERE user_id = ?", (supplier_user_id,)).fetchone()
    supplier_profile_id = supplier_profile["id"] if supplier_profile else None
    if supplier_profile_id:
        if not database.execute("SELECT 1 FROM inventory_items WHERE supplier_id = ? LIMIT 1", (supplier_profile_id,)).fetchone():
            items = [
                ("Paracetamol 500mg", 85, 0.8),
                ("Amoxicillin 500mg", 70, 1.2),
                ("Bandage sterile", 90, 0.5),
                ("Pain relief gel", 60, 2.5),
                ("Surgical dressing", 45, 3.0),
            ]
            for name, stock, price in items:
                database.execute(
                    "INSERT INTO inventory_items (id, supplier_id, name, stock_pct, unit_price) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid4()), supplier_profile_id, name, stock, price),
                )
        patient_ids = [row["id"] for row in database.execute("SELECT id FROM patient_profiles").fetchall()]
        if patient_ids:
            if not database.execute("SELECT 1 FROM orders LIMIT 1").fetchone():
                for i, patient_id in enumerate(patient_ids):
                    reference = f"ORD-{i+1:04d}"
                    items_json = '[{"name":"Paracetamol 500mg","qty":30},{"name":"Bandage sterile","qty":10}]'
                    total_amount = 30 * 0.8 + 10 * 0.5
                    status = "shipped" if i == 0 else "processing" if i == 1 else "delivered"
                    database.execute(
                        "INSERT INTO orders (id, reference, patient_id, supplier_id, items_json, total_amount, status, match_score, distance_km, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(uuid4()), reference, patient_id, supplier_profile_id, items_json, total_amount, status, 0.92, 3.5 + i, now),
                    )
    database.commit()