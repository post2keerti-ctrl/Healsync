"""Persistence contracts shared by SQLite and Firestore adapters.

Routers and services should depend on these typed boundaries rather than a
specific database SDK. The first contract covers identity records and is the
pattern for the remaining domain repositories.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class UserRecord:
    id: str
    firebase_uid: str
    email: str
    name: str
    role: str


@dataclass(frozen=True)
class PatientProfile:
    id: str
    user_id: str
    surgery_type: str
    recovery_day: int
    recovery_total_days: int
    confidence_score: int
    location_lat: float
    location_lng: float


@dataclass(frozen=True)
class RecoveryItem:
    id: str
    patient_id: str
    day: int
    time: str
    title: str
    description: str
    category: str
    doctor_adjusted: bool


@dataclass(frozen=True)
class AlertRecord:
    id: str
    patient_id: str
    severity: str
    message: str
    resolved: bool
    created_at: str


class UserRepository(Protocol):
    def get_by_firebase_uid(self, firebase_uid: str) -> UserRecord | None:
        """Return the local profile for a verified Firebase identity."""

    def create_or_update(self, user: UserRecord) -> UserRecord:
        """Persist a profile without allowing arbitrary role escalation."""


class PatientRepository(Protocol):
    def get_by_user_id(self, user_id: str) -> PatientProfile | None: ...

    def recovery_items(self, patient_id: str, day: int | None = None) -> list[RecoveryItem]: ...

    def alerts(self, patient_id: str) -> list[AlertRecord]: ...
