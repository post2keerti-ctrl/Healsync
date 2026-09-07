"""
MongoDB Atlas connection.

If MONGODB_URI is set (a real Atlas connection string), we connect to it
with pymongo exactly as you would in production. If it is NOT set, we
transparently swap in `mongomock` — an in-memory Mongo-compatible engine —
so the whole API still runs for local development without needing a real
cluster. The application code above this layer never knows the difference;
it just calls collection methods (`insert_one`, `find`, etc.) normally.
"""
from bson import ObjectId

from . import config

if config.USE_REAL_MONGO:
    from pymongo import MongoClient
    client = MongoClient(config.MONGODB_URI)
    print(f"[database] Connected to real MongoDB Atlas: db={config.MONGODB_DB_NAME}")
else:
    import mongomock
    client = mongomock.MongoClient()
    print("[database] MONGODB_URI not set — using in-memory mongomock for local development.")

db = client[config.MONGODB_DB_NAME]

# Collections — mirrors the entities in the recovery-coordination domain
users = db["users"]                       # {firebase_uid, name, email, role}
patient_profiles = db["patient_profiles"]  # {user_id, doctor_id, surgery_type, recovery_day, ...}
doctor_profiles = db["doctor_profiles"]
supplier_profiles = db["supplier_profiles"]
recovery_plan_items = db["recovery_plan_items"]
documents = db["documents"]
inventory_items = db["inventory_items"]
orders = db["orders"]
alerts = db["alerts"]
notifications = db["notifications"]        # log of pushes sent (real FCM or local fallback)


def oid(id_str: str) -> ObjectId:
    """Convert a string id from the API into a Mongo ObjectId, with a clear error if invalid."""
    try:
        return ObjectId(id_str)
    except Exception:
        raise ValueError(f"'{id_str}' is not a valid document id")


def to_str_id(doc: dict) -> dict:
    """Replace Mongo's `_id` (ObjectId) with a plain string `id` field for JSON responses."""
    if doc is None:
        return doc
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc
