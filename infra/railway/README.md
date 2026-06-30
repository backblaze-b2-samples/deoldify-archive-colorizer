# Railway Deployment — deoldify-archive-colorizer

Deploy both services (web + api) on Railway.

> Note: DeOldify colorization is CPU/GPU-intensive and downloads ~250 MB of
> model weights on first run. Railway's web tier is fine for the UI, but for
> real colorization throughput prefer a GPU-backed host (or run the API
> locally). See the colorization feature doc for device auto-detect details.

## Setup

1. Create a new Railway project
2. Add two services from the same repo:

### Web Service (Next.js)
- **Root Directory**: `apps/web`
- **Build Command**: `pnpm install && pnpm build`
- **Start Command**: `pnpm start`
- **Port**: `3000`

### API Service (FastAPI)
- **Root Directory**: `services/api`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Environment Variables

Set these on the API service:

| Variable | Value |
|----------|-------|
| `B2_APPLICATION_KEY_ID` | Your B2 application key ID |
| `B2_APPLICATION_KEY` | Your B2 application key |
| `B2_BUCKET_NAME` | Your bucket name |
| `B2_REGION` | Your B2 region (e.g., `us-west-004`) — the S3 endpoint is derived from this |
| `B2_PUBLIC_URL_BASE` | (optional) Public base URL for object links |
| `API_CORS_ORIGINS` | Your web service URL (e.g., `https://web-production-xxx.up.railway.app`) |

Set this on the Web service:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | Your API service URL (e.g., `https://api-production-xxx.up.railway.app`) |
