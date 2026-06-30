<!-- last_verified: 2026-06-30 -->
# DeOldify Archive Colorizer

Restore and colorize black-and-white historical footage with **[DeOldify](https://github.com/jantic/DeOldify)** running locally, and keep both the original masters and the colorized restorations in **[Backblaze B2](https://www.backblaze.com/sign-up/ai-cloud-storage?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=b2ai-deoldify-archive-colorizer)**. Built for film archives, museums, and documentary producers who need their full pipeline — ingest, colorize, compare, retain — backed by durable object storage.

Everything heavy runs on-device using open-source models. There is **no second API key**: B2 credentials only.

## The data-doubling story

An archival digitization team ingests scanned B&W frames or clips into B2 under `archive/originals/`, runs DeOldify's NoGAN colorizer on each asset, applies an optional denoise/sharpen restore pass, and writes a full-color restored rendition plus a provenance metadata JSON to `archive/restored/<asset_id>/`. **Both** the original master and every restored variant are retained in B2 as authoritative archival objects.

So a 10 TB B&W archive becomes 20+ TB of permanently-stored originals-plus-restorations. B2 is the single storage layer for both — via the S3-compatible API, with a custom user agent and standard `B2_*` env vars.

## What you get

- **Colorization (DeOldify, local)** — NoGAN colorization of B&W stills; the marquee feature. Artistic / Stable image models, with a Video model path for clips.
- **Restoration lifecycle** — create, browse, re-colorize, and delete restorations. Each restoration is an immutable archival render with provenance metadata.
- **Restoration Library** — a gallery scoped to `archive/restored/`, with side-by-side original-vs-restored compare on each detail page.
- **Archival data-growth dashboard** — originals bytes vs restored bytes, total assets restored, restorations today, and a storage-growth chart that visualizes the data-doubling story.
- **Ingest** — upload B&W originals to `archive/originals/`.
- **Full bucket explorer** — the kept `/files` view over the entire bucket, so you can see every object (originals + restored) at the byte level.
- **Agent-optimized docs** — your AI coding agent can read the repo and start contributing immediately.

## Agent-First Architecture

This repo is optimized for coding agents. **[AGENTS.md](AGENTS.md) is the single source of truth** — a compact entry point with the repository layout, architectural invariants, commands, and conventions. Architecture is enforced mechanically (structural tests, ruff, ESLint) rather than by convention:

| Principle | Implementation |
|-----------|---------------|
| Single source of truth for agents | AGENTS.md — layout, invariants, commands |
| Enforce invariants mechanically | Structural tests + ruff + ESLint verify boundaries |
| Strict layered architecture | `types -> config -> repo -> service -> runtime`, enforced by tests |
| Contain external SDKs | `boto3` **and** `deoldify`/`torch`/`fastai` only in `repo/` — verified by a structural test |
| Keep files agent-sized | 300-line limit per file, enforced by test |
| Docs updated with code | Same-PR requirement prevents documentation rot |
| Structured observability | JSON logging, `/metrics` endpoint, request tracing |

## Quick Start

You need: Node.js >= 20, pnpm >= 9, Python >= 3.11, and a free **[Backblaze B2 account](https://www.backblaze.com/sign-up/ai-cloud-storage?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=b2ai-deoldify-archive-colorizer)**.

### 1. Install frontend + core backend dependencies

```bash
pnpm install
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ../..
```

### 2. Install the DeOldify model stack (heavy ML deps)

The colorization model stack is pinned in a separate file so the core API stays light. Install it into the same venv:

```bash
cd services/api
source .venv/bin/activate
pip install -r requirements-ml.txt
cd ../..
```

> **Why pinned?** Unpinned `torch`/`fastai`/`huggingface` is a classic false-green: the API boots and tests pass, but the model load fails on a fresh clone. The window in `requirements-ml.txt` is known to load DeOldify's NoGAN weights. The adapter also works around torch >= 2.x's `weights_only=True` default, which otherwise refuses DeOldify's legacy pickled `.pth` checkpoints.

Model weights (`ColorizeArtistic_gen.pth` / `ColorizeStable_gen.pth`, ~250 MB each) download on first colorization into a **gitignored** `services/api/models/` directory.

### 3. Add your B2 credentials

```bash
cp .env.example .env
```

Open `.env` and fill in your credentials from the [Backblaze B2 dashboard](https://secure.backblaze.com/b2_buckets.htm?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=b2ai-deoldify-archive-colorizer):

1. **Create a bucket.** Paste its **Bucket Unique Name** into `B2_BUCKET_NAME`, and set `B2_REGION` to the bucket's region (e.g. `us-west-004`). The S3 endpoint is constructed as `https://s3.{B2_REGION}.backblazeb2.com` — you do not set the endpoint directly.
2. **Create an application key** with `Read and Write` permission. Paste **keyID** into `B2_APPLICATION_KEY_ID` and **applicationKey** into `B2_APPLICATION_KEY` (only shown once).
3. *(Optional)* `B2_PUBLIC_URL_BASE` — a public base URL for object links. Leave empty to fall back to short-lived presigned URLs.

> Walkthroughs: [creating a bucket](https://www.backblaze.com/docs/cloud-storage-create-and-manage-buckets) and [creating app keys](https://www.backblaze.com/docs/cloud-storage-create-and-manage-app-keys).

### 4. Run it

```bash
pnpm dev
```

Frontend at `localhost:3000`, API at `localhost:8000`. `pnpm dev` runs `pnpm doctor` first — a preflight check that catches common setup gotchas (wrong Node/Python version, missing venv, missing or placeholder `.env`, ports already taken).

### 5. Try the happy path

1. **Ingest** a black-and-white image on the Ingest page — it lands in `archive/originals/`.
2. Go to **Restorations → New restoration**, pick that original, choose a model variant and render quality, and **Colorize**.
3. The restored rendition + a `metadata.json` are written to `archive/restored/<asset_id>/`. Open the restoration to compare original vs restored side by side.

## Device selection (local model)

Colorization is fully local. The device helper auto-detects the best available device — **CUDA → Apple MPS → CPU** — and **defaults to CPU**; it never hard-requires a GPU. DeOldify rides an older fastai/torch stack with weak MPS support, so on Apple silicon it is treated as best-effort and falls back **CUDA → CPU** if a build fails on MPS. A still completes in seconds to a few minutes on CPU.

Video clips are the heavier path (DeOldify's `VideoColorizer` → MP4 via the bundled `imageio-ffmpeg` binary, not bare system `ffmpeg`). The synchronous flow in this sample targets stills; see [tech-debt-tracker](docs/exec-plans/tech-debt-tracker.md) for the async-queue note.

## Tech Stack

- TypeScript, Next.js 16, React 19, Tailwind v4, shadcn/ui, Recharts
- TanStack Query — caching, dedup, retry for every fetch
- Python 3.11+, FastAPI, boto3, Pydantic v2, Pillow
- DeOldify (NoGAN), PyTorch, fastai — pinned in `requirements-ml.txt`, imports confined to `repo/`
- Backblaze B2 (S3-compatible object storage)
- pnpm workspaces (monorepo)

## Commands

| Command | What it does |
|---------|-------------|
| `pnpm dev` | Start frontend + backend |
| `pnpm dev:web` | Frontend only |
| `pnpm dev:api` | Backend only |
| `pnpm build` | Build frontend |
| `pnpm lint` | Lint frontend |
| `pnpm lint:api` | Lint backend (ruff) |
| `pnpm test:api` | Run backend tests |
| `pnpm check:structure` | Verify layering rules + SDK containment |
| `pnpm test:e2e` | Playwright e2e tests (run `pnpm --filter @deoldify-archive-colorizer/web exec playwright install chromium` once first) |

## Documentation Map

| Doc | Purpose |
|-----|---------|
| [AGENTS.md](AGENTS.md) | Agent table of contents — start here |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System layout, layering, data flows |
| [docs/features/](docs/features/) | Feature docs (colorization, restore pass, library, dashboard, ingest, browser, metadata) |
| [docs/app-workflows.md](docs/app-workflows.md) | Archivist journeys |
| [docs/dev-workflows.md](docs/dev-workflows.md) | Engineering workflows and testing |
| [docs/SECURITY.md](docs/SECURITY.md) | Security principles |
| [docs/RELIABILITY.md](docs/RELIABILITY.md) | Reliability expectations |
| [docs/exec-plans/](docs/exec-plans/) | Execution plans and tech debt tracker |

## License

MIT License - see [LICENSE](LICENSE) for details.

## Claude Agent B2 Skill

Manage Backblaze B2 from your terminal using natural language (list/search, audits, stale or large file detection, security checks, safe cleanup).

Repo: [https://github.com/backblaze-b2-samples/claude-skill-b2-cloud-storage](https://github.com/backblaze-b2-samples/claude-skill-b2-cloud-storage)
