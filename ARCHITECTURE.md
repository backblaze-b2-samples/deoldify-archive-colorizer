<!-- last_verified: 2026-06-30 -->
# Architecture

DeOldify Archive Colorizer colorizes black-and-white archival footage with
DeOldify (NoGAN, fully local) and retains both originals and colorized
restorations in Backblaze B2. The primary entity is the `Restoration`.

## Components

- **apps/web/** — Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
  - Archival data-growth dashboard (originals vs restored bytes, growth ratio)
  - Restoration library (`archive/restored/`-scoped gallery) + detail/compare view
  - Create / re-colorize forms (selectors + the reused `generating-loader`)
  - Ingest (upload) of B&W masters to `archive/originals/`
  - Full bucket explorer (`/files`) over the whole bucket
  - Dark mode via `next-themes`
- **services/api/** — FastAPI backend (layered architecture)
  - REST API for the Restoration lifecycle + file upload/listing/deletion
  - B2 S3 integration via boto3
  - DeOldify colorization delegated over HTTP to the `infra/deoldify/` container via the `repo/deoldify_repo.py` adapter (no API key)
  - Optional denoise/sharpen restore pass (Pillow)
  - File metadata extraction (images, PDFs)
  - Health check, structured JSON logging, Prometheus-format metrics
- **infra/deoldify/** — DeOldify colorization microservice (FastAPI, CPU)
  - Runs the legacy fastai-v1/torch-1.11 stack, isolated in a native `linux/arm64` container
  - `POST /colorize` (image bytes → colorized PNG) and `GET /health`; stateless, no B2
- **packages/shared/** — TypeScript type definitions
  - Mirrors Pydantic models from the API (incl. `Restoration`, `RestorationStats`)
  - Consumed by `apps/web/` as workspace dependency

## Backend Layering

The API follows a strict layered architecture:

```
types/     Pydantic models — no logic, no imports from other layers
  |
config/    Settings (pydantic-settings) — depends only on types
  |
repo/      Data access (boto3 B2 client) — no business logic
  |
service/   Business logic — calls repo, returns types
  |
runtime/   FastAPI routes — calls service, never repo directly
```

### Layering Rules

1. Dependencies flow downward only: `types` -> `config` -> `repo` -> `service` -> `runtime`
2. No backward imports (e.g., service must not import from runtime)
3. `boto3` is only allowed in the `repo/` layer. The DeOldify model stack (`deoldify`, `torch`, `torchvision`, `fastai`, `imageio_ffmpeg`) is imported **nowhere** in this API — it runs in the `infra/deoldify/` container and the repo adapter reaches it over HTTP
4. All boundary data uses Pydantic models (no raw dicts across layers)
5. Each file stays under 300 lines

### Directory Structure

```
services/api/
  main.py                  App entrypoint, middleware, router registration
  app/
    types/                 Pydantic models (Restoration, RestorationStats, FileMetadata, ...)
    config/                Settings (B2_* env, archive prefixes, deoldify_service_url); endpoint from region
    repo/                  B2 S3 client + DeOldify HTTP adapter (data/model access layer)
      b2_client.py           boto3 client (custom UA, region->endpoint), object I/O
      deoldify_repo.py       DeOldify adapter — httpx client to the colorizer container (no ML imports)
    service/               Business logic (restoration lifecycle, restore pass, upload, files)
    runtime/               FastAPI route handlers (restorations, files, upload, health, metrics)
  tests/                   pytest tests (structural + integration + deoldify guard)
infra/deoldify/            Colorization microservice: Dockerfile, server.py, requirements.txt
```

## Boundary Invariants

- **No external SDK leakage**: `boto3` is only imported in `app/repo/`. The DeOldify model stack (`deoldify`, `torch`, `fastai`, `imageio_ffmpeg`) is imported **nowhere** in this API — it lives only in the `infra/deoldify/` container. The repo adapter reaches it over HTTP (`httpx`) and pulls in no ML SDK (verified by `tests/test_structure.py::test_deoldify_stack_not_imported_anywhere` and `tests/test_deoldify_repo.py`).
- **Colorization on CPU in-container**: colorization runs on CPU in the container (no GPU passthrough; DeOldify's legacy stack has no usable MPS path). `detect_device` reports the container's device via its `/health` probe and never hard-requires a GPU — if the service is unreachable it still reports CPU rather than raising.
- **No raw dicts at boundaries**: All data crossing layer boundaries uses typed Pydantic models.
- **No mutable globals**: Configuration is read-only after init. No module-level mutable state shared between layers.
- **Validated inputs**: All HTTP inputs validated by FastAPI/Pydantic. All file keys validated against prefix allowlist.

## Deployment

- **Local dev** — `pnpm dev` runs three processes via `concurrently`
  - Web: `localhost:3000`
  - API (host uvicorn): `localhost:8000`
  - DeOldify colorizer (Docker, `docker compose up --build deoldify`): `localhost:8137`
  - Requires a running Docker daemon (Colima on macOS); `scripts/dev.sh` prechecks it
- **Railway** — the web + API services from the same repo; the colorization service
  deploys from `infra/deoldify/` as its own `linux/arm64` container, reachable via `DEOLDIFY_SERVICE_URL`
  - See `infra/railway/README.md` for configuration

## Data Stores

- **Backblaze B2** — object storage (S3-compatible API), the sole data store
  - `archive/originals/<name>` — ingested B&W masters (Ingest page)
  - `archive/restored/<asset_id>/restored.{png,mp4}` — colorized rendition
  - `archive/restored/<asset_id>/metadata.json` — provenance + status (this IS the
    Restoration record; there is no application database)
  - Listing/metadata via S3 `list_objects_v2` / `head_object`; reads via `get_object`
  - Endpoint constructed from `B2_REGION` (`https://s3.{region}.backblazeb2.com`)

## External Services

- **Backblaze B2 S3 API** — storage, retrieval, deletion, presigned URLs (custom UA `deoldify-archive-colorizer`)
- **DeOldify colorization service** (`infra/deoldify/`) — NoGAN colorization over HTTP; no external API key. Runs the legacy fastai-v1/torch-1.11 stack on CPU in a native `linux/arm64` container. Model weights + resnet backbones are baked into the image at build time (no runtime download). Stateless and credential-free (never touches B2).

## Trust Boundaries

See [docs/SECURITY.md](docs/SECURITY.md) for full security documentation.

- **Frontend -> API** — CORS-restricted to configured origins. `CORSMiddleware` is registered LAST in `main.py` (outermost) so it wraps **every** response, including uncaught-exception 500s — otherwise the browser would block error responses and the UI would only see an opaque "network error". See [docs/RELIABILITY.md](docs/RELIABILITY.md#error-handling).
- **API -> B2** — authenticated via application keys, signature v4
- **Client -> B2** — presigned URLs for download (10-min expiry, forced attachment)

## Data Flows

- **Ingest**: Browser -> `POST /upload` (multipart) -> API validates -> repo writes to `archive/originals/` -> metadata extracted -> response
- **Create restoration**: Browser -> `POST /restorations` -> service fetches the source bytes from B2 (`get_object`) -> `deoldify_repo.colorize_image_bytes` POSTs them to the `infra/deoldify/` container (`POST /colorize`) which returns the colorized PNG -> optional restore pass (Pillow, in-API) -> repo writes `restored.png` + `metadata.json` to `archive/restored/<asset_id>/` -> Restoration returned
- **Re-colorize (run)**: `POST /restorations/<asset_id>/rerun` -> same source, new params -> overwrites the rendition
- **List restorations**: `GET /restorations` -> service reads each `metadata.json` under `archive/restored/`
- **Compare/preview**: `GET /restorations/<asset_id>/preview?target=source|rendition` -> presigned URL -> browser renders side by side
- **Delete restoration**: `DELETE /restorations/<asset_id>` -> deletes ONLY the rendition + metadata.json; the original master is retained
- **Dashboard**: `GET /restorations/stats` -> service aggregates originals vs restored bytes + counts

## Observability

- Structured JSON logging on all requests with `request_id`
- Request timing middleware (logs duration per request; also the catch-all that converts uncaught exceptions to a typed JSON 500)
- `/metrics` endpoint (Prometheus format: request count, latency, upload count)
- `/health` endpoint (B2 connectivity check)

## Canonical Files

- Restoration router: `services/api/app/runtime/restorations.py`
- Restoration business logic: `services/api/app/service/restoration.py`
- DeOldify HTTP adapter (model access): `services/api/app/repo/deoldify_repo.py`
- DeOldify colorization service: `infra/deoldify/server.py` (+ `Dockerfile`, `requirements.txt`)
- B2 data access (repo layer): `services/api/app/repo/b2_client.py`
- Pydantic models: `services/api/app/types/` (`restoration.py`, `files.py`, `upload.py`, `stats.py`)
- Config (pydantic-settings): `services/api/app/config/settings.py`
- Structural tests: `services/api/tests/test_structure.py`; DeOldify guard: `tests/test_deoldify_repo.py`
- Frontend API client: `apps/web/src/lib/api-client.ts`
- Shared TypeScript types: `packages/shared/src/types.ts`

## Core Features

- [Colorization (DeOldify, local)](docs/features/colorization.md)
- [Restore Pass](docs/features/restore-pass.md)
- [Restoration Library](docs/features/restoration-library.md)
- [Dashboard](docs/features/dashboard.md)
- [Ingest / File Upload](docs/features/file-upload.md)
- [Bucket Explorer](docs/features/file-browser.md)
- [Metadata Extraction](docs/features/metadata-extraction.md)

## References

- [docs/SECURITY.md](docs/SECURITY.md) — security principles and implementation
- [docs/RELIABILITY.md](docs/RELIABILITY.md) — reliability expectations
- [AGENTS.md](AGENTS.md) — architectural invariants and agent instructions
