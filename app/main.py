"""
HealSync API — entrypoint (stack-aligned build: MongoDB Atlas, Firebase Auth,
Tesseract OCR, spaCy/scispaCy NER, Llama 3, Google Maps + Dijkstra, weighted
supplier matching).

Run locally:
    uvicorn app.main:app --reload --port 8000

Docs:
    http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, seed
from .routers import auth, doctors, patients, suppliers

app = FastAPI(
    title="HealSync API",
    description=(
        "Post-surgical recovery coordination platform — MongoDB Atlas · Firebase Auth · "
        "Tesseract OCR · spaCy/scispaCy · Llama 3 · Google Maps + Dijkstra routing · "
        "weighted supplier matching."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your real frontend domain(s) in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(doctors.router)
app.include_router(suppliers.router)


@app.on_event("startup")
def on_startup():
    seed.run()


@app.get("/api-info", tags=["Health"])
def root():
    return {
        "status": "ok",
        "service": "HealSync API",
        "docs": "/docs",
        "integrations": {
            "mongodb": "Atlas (real)" if config.USE_REAL_MONGO else "mongomock (local dev)",
            "firebase_auth": "Firebase Admin SDK (real)" if config.USE_REAL_FIREBASE else "dev-login fallback",
            "google_maps": "Google Maps API (real)" if config.USE_REAL_MAPS else "haversine fallback",
            "llama3": "Ollama/Llama 3 (real)" if config.USE_REAL_LLM else "template fallback",
        },
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}


app.mount("/", StaticFiles(directory="app/static", html=True), name="frontend")
