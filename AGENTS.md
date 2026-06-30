<!-- last_verified: 2026-06-30 -->
# AGENTS.md

This is the authoritative control surface for all coding agents. Read this first.

This app — **DeOldify Archive Colorizer** — colorizes black-and-white archival
footage with DeOldify (NoGAN, fully local, no external API key) and retains both
originals and colorized restorations in Backblaze B2. The primary entity is the
**`Restoration`** (one B&W source original + its colorized rendition + provenance
metadata, persisted under `archive/restored/<asset_id>/`).

## 1. Repository Map

```
apps/web/          Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
  src/app/restorations/        Restoration library + create + detail/compare pages
  src/components/restorations/ Restoration UI (form, library, detail, thumbnails)
  src/components/dashboard/    Archival data-growth metrics
services/api/      FastAPI backend (layered: types/config/repo/service/runtime)
  app/repo/deoldify_repo.py    DeOldify adapter — ONLY place deoldify/torch/fastai import
  app/repo/deoldify_runtime.py Heavy model invocation + MP4 encode (lazily imported)
  app/repo/b2_client.py        boto3 S3 client (custom UA, region->endpoint)
  app/service/restoration.py   Restoration lifecycle business logic
  app/service/restore_pass.py  Denoise/sharpen post-process (Pillow, pure)
  app/runtime/restorations.py  Restoration router
  requirements-ml.txt          PINNED DeOldify/torch/fastai stack (separate install)
packages/shared/   Shared TypeScript types
docs/              System of record (features, workflows, security, reliability)
docs/exec-plans/   Execution plans and tech debt tracker
infra/railway/     Deployment config
```

## 2. App surfaces (kept starter scaffolding + this app's features)

**Kept from the starter (do not strip, rename, or replace)**
- **UI kit / design system.** `apps/web/src/components/ui/` (shadcn primitives), the design tokens in `apps/web/src/app/globals.css`, and the `/design` reference page. Build new screens with these primitives; never edit the generated `components/ui/` files directly. The `generating-loader` is reused for the "colorizing…" state.
- **Full bucket explorer.** `/files` route, `apps/web/src/app/files/`, and `apps/web/src/components/files/`. This is the raw B2 surface that shows *every* object (originals + restored side by side) and reinforces the data-doubling story. Non-negotiable keep.
- **Ingest (upload).** `/upload` route and `apps/web/src/components/upload/`. Default destination prefix is `archive/originals/` (single config constant `settings.originals_prefix`).
- The sidebar nav itself + Settings + the Design System utility link.
- **Metadata extraction** (`service/metadata.py`, Pillow) — reused to inspect ingested originals.

**This app's features**
- **Restoration (primary entity).** Full lifecycle — create / read / run(re-colorize) / delete. See §4 for the verb table and the deliberately-omitted `edit`.
- **Restoration Library.** `/restorations` — a gallery scoped to `archive/restored/` (separate from the full-bucket `/files` explorer), with original-vs-restored compare on each detail page.
- **Archival data-growth dashboard.** `/` and `apps/web/src/components/dashboard/` show originals bytes vs restored bytes, total assets restored, restorations today, and a storage-growth chart. New aggregations flow through `runtime -> service -> repo` and TanStack Query hooks in `apps/web/src/lib/queries.ts` — no bare `useEffect + fetch`.

## 3. Architectural Invariants

**Backend layering**: `types` -> `config` -> `repo` -> `service` -> `runtime`

- No backward imports across layers
- No `boto3` outside `repo/`
- **No `deoldify` / `torch` / `fastai` / `cv2` / `imageio_ffmpeg` outside `repo/`** — the DeOldify model stack is an external SDK with the same containment invariant as boto3. `app/repo/deoldify_repo.py` is the only adapter; its heavy imports are deferred into functions so importing the module stays cheap and network-free (relied on by the no-network guard test).
- No business logic in route handlers (`runtime/`)
- All external APIs/models wrapped in `repo/` adapters
- All request/response data validated at boundary (Pydantic models)
- No shared mutable state across layers
- **Device selection is runtime auto-detect** (CUDA → Apple MPS → CPU, defaults to CPU). Never hard-require a GPU. DeOldify's MPS support is weak, so MPS is best-effort and falls back CUDA → CPU.

**Frontend**: shadcn/ui components in `src/components/ui/` are generated — never modify them.

**Data fetching**: every API call flows through TanStack Query hooks in `apps/web/src/lib/queries.ts`. No bare `useEffect + fetch` patterns. New endpoints touch three files: `runtime/<router>.py`, `lib/api-client.ts`, `lib/queries.ts`.

## 3a. Restoration lifecycle (primary entity)

A `Restoration` = one B&W source original + its colorized rendition + provenance
metadata, stored under `archive/restored/<asset_id>/` (`restored.png` / `restored.mp4`
+ `metadata.json`). `asset_id` is derived deterministically from the source key, so
re-colorizing overwrites the same asset (no unbounded versioning).

| Verb | Built? | Surface |
|------|--------|---------|
| **create** | yes | `/restorations/new` → `POST /restorations` (pick source + params; runs colorization; writes rendition + metadata.json). |
| **read** | yes | `/restorations` library + `/restorations/<asset_id>` detail (original-vs-restored compare + provenance). |
| **run** | yes | "Re-colorize" on detail → `POST /restorations/<asset_id>/rerun` (same source, new params; overwrites rendition). |
| **delete** | yes | `DELETE /restorations/<asset_id>` — removes ONLY the rendition + metadata.json. The original master under `archive/originals/` is retained — that's the point. |
| **edit** | **omitted (justified)** | A finished restoration is an immutable archival render; editing a completed render would corrupt its archival fidelity. Changing parameters means producing a new render — covered by **create** (new asset) and **run/re-colorize** (same asset). Recorded in the initial-scaffold plan's `omitted_ui_verbs`. |

`POST` processing is synchronous; the frontend shows the kept `generating-loader`.
An async job queue is out of scope — see `docs/exec-plans/tech-debt-tracker.md`.

## 4. Quality Expectations

- **DRY** — do not duplicate logic, types, or constants. Extract shared code only when used in 2+ places.
- Structured JSON logging only — no `print()` statements
- No raw SDK calls outside `repo/` layer
- Files stay under 300 lines
- Tests added or updated for every behavior change
- Docs updated in same PR as code changes
- Lint clean before merge
- Prefer boring, composable libraries over clever abstractions
- No implicit type assumptions — use typed models

## 5. Mechanical Enforcement

| Rule | Enforced by |
|------|-------------|
| No backward imports | `tests/test_structure.py::test_no_backward_imports` |
| No boto3 / DeOldify / torch / fastai / cv2 outside repo/ | `tests/test_structure.py::test_boto3_only_in_repo` |
| DeOldify adapter import stays network-free + stable API | `tests/test_deoldify_repo.py` |
| File size < 300 lines | `tests/test_structure.py::test_file_size_limits` |
| All layers exist | `tests/test_structure.py::test_all_layers_exist` |
| No bare print() | `ruff` rule T20 |
| Import ordering | `ruff` rule I001 |
| Frontend strict equality | `eslint` rule eqeqeq |
| No unused vars | `eslint` + `ruff` rules |

## 6. Commands

```bash
# Run
pnpm dev               # start both frontend and backend
pnpm dev:web           # frontend only
pnpm dev:api           # backend only

# Test & Lint
pnpm lint              # frontend lint (eslint)
pnpm build             # frontend type check + build
pnpm lint:api          # backend lint (ruff)
pnpm test:api          # backend tests (pytest)
pnpm check:structure   # structural boundary tests
pnpm test:e2e          # Playwright e2e tests
```

## 7. Agent Workflow

1. Read this file first.
2. Review [ARCHITECTURE.md](ARCHITECTURE.md) before structural changes.
3. For non-trivial changes, create a plan in `docs/exec-plans/active/`.
4. Implement the smallest coherent change.
5. Run: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
6. Update docs in the same PR (see §9).
7. Move completed plans to `docs/exec-plans/completed/`.
8. Only change files relevant to the task. No drive-by improvements.

## 8. Frontend Conventions

See [docs/dev-workflows.md](docs/dev-workflows.md) for full details.

## 9. Doc Update Mapping

| Change Type | Update Location |
|-------------|-----------------|
| Feature logic, inputs, outputs, tests | `docs/features/<feature>.md` |
| User journeys | `docs/app-workflows.md` |
| System layout, deployments | `ARCHITECTURE.md` |
| Dev or testing process | `docs/dev-workflows.md` |
| Setup or scope changes | `README.md` |
| Security changes | `docs/SECURITY.md` |
| Reliability changes | `docs/RELIABILITY.md` |
| Active work plans | `docs/exec-plans/active/` |
| Known tech debt | `docs/exec-plans/tech-debt-tracker.md` |

If documentation and implementation conflict, update docs in the same PR. Documentation rot destroys agent reliability.

## 10. Doc Map

| Topic | Location |
|-------|----------|
| System layout, data flows, boundaries | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Feature docs | [docs/features/](docs/features/) |
| User journeys | [docs/app-workflows.md](docs/app-workflows.md) |
| Engineering workflows and testing | [docs/dev-workflows.md](docs/dev-workflows.md) |
| Security principles | [docs/SECURITY.md](docs/SECURITY.md) |
| Reliability expectations | [docs/RELIABILITY.md](docs/RELIABILITY.md) |
| Execution plans | [docs/exec-plans/](docs/exec-plans/) |
| Tech debt | [docs/exec-plans/tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md) |

## 11. When Unsure

- Prefer boring, stable libraries
- Prefer small PRs over large changes
- Add tests with every change
- Never bypass lint rules without explicit instruction
- Ask before making destructive or irreversible changes
