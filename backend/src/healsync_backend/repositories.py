"""Environment-aware repository construction."""
from __future__ import annotations

from .config import USE_FIRESTORE
from .db.firestore import FirestoreUserRepository
from .db.repositories.users import SQLiteUserRepository
from .db.repositories.patients import SQLitePatientRepository
from .db.sqlite import SQLiteDatabase
from .firebase import firestore_client


def user_repository():
    if USE_FIRESTORE:
        return FirestoreUserRepository(firestore_client())
    database = SQLiteDatabase()
    database.initialize()
    return SQLiteUserRepository(database)


def patient_repository():
    if USE_FIRESTORE:
        raise NotImplementedError("Firestore patient repository is the next migration slice")
    database = SQLiteDatabase()
    database.initialize()
    return SQLitePatientRepository(database)
