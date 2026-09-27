# Free demo deployment

This setup uses Vercel Free for the frontend and a Render Free web service for the
API. It does not require a Google Cloud billing account. It is for the seeded,
synthetic demo data only.

## Limitations

- Render's free API service can spin down when idle, so its first request may be
  slow. Free quotas and provider terms can change.
- The API uses local SQLite and the container's temporary filesystem. Changes and
  uploaded document files can be lost when Render restarts or redeploys; the
  synthetic sample data is seeded again at startup.
- Demo accounts use the shared password `demo`. Anyone who can reach the app can
  access the synthetic demo workspaces. Do not add real patient or other private
  information.
- Free plans are not an always-on or production data-storage guarantee.

## Deploy the frontend

1. Sign in to Vercel and import the private `post2keerti-ctrl/HealSync-app`
   repository.
2. Set the project root directory to `frontend`, the framework preset to Vite, the
   build command to `npm run build`, and the output directory to `dist`.
3. Deploy once and copy the Vercel origin, such as `https://your-app.vercel.app`.
   Firebase environment variables are not required for the demo login.

## Deploy the API

1. Sign in to Render and create a Blueprint instance from the same GitHub repository,
   using the checked-in `render.yaml`.
2. When prompted for `ALLOWED_ORIGINS`, enter the exact Vercel origin copied above
   (scheme and hostname only; no path or trailing slash).
3. Deploy the `healsync-demo-api` service. Render generates a private JWT signing
   secret for it; do not replace it with a value committed to Git.
4. Open `https://YOUR_RENDER_SERVICE.onrender.com/health`. The response should
   report `"status":"healthy"` and `"storage":"sqlite"`.

## Connect the frontend and verify

1. In Vercel project settings, add the Production environment variable
   `VITE_API_BASE_URL=https://YOUR_RENDER_SERVICE.onrender.com/api/v1`.
2. Redeploy the frontend so Vite includes the API URL in the build.
3. Open the Vercel URL, select a role, and sign in with the prefilled email and
   password `demo`. Check the dashboard, orders, inventory, patient documents,
   and doctor alerts.

Do not put passwords, API keys, or service-account credentials in this repository.
This demo deployment does not use Firestore or durable file storage.
