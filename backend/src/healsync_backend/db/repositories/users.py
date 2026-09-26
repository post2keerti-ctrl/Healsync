"""SQLite user repository used by local backend runs and tests."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ...contracts import UserRecord
from ..sqlite import SQLiteDatabase


class SQLiteUserRepository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def get_by_firebase_uid(self, firebase_uid: str) -> UserRecord | None:
        row = self.database.execute(
            "SELECT id, firebase_uid, email, name, role FROM users WHERE firebase_uid = ?",
            (firebase_uid,),
        ).fetchone()
        if row is None:
            return None
        return UserRecord(**dict(row))

    def get_by_email(self, email: str) -> UserRecord | None:
        row = self.database.execute(
            "SELECT id, firebase_uid, email, name, role FROM users WHERE email = ?",
            (email.lower(),),
        ).fetchone()
        return UserRecord(**dict(row)) if row else None

    def create_or_update(self, user: UserRecord) -> UserRecord:
        existing = self.get_by_firebase_uid(user.firebase_uid)
        if existing is None:
            existing = self.get_by_email(user.email)
            if existing is not None and existing.role != user.role:
                raise ValueError("Changing an existing user's role requires an administrator")
        if existing is not None and existing.role != user.role:
            raise ValueError("Changing an existing user's role requires an administrator")
        user_id = existing.id if existing else user.id or str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        if existing is not None:
            self.database.execute(
                "UPDATE users SET firebase_uid = ?, email = ?, name = ?, role = ? WHERE id = ?",
                (user.firebase_uid, user.email, user.name, user.role, user_id),
            )
            self.database.commit()
            return UserRecord(id=user_id, firebase_uid=user.firebase_uid, email=user.email, name=user.name, role=user.role)
        self.database.execute(
            """
            INSERT INTO users (id, firebase_uid, email, name, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(firebase_uid) DO UPDATE SET email=excluded.email, name=excluded.name
            """,
            (user_id, user.firebase_uid, user.email, user.name, user.role, now),
        )
        self.database.commit()
        return UserRecord(id=user_id, firebase_uid=user.firebase_uid, email=user.email, name=user.name, role=user.role)
