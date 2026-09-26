"""SQLite patient repository for the migrated patient API."""
from __future__ import annotations

from ..sqlite import SQLiteDatabase
from ...contracts import AlertRecord, PatientProfile, RecoveryItem


class SQLitePatientRepository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def get_by_user_id(self, user_id: str) -> PatientProfile | None:
        row = self.database.execute(
            """
            SELECT id, user_id, surgery_type, recovery_day, recovery_total_days,
                   confidence_score, location_lat, location_lng, doctor_id
            FROM patient_profiles WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        return PatientProfile(**dict(row)) if row else None

    def recovery_items(self, patient_id: str, day: int | None = None) -> list[RecoveryItem]:
        query = """
            SELECT id, patient_id, day, time, title, description, category, doctor_adjusted
            FROM recovery_plan_items WHERE patient_id = ?
        """
        params: list[object] = [patient_id]
        if day is not None:
            query += " AND day = ?"
            params.append(day)
        query += " ORDER BY day ASC, time ASC"
        return [RecoveryItem(**dict(row)) for row in self.database.execute(query, params).fetchall()]

    def alerts(self, patient_id: str) -> list[AlertRecord]:
        rows = self.database.execute(
            """
            SELECT id, patient_id, severity, message, resolved, created_at
            FROM alerts WHERE patient_id = ? ORDER BY created_at DESC
            """,
            (patient_id,),
        ).fetchall()
        return [AlertRecord(**dict(row)) for row in rows]


class FirestorePatientRepository:
    def __init__(self, client) -> None:
        self.client = client

    def get_by_user_id(self, user_id: str) -> PatientProfile | None:
        from ..firestore_data import records

        matches = records(self.client, "patient_profiles", user_id=user_id)
        if not matches:
            return None
        row = matches[0]
        return PatientProfile(
            id=row["id"],
            user_id=row["user_id"],
            surgery_type=row.get("surgery_type", ""),
            recovery_day=int(row.get("recovery_day", 1)),
            recovery_total_days=int(row.get("recovery_total_days", 14)),
            confidence_score=int(row.get("confidence_score", 90)),
            location_lat=float(row.get("location_lat", 0)),
            location_lng=float(row.get("location_lng", 0)),
            doctor_id=row.get("doctor_id"),
        )

    def recovery_items(self, patient_id: str, day: int | None = None) -> list[RecoveryItem]:
        from ..firestore_data import records

        items = records(self.client, "recovery_plan_items", patient_id=patient_id)
        if day is not None:
            items = [item for item in items if int(item.get("day", 0)) == day]
        items.sort(key=lambda item: (int(item.get("day", 0)), item.get("time", "")))
        return [
            RecoveryItem(
                id=item["id"],
                patient_id=item["patient_id"],
                day=int(item.get("day", 1)),
                time=item.get("time", ""),
                title=item.get("title", ""),
                description=item.get("description", ""),
                category=item.get("category", "checkup"),
                doctor_adjusted=bool(item.get("doctor_adjusted", False)),
            )
            for item in items
        ]

    def alerts(self, patient_id: str) -> list[AlertRecord]:
        from ..firestore_data import records

        alerts = records(self.client, "alerts", patient_id=patient_id)
        alerts.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return [
            AlertRecord(
                id=item["id"],
                patient_id=item["patient_id"],
                severity=item.get("severity", "info"),
                message=item.get("message", ""),
                resolved=bool(item.get("resolved", False)),
                created_at=item.get("created_at", ""),
            )
            for item in alerts
        ]
