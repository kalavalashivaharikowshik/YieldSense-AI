# YieldSense AI – Web App

React + Vite front end for YieldSense AI. It talks to the FastAPI backend in
`../backend`.

## Setup

```bash
cd web
npm install
cp .env.example .env   # then set VITE_API_BASE_URL
npm run dev            # http://localhost:5173
```

`VITE_API_BASE_URL` must point at the API **including** the `/api` prefix,
for example `http://localhost:8000/api`. The backend must list the web app's
origin in its `CORS_ORIGINS` setting.

## Scripts

| Command           | What it does                         |
| ----------------- | ------------------------------------ |
| `npm run dev`     | Start the development server         |
| `npm run build`   | Build the production bundle (`dist`) |
| `npm run preview` | Serve the production build locally   |
| `npm run lint`    | Run ESLint                           |

## Deployment

Pushing to `main` builds and deploys the site to Azure Static Web Apps
(`.github/workflows/azure-static-web-apps-*.yml`). The build reads
`VITE_API_BASE_URL` from the repository secret of the same name.
`public/staticwebapp.config.json` sends unknown paths to `index.html` so
React Router can handle them.
