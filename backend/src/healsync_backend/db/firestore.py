"""Firestore repository implementation for Firebase-hosted production."""
from __future__ import annotations

from uuid import uuid4

from ..contracts import UserRecord


class FirestoreUserRepository:
    """Persist user profiles without allowing client-controlled role changes."""

    def __init__(self, client: object, collection: str = "users") -> None:
        self.collection = client.collection(collection)

    def get_by_firebase_uid(self, firebase_uid: str) -> UserRecord | None:
        matches = self.collection.where("firebase_uid", "==", firebase_uid).limit(1).stream()
        document = next(iter(matches), None)
        if document is None:
            return None
        data = document.to_dict()
        return UserRecord(id=document.id, firebase_uid=data["firebase_uid"], email=data["email"], name=data["name"], role=data["role"])

    def create_or_update(self, user: UserRecord) -> UserRecord:
        existing = self.get_by_firebase_uid(user.firebase_uid)
        if existing is not None and existing.role != user.role:
            raise ValueError("Changing an existing user's role requires an administrator")
        user_id = existing.id if existing else (user.id or str(uuid4()))
        self.collection.document(user_id).set(
            {"firebase_uid": user.firebase_uid, "email": user.email, "name": user.name, "role": user.role},
            merge=True,
        )
        return UserRecord(id=user_id, firebase_uid=user.firebase_uid, email=user.email, name=user.name, role=user.role)
