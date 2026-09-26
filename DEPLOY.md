# HealSync production deployment

The frontend is hosted on Vercel. The FastAPI service runs on Cloud Run and stores
application data in Firestore; prescription originals are stored in Cloud Storage.
Do not deploy the local SQLite database, uploads folder, or `.env` files.

## 1. Prepare Google Cloud

Use a Google Cloud project with billing enabled and the `gcloud` CLI:

```powershell
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com
gcloud firestore databases create --database="(default)" --location=asia-south1 --type=firestore-native
```

Create a Cloud Storage bucket in the same project, and record its bucket name:

```powershell
gcloud storage buckets create gs://YOUR_PROJECT_ID.firebasestorage.app --location=asia-south1
```

Grant the Cloud Run runtime service account access to Firestore and uploaded files:

```powershell
$PROJECT_NUMBER = gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)"
$RUNTIME_SA = "$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID --member="serviceAccount:$RUNTIME_SA" --role="roles/datastore.user"
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID --member="serviceAccount:$RUNTIME_SA" --role="roles/storage.objectAdmin"
```

Deploy from the repository root. The runtime uses Application Default Credentials;
never commit a service-account key:

```powershell
gcloud run deploy healsync-api `
  --source backend `
  --region asia-south1 `
  --allow-unauthenticated `
  --port 8080 `
  --set-env-vars "ENVIRONMENT=production,USE_FIRESTORE=true,ENABLE_DEV_AUTH=false,FIRESTORE_COLLECTION_PREFIX=healsync,FIREBASE_STORAGE_BUCKET=YOUR_PROJECT_ID.firebasestorage.app,ALLOWED_ORIGINS=https://YOUR_VERCEL_DOMAIN"
```

The command prints the API URL. Check `https://YOUR_CLOUD_RUN_URL/health`; it should
report `healthy` and `firestore`.

## 2. Prepare Firebase Authentication

In Firebase Console for the same Google Cloud project:

1. Enable Email/Password under Authentication sign-in providers.
2. Create the user accounts that should be allowed to sign in. Seeded sample account
   emails are `karthik@healsync.com`, `doctor@healsync.com`, `supplier@healsync.com`,
   `patient1@healsync.com`, `patient2@healsync.com`, and `patient3@healsync.com`.
3. Set account passwords through Firebase Console or Firebase's password-reset
   workflow. The application does not enable production demo-password login.

The API seeds non-sensitive sample profiles, inventory, orders, plans, and alerts in
Firestore at startup. A verified Firebase account is linked to its seeded profile by
email. Only use synthetic data in these demo profiles.

## 3. Deploy the frontend on Vercel

1. Import `post2keerti-ctrl/HealSync-app` into Vercel and grant Vercel access to the
   private repository.
2. Set the Vercel project Root Directory to `frontend`.
3. Use the Vite preset, build command `npm run build`, and output directory `dist`.
4. Set these environment variables for Production (and Preview if desired):
   - `VITE_API_BASE_URL=https://YOUR_CLOUD_RUN_URL/api/v1`
   - `VITE_FIREBASE_API_KEY` (Firebase web API key)
   - `VITE_FIREBASE_AUTH_DOMAIN`
   - `VITE_FIREBASE_PROJECT_ID`
   - `VITE_FIREBASE_STORAGE_BUCKET`
   - `VITE_FIREBASE_MESSAGING_SENDER_ID`
   - `VITE_FIREBASE_APP_ID`
5. Redeploy the frontend after saving the variables.
6. Set Cloud Run `ALLOWED_ORIGINS` to the exact Vercel production domain and redeploy
   the API. Include the custom domain too if one is added.

Firebase web configuration is client configuration, not an Admin credential. Never
put Firebase service-account JSON or private keys into Vercel `VITE_` variables.
The Cloud Run service uses its attached Google service account for Firestore and
Storage access.

## Persistence and availability notes

- Firestore and Cloud Storage persist across backend restarts and scale events.
- Cloud Run may scale to zero, so the first request after inactivity can be slower.
  Use a paid minimum-instance setting if a warm response is required continuously.
- Vercel deploys on pushes to the connected branch. Keep build/runtime secrets in the
  provider dashboards, never in the Git repository.
- Configure billing alerts and quotas in Google Cloud before sharing the app publicly.
