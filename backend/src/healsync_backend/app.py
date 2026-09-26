"""Application factory for local Uvicorn and Firebase Functions."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import ALLOWED_ORIGINS, LOCAL_DEV_ORIGIN_REGEX, USE_FIRESTORE


def create_app() -> FastAPI:
    app = FastAPI(title="HealSync API", version="3.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_origin_regex=LOCAL_DEV_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    from .routes import router
    app.include_router(router)
    from .patient_routes import router as patient_router
    app.include_router(patient_router)
    from .doctor_routes import router as doctor_router
    app.include_router(doctor_router)

    if USE_FIRESTORE:
        from .db.firestore_data import seed_firestore
        from .firebase import firestore_client
        seed_firestore(firestore_client())
    else:
        from .db.sqlite import SQLiteDatabase
        from .seed import seed_sqlite
        database = SQLiteDatabase()
        database.initialize()
        seed_sqlite(database)
        database.close()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy", "storage": "firestore" if USE_FIRESTORE else "sqlite"}

    return app
