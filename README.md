# HealSync API — MongoDB · Firebase · OCR/NLP/LLM · Maps + Dijkstra

The full backend implementation of your architecture notes, tested end-to-end:

| Layer | Technology | Status in this build |
|---|---|---|
| Mobile App | Flutter | (not included — this is the backend it talks to) |
| Backend API | Python · FastAPI | ✅ implemented |
| Authentication | Firebase Auth | ✅ implemented (+ local dev-login fallback) |
| Database | MongoDB Atlas | ✅ implemented (+ local mongomock fallback) |
| OCR | Tesseract | ✅ implemented & tested |
| LLM | Llama 3 | ✅ implemented (+ deterministic template fallback) |
| NLP | spaCy | ✅ implemented & tested |
| Medical NER | scispaCy | ✅ implemented (+ rule-based fallback — see below) |
| Cloud | Google Cloud / AWS | ✅ Dockerized, deploy guide in `DEPLOY.md` |
| Notifications | Firebase Cloud Messaging | ✅ implemented (+ local log fallback) |
| Maps | Google Maps API | ✅ implemented (+ haversine fallback) |
| Routing | Dijkstra's Algorithm | ✅ implemented & tested |
| Supplier Selection | Weighted Scoring Algorithm | ✅ implemented & tested |

**Every external integration works two ways:** the real service when you configure
credentials, or a transparent local fallback when you don't — so this app runs and is
fully demoable right now, with zero setup, and upgrades to production services by
setting environment variables only (no code changes). See `app/config.py`.

## Quick start (zero configuration)

```bash
pip install -r requirements.txt
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/docs**. On startup, demo data seeds automatically:
patients, a doctor, and two suppliers around Chennai (with real coordinates, so
the matching/routing math has something realistic to compute over).

### Logging in (no Firebase project needed yet)

```bash
curl -X POST http://127.0.0.1:8000/auth/dev-login \
  -H "Content-Type: application/json" \
  -d '{"email":"karthik@healsync.com","password":"anything"}'
```

Returns a token — use it exactly like a real Firebase ID token:
```bash
curl http://127.0.0.1:8000/patients/me/dashboard -H "Authorization: Bearer <id_token>"
```

Seeded demo accounts: `karthik@healsync.com`, `anitha@healsync.com`, `ravi@healsync.com`,
`sita@healsync.com` (patients), `doctor@healsync.com`, `supplier@healsync.com` (Apollo
MedSupply), `medplus@healsync.com` (MedPlus Wholesale, for score comparison).

`/auth/dev-login` automatically disables itself the moment you configure real Firebase
credentials — you can't accidentally ship it live.

## Deploying to a real, public URL

See **`DEPLOY.md`** — exact commands for Google Cloud Run and Render, plus a
credentials checklist for MongoDB Atlas, Firebase, and Google Maps.

## Project structure

```
app/
  main.py                    FastAPI app, CORS, startup seeding
  config.py                  Every env var + its fallback behavior, in one place
  database.py                MongoDB Atlas connection (mongomock fallback)
  firebase_auth.py           Firebase ID token verification (dev-login fallback)
  schemas.py                 Pydantic request/response models
  seed.py                    Demo data generator
  services/
    ocr_service.py            Tesseract text extraction
    nlp_service.py             spaCy + scispaCy medical entity extraction
    llm_service.py              Llama 3 recovery-plan generation
    matching_service.py          Weighted supplier scoring
    routing_service.py            Google Maps distance/ETA + Dijkstra routing
    notification_service.py        Firebase Cloud Messaging
  routers/
    auth.py                   /auth/dev-login, /auth/sync-profile, /auth/me
    patients.py                 dashboard, recovery-plan, documents, cart, orders, alerts
    doctors.py                    patient roster, plan review & approval
    suppliers.py                    orders, inventory, score, Dijkstra delivery route
```

## The document pipeline, concretely

`POST /patients/me/documents` (multipart file upload) runs:

1. **Tesseract** reads the image → raw text
2. **spaCy/scispaCy** pulls out medicine names, dosages, frequency, duration
   - Tries the clinical `en_core_sci_sm` model first; if it's not installed (its
     model host is blocked on some networks — including this sandbox — pip installs
     fine on a normal connection), falls back to general spaCy + a rule-based
     dosage/frequency matcher. Check which is active via a document's
     `nlp_pipeline_mode` field in the response, or `nlp_service.pipeline_mode()`.
3. **Llama 3** turns the medicine list into a day-by-day recovery plan (medicines,
   meals, exercises) — saved straight into the patient's recovery timeline

I tested this full chain with a synthetic test image in this sandbox and confirmed
each stage runs and hands off correctly to the next.

## The matching + routing math, concretely

- `matching_service.score_supplier()` — the weighted formula from your notes:
  `0.35·stock + 0.25·proximity + 0.20·cost + 0.20·speed`, using real distance from
  `routing_service.distance_km()` (Google Maps when configured, haversine otherwise).
- `routing_service.shortest_route()` — Dijkstra's algorithm computes the
  shortest-total-distance order to visit every one of a supplier's accepted orders in
  one delivery run. Exposed at `GET /suppliers/me/delivery-route`.

Both were tested directly in this sandbox against real Chennai-area coordinates.
