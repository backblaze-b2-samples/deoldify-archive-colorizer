#!/bin/sh
# Pick a free API port (uvicorn won't auto-pick), wire CORS + the
# web-side API URL to whatever we landed on, then hand off to
# concurrently. Next.js handles its own port fallback natively.
#
# The DeOldify colorizer runs in a native linux/arm64 Docker container (the
# legacy fastai-v1/torch-1.11 stack can't live in the modern API's venv), so a
# running Docker daemon is required. We start it as a third concurrent process.
set -e

HERE="$(dirname "$0")"

# --- Docker precheck: the colorization service runs in a container ---
if ! docker info >/dev/null 2>&1; then
  printf '\n✗ Docker is required for the DeOldify colorization service.\n'
  printf '  Start it and retry — on macOS with Colima:  colima start\n\n'
  exit 1
fi

API_PORT="$(node "$HERE/pick-port.mjs" 8000)"

if [ "$API_PORT" != "8000" ]; then
  printf '\n⚠  API on http://localhost:%s (8000 was busy)\n\n' "$API_PORT"
fi

export API_PORT
export NEXT_PUBLIC_API_URL="http://localhost:$API_PORT"
# Where the API reaches the DeOldify colorization container.
export DEOLDIFY_SERVICE_PORT="${DEOLDIFY_SERVICE_PORT:-8137}"
export DEOLDIFY_SERVICE_URL="http://localhost:${DEOLDIFY_SERVICE_PORT}"
# Dev-only: accept any localhost:<port> origin so the web side works
# regardless of which port `next dev` lands on. Never set in prod.
export API_CORS_ORIGIN_REGEX='^http://localhost:[0-9]+$'

exec pnpm exec concurrently \
  --kill-others-on-fail \
  --names web,api,deoldify \
  --prefix-colors blue,green,magenta \
  "pnpm dev:web" "pnpm dev:api" "docker compose up --build deoldify"
