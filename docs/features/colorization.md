<!-- last_verified: 2026-06-30 -->
# Feature: Colorization (DeOldify, local)

## Purpose
Colorize black-and-white archival stills with DeOldify's NoGAN deep-learning model, fully on-device — the marquee feature.

## Used By
- UI: `/restorations/new` (create) and the Re-colorize action on `/restorations/<asset_id>`
- API: `POST /restorations`, `POST /restorations/<asset_id>/rerun`
- Model: DeOldify (NoGAN) — `jantic/DeOldify`, Artistic + Stable image models (Video model for clips)

## Core Functions
- `services/api/app/repo/deoldify_repo.py` — the adapter: `detect_device()`, `ensure_weights()`, `colorize_image_bytes()`. ONLY place `deoldify`/`torch`/`fastai` import.
- `services/api/app/repo/deoldify_runtime.py` — heavy model invocation, lazily imported (keeps the adapter import network-free)
- `services/api/app/service/restoration.py` — `create_restoration()`, `rerun_restoration()` orchestration
- `apps/web/src/components/restorations/restoration-form.tsx` — selector-based params form

## Inputs
- source_key: string (an object under `archive/originals/`)
- params.model_variant: artistic | stable | video (Select)
- params.render_quality: draft (21) | balanced (30) | high (35) (Select → render factor)
- params.denoise / params.sharpen: bool (Switch)

## Outputs
- `archive/restored/<asset_id>/restored.png` — colorized rendition (B2 PutObject)
- `archive/restored/<asset_id>/metadata.json` — provenance + status
- Returns a `Restoration` with `status` (`completed` / `failed`), `device`, `render_factor`, model version

## Flow
- Service fetches the source bytes from B2 (`get_object`)
- `colorize_image_bytes()` ensures the variant's weights are present (downloads ~250 MB to a gitignored `models/` dir on first run), then runs the model on the auto-detected device
- Optional restore pass (denoise/sharpen) is applied to the colorized output
- Rendition + metadata.json are written to B2

## Device selection (deployment: local)
- Auto-detect: **CUDA → Apple MPS → CPU**, default **CPU**. Never hard-requires a GPU.
- DeOldify rides an older fastai/torch stack with weak MPS support → MPS is best-effort; if a colorizer build fails on MPS the runtime falls back **CUDA → CPU** rather than crashing.

## Dependency notes
- The DeOldify/torch/fastai stack is **pinned** in `services/api/requirements-ml.txt` (separate from core deps). Unpinned ML deps are a false-green: the API boots and tests pass but the model load fails on a fresh clone.
- torch >= 2.x defaults `torch.load(weights_only=True)`, which refuses DeOldify's legacy pickled `.pth` weights. `_patch_torch_load_for_legacy_weights()` forces `weights_only=False` and registers safe globals before each model load.
- MP4 encoding (video path) uses the bundled `imageio-ffmpeg` binary, not bare system `ffmpeg`.

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
- Test files: `services/api/tests/test_deoldify_repo.py` (no-network signature/import guard), `services/api/tests/test_restorations.py` (lifecycle with model stubbed)
- The guard test asserts the adapter imports without pulling torch/deoldify, the public API + signatures are stable, and `detect_device()` returns cuda/mps/cpu — true end-to-end colorization is validated by the later verify pipeline step (not in the unit suite, to keep it fast/deterministic)
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: all pytest tests green; structural test confirms deoldify/torch/fastai confined to `repo/`

## Related Docs
- [Restore Pass](restore-pass.md)
- [Restoration Library](restoration-library.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
