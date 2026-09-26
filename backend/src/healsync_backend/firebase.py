"""Firebase Admin initialization shared by Auth, Firestore, and Storage."""
from __future__ import annotations

from functools import lru_cache

import firebase_admin
from firebase_admin import auth, credentials, firestore, storage


@lru_cache(maxsize=1)
def initialize() -> firebase_admin.App:
    if firebase_admin._apps:
        return firebase_admin.get_app()
    return firebase_admin.initialize_app(options={"storageBucket": None})


def verify_id_token(id_token: str) -> dict:
    initialize()
    return auth.verify_id_token(id_token)


def firestore_client():
    initialize()
    return firestore.client()


def storage_bucket():
    initialize()
    return storage.bucket()
