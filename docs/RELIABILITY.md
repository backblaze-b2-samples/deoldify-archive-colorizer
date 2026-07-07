<!-- last_verified: 2026-06-25 -->
# Reliability

Reliability expectations and practices for this project.

## Health Checks

- `GET /health` verifies B2 connectivity and returns `healthy` or `degraded`
- Health endpoint is always available, even when B2 is down

## Error Handling

- HTTP handlers return structured error responses with appropriate status codes
- External service failures (B2) are caught and surfaced as 500/503 responses
- No unhandled exceptions leak stack traces to clients
- Uncaught exceptions are converted to a typed JSON 500 (`{"detail": "Internal server error"}`, modeled by `app.types.ErrorResponse`) by the catch-all in `timing_middleware`
- **Error responses carry CORS headers.** `CORSMiddleware` is registered LAST in `main.py` so it is the outermost middleware and wraps every response — including uncaught-exception 500s produced by the inner catch-all. This is intentional and load-bearing: if a 500 shipped without `Access-Control-Allow-Origin`, the browser would block it and the frontend would surface only an opaque "network error", hiding the real server bug. Regression-guarded by `tests/test_error_handling.py::test_unhandled_exception_500_carries_cors_headers`.

## Logging

- Structured JSON logging via Python stdlib
- Every request gets a `request_id` for tracing
- Log levels: ERROR for failures, WARNING for degraded state, INFO for requests

## Observability

- Request timing middleware logs duration for every request
- `/metrics` endpoint exposes basic Prometheus-format counters
- Upload success/failure counts tracked

## Graceful Degradation

- File listing returns empty list (not error) when B2 has no objects
- Metadata extraction failures don't block upload (return partial metadata)
- Frontend shows skeleton states while loading, error states on failure
- If the colorizer service is unreachable, `detect_device()` still returns a CPU `DeviceInfo` (never raises), and a failed colorize is persisted as a `status="failed"` restoration (with the error) so the asset stays visible/inspectable rather than crashing the request

## Colorizer Memory Budget (OOM safety)

DeOldify renders internally at `render_factor * 16` px, and the model's
forward-pass activations scale with that area — so **peak container RAM is
driven by `render_factor` and by the model variant** (the heavier `stable`
resnet101 peaks higher than `artistic` resnet34 at the same factor), **not by
the input image size**. On the default ~4 GiB Colima VM, `render_factor` ≥ 28
exceeds the budget for either variant, and **`stable` alone already OOMs at
`render_factor` 24** (the "High" preset) even on a single still. An OOM
**kills** the colorizer container via the Linux kernel (SIGKILL, exit 137),
which is restarted by `restart: unless-stopped`; to the API this shows up as a
`RemoteProtocolError` ("Server disconnected without sending a response").

Mitigations in place:

- The UI render-quality presets map to `render_factor` — Draft / Balanced /
  High → **16 / 22 / 24** — and the effective factor is then **clamped per
  variant** to that variant's proven-safe ceiling: **artistic ≤ 24, stable ≤ 22**
  (`VARIANT_MAX_RENDER_FACTOR` in `deoldify_repo.py`). So the otherwise-crashing
  **stable + High** combo renders at 22, and **no selectable variant×preset
  combo (including the default and "High") can OOM the service** on a 4 GiB
  budget. The clamp is resolved in `create_restoration()`
  (`services/api/app/service/restoration.py`) **before** the render, so the
  `render_factor` recorded in each restoration's `metadata.json` provenance is
  exactly the factor that ran. Presets live in `_RENDER_FACTORS` there,
  mirrored by `RENDER_PRESETS` in `deoldify_repo.py`.
- `colorize_image_bytes()` maps the disconnect signature to an actionable
  `RuntimeError` ("…likely ran out of memory. Try a lower render quality…")
  instead of the raw transport error.

To render at higher factors, raise the VM memory first (`colima start
--memory 8`) and only then raise the presets and the per-variant ceilings
(`VARIANT_MAX_RENDER_FACTOR`). See README → *Compute*.

## Deployment

- Railway health checks on `/health`
- Zero-downtime deploys via rolling updates
- Environment-specific configuration via env vars (no config files in prod)
