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
                   confidence_score, location_lat, location_lng
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
