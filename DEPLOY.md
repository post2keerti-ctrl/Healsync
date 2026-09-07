# Deploying HealSync API

I can't push a live server from this sandbox myself — the sandbox's network is locked
to package registries only (PyPI, npm, GitHub), it can't reach Google Cloud, Render,
or MongoDB Atlas. But the app is fully containerized and tested; below are exact,
copy-paste commands for the two most sensible options. Both get you a real public URL.

I already ran the full app end-to-end in this sandbox (auth, dashboard, document
upload → OCR → NLP → LLM pipeline, order matching, doctor plan approval, supplier
accept/decline, Dijkstra delivery routing) against the in-memory dev fallbacks —
everything below is the exact same code, just pointed at real services.

---

## Option A — Google Cloud Run (matches your architecture notes: "Cloud: Google Cloud")

**Prerequisites:** a Google Cloud project with billing enabled, and the `gcloud` CLI
installed locally (`gcloud` on your own machine, not in this sandbox).

```bash
# 1. Authenticate and set your project
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 2. Enable the required APIs (one-time)
gcloud services enable run.googleapis.com artifactregistry.googleapis.com

# 3. From inside the healsync_stack/ folder — build and deploy in one command.
#    Cloud Run builds the Dockerfile for you (Cloud Build) and gives you a public HTTPS URL.
gcloud run deploy healsync-api \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars "MONGODB_URI=<your Atlas URI>,MONGODB_DB_NAME=healsync,GOOGLE_MAPS_API_KEY=<your key>"

# 4. (Optional) attach Firebase Admin credentials as a secret instead of a plain env var:
gcloud secrets create firebase-service-account --data-file=firebase-service-account.json
gcloud run services update healsync-api \
  --update-secrets=/app/firebase-service-account.json=firebase-service-account:latest \
  --set-env-vars="FIREBASE_CREDENTIALS_PATH=/app/firebase-service-account.json"
```

`gcloud` prints your live URL at the end, e.g. `https://healsync-api-xxxxx.a.run.app`.
Test it immediately:
```bash
curl https://healsync-api-xxxxx.a.run.app/
```

**Since you're already in Antigravity / Firebase tooling:** Firebase Hosting can also
front this Cloud Run service directly (so your API lives under your Firebase project's
domain) — `firebase init hosting`, choose "Cloud Run" as the backend, point it at
`healsync-api`. Antigravity's Firebase integration can scaffold this rewrite for you
if you ask it to "connect Firebase Hosting to my Cloud Run service."

---

## Option B — Render.com (fastest path, free tier, no CLI needed)

1. Push this project to a GitHub repo.
2. Go to [render.com](https://render.com) → New → Blueprint → connect the repo.
   Render reads `render.yaml` (already included) and provisions the service automatically.
3. In the Render dashboard, fill in the secret env vars it prompts for:
   `MONGODB_URI`, `GOOGLE_MAPS_API_KEY` (leave blank to use fallbacks).
4. Click Deploy. Render builds the same `Dockerfile` and gives you a URL like
   `https://healsync-api.onrender.com`.

No `gcloud` install, no billing account needed to start — good for a quick demo link.

---

## Before you deploy: get your real credentials

The app works with zero configuration (every integration has a local fallback — see
`app/config.py`), but for a real deployment you'll want at least the database and auth
wired up for real:

### 1. MongoDB Atlas (5 min)
1. [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas) → free M0 cluster.
2. Database Access → add a user + password.
3. Network Access → Allow Access from Anywhere (`0.0.0.0/0`) for Cloud Run/Render, since
   they don't have static IPs on the free tier.
4. Connect → Drivers → copy the connection string into `MONGODB_URI`.

### 2. Firebase Authentication (5 min)
1. [console.firebase.google.com](https://console.firebase.google.com) → your project
   (or create one — this is the same project Antigravity/Firebase Studio scaffolds for you).
2. Build → Authentication → enable Email/Password (or whichever sign-in method your
   Flutter app uses).
3. Project Settings (gear icon) → Service Accounts → **Generate new private key** →
   downloads a JSON file. That's `FIREBASE_CREDENTIALS_PATH`.
4. Your Flutter app uses the Firebase client SDK to sign users in and gets an ID token;
   send that token to this API's `Authorization: Bearer <token>` header — no backend
   password handling needed.

### 3. Google Maps (2 min)
1. Google Cloud Console → APIs & Services → Library → enable **Distance Matrix API**.
2. Credentials → Create API key → restrict it to that API → set as `GOOGLE_MAPS_API_KEY`.

### 4. Llama 3 (optional — the template fallback is solid for a demo)
Cheapest real option: run Ollama on a small Cloud Run/Compute Engine instance or any
VPS — `curl -fsSL https://ollama.com/install.sh | sh && ollama pull llama3` — then set
`LLAMA_BASE_URL` to that machine's address.

---

## Deploying without any of the above

You don't have to configure anything to get a working public demo — every integration
degrades gracefully (see the `/` endpoint's `integrations` block to confirm what's
active). Deploying the container as-is with zero env vars still gives you a fully
functional API; it just uses mongomock (data resets on restart) and the dev-login
endpoint instead of real Firebase. That's a perfectly reasonable way to get a live demo
link fast, then swap in real credentials later without touching any code.
