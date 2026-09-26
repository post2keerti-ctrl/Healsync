"""Firebase Admin initialization shared by Auth, Firestore, and Storage."""
from __future__ import annotations

from functools import lru_cache
import os

import firebase_admin
from firebase_admin import auth, credentials, firestore, storage


@lru_cache(maxsize=1)
def initialize() -> firebase_admin.App:
    if firebase_admin._apps:
        return firebase_admin.get_app()
    bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
    options = {"storageBucket": bucket} if bucket else None
    return firebase_admin.initialize_app(options=options)


def verify_id_token(id_token: str) -> dict:
    initialize()
    return auth.verify_id_token(id_token)


def firestore_client():
    initialize()
    return firestore.client()


def storage_bucket():
    initialize()
    return storage.bucket()
