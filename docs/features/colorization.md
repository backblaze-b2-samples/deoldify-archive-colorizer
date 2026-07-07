<!-- last_verified: 2026-06-30 -->
# Feature: Colorization (DeOldify, local)

## Purpose
Colorize black-and-white archival stills with DeOldify's NoGAN deep-learning model, fully on-device — the marquee feature.

## Used By
- UI: `/restorations/new` (create) and the Re-colorize action on `/restorations/<asset_id>`
- API: `POST /restorations`, `POST /restorations/<asset_id>/rerun`
- Model: DeOldify (NoGAN) — `jantic/DeOldify`, Artistic + Stable image models (still images only; the Video model is not exposed)

## Core Functions
- `services/api/app/repo/deoldify_repo.py` — the HTTP adapter: `detect_device()` (probes the service `/health`) and `colorize_image_bytes()` (POSTs image bytes to the service). Pulls in **no** ML SDK — the model stack lives only in the container.
- `infra/deoldify/server.py` — the colorization microservice (FastAPI, CPU): builds + caches one DeOldify colorizer per variant, exposes `GET /health` and `POST /colorize`.
- `services/api/app/service/restoration.py` — `create_restoration()`, `rerun_restoration()` orchestration
- `apps/web/src/components/restorations/restoration-form.tsx` — selector-based params form

## Inputs
- source_key: string (an object under `archive/originals/`)
- params.model_variant: artistic | stable (Select)
- params.render_quality: draft (16) | balanced (22) | high (24) (Select → render factor). The effective render_factor is additionally clamped per variant — **stable is memory-capped at 22** (its heavier resnet101 OOM-crashes at 24 on the CPU container), artistic keeps 24 — so no selectable variant×preset combo can OOM-kill the colorizer on a 4 GiB budget. See RELIABILITY.md.
- params.denoise / params.sharpen: bool (Switch)

## Outputs
- `archive/restored/<asset_id>/restored.png` — colorized rendition (B2 PutObject)
- `archive/restored/<asset_id>/metadata.json` — provenance + status
- Returns a `Restoration` with `status` (`completed` / `failed`), `device`, `render_factor`, model version

## Flow
- Service fetches the source bytes from B2 (`get_object`)
- `colorize_image_bytes()` POSTs the bytes (multipart `file` + `variant` + `render_factor`) to the colorization service's `POST /colorize`; the service builds/caches the DeOldify colorizer for the variant and returns the colorized PNG on CPU
- Optional restore pass (denoise/sharpen, Pillow, in-API) is applied to the colorized output
- Rendition + metadata.json are written to B2

## Device (deployment: container)
- Colorization runs on **CPU inside the `infra/deoldify/` container** — no GPU passthrough; DeOldify's legacy stack has no usable Apple MPS path.
- `detect_device()` reports the container's device by probing its `/health`; it never hard-requires a GPU and returns CPU (with a "service unavailable" label) if the service is unreachable, rather than raising.

## Dependency notes
- The DeOldify / torch-1.11 / fastai-1.0.60 stack is **pinned** in `infra/deoldify/requirements.txt` and installed in ordered layers by `infra/deoldify/Dockerfile` (fastai `--no-deps`; numpy held < 2 via `constraints.txt`). It is irreconcilable with this API's modern fastai-2 / torch-2 / Python-3.11 env, which is why it runs in its own container. This API imports **no** ML SDK at all.
- Model weights (`ColorizeArtistic_gen.pth` ~243 MB, `ColorizeStable_gen.pth` ~833 MB) and the resnet backbones are baked into the image at build time, so there is no download at request time.
- The container is **native `linux/arm64` only** (torch amd64 wheels `SIGILL` under QEMU on Apple silicon) and is stateless / credential-free (never touches B2).

## Edge Cases
- Source not under `archive/originals/` → 400
- Source not found → 404
- Video source in the synchronous flow → 400 (heavier path; see tech-debt-tracker)
- Model failure → `metadata.json` is still written with `status="failed"` and the error, so the asset is visible and inspectable; no rendition is uploaded

## UX States
- Loading: the reused `generating-loader` shows "Colorizing…" while the POST is in flight
- Empty (create): no originals ingested → prompt to ingest
- Error: toast with the failure detail; the failed restoration is still listed

## Verification
- Test files: `services/api/tests/test_deoldify_repo.py` (import/signature + HTTP-contract guard, network fully stubbed), `services/api/tests/test_restorations.py` (lifecycle with the colorize call stubbed)
- The guard test asserts the adapter imports without pulling torch/deoldify/fastai, the public API + signatures are stable, `colorize_image_bytes()` POSTs to the service and maps errors to `RuntimeError`, and `detect_device()` never raises — true end-to-end colorization is validated against the running container by the verify pipeline step (not in the unit suite, to keep it fast/deterministic)
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: all pytest tests green; structural test confirms the DeOldify model stack is imported nowhere in the API (it lives only in `infra/deoldify/`)

## Related Docs
- [Restore Pass](restore-pass.md)
- [Restoration Library](restoration-library.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
