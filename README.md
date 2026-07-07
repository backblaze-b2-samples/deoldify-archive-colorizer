<!-- last_verified: 2026-06-30 -->
# DeOldify Archive Colorizer

Restore and colorize black-and-white historical footage with **[DeOldify](https://github.com/jantic/DeOldify)** running locally, and keep both the original masters and the colorized restorations in **[Backblaze B2](https://www.backblaze.com/sign-up/ai-cloud-storage?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=b2ai-deoldify-archive-colorizer)**. Built for film archives, museums, and documentary producers who need their full pipeline — ingest, colorize, compare, retain — backed by durable object storage.

Everything heavy runs on-device using open-source models. There is **no second API key**: B2 credentials only.

## The data-doubling story

An archival digitization team ingests scanned B&W frames or clips into B2 under `archive/originals/`, runs DeOldify's NoGAN colorizer on each asset, applies an optional denoise/sharpen restore pass, and writes a full-color restored rendition plus a provenance metadata JSON to `archive/restored/<asset_id>/`. **Both** the original master and every restored variant are retained in B2 as authoritative archival objects.

So a 10 TB B&W archive becomes 20+ TB of permanently-stored originals-plus-restorations. B2 is the single storage layer for both — via the S3-compatible API, with a custom user agent and standard `B2_*` env vars.

## What you get

- **Colorization (DeOldify, local)** — NoGAN colorization of B&W stills; the marquee feature. Artistic and Stable image models.
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
| Contain external SDKs | `boto3` only in `repo/`; the `deoldify`/`torch`/`fastai` model stack runs in a separate container and is imported **nowhere** in the API — both verified by structural tests |
| Keep files agent-sized | 300-line limit per file, enforced by test |
| Docs updated with code | Same-PR requirement prevents documentation rot |
| Structured observability | JSON logging, `/metrics` endpoint, request tracing |

## Quick Start

You need: Node.js >= 20, pnpm >= 9, Python >= 3.11, **Docker** (for the colorization service — on Apple silicon / macOS, [Colima](https://github.com/abiosoft/colima) works well: `colima start`), and a free **[Backblaze B2 account](https://www.backblaze.com/sign-up/ai-cloud-storage?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=b2ai-deoldify-archive-colorizer)**.

### 1. Install frontend + core backend dependencies

```bash
pnpm install
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ../..
```

### 2. Colorization service (Docker)

DeOldify rides the **fastai-v1 / torch-1.11 / Pillow<10** stack, which is irreconcilable with this API's modern fastai-2 / torch-2 / Python-3.11 environment. So colorization runs in its own **native `linux/arm64` container** (`infra/deoldify/`); the API talks to it over HTTP. Nothing to install into the venv — Docker builds it for you.

`pnpm dev` builds and starts the container automatically. You can also build/run it on its own:

```bash
docker compose up --build deoldify     # or: pnpm dev:deoldify
```

> **First build is slow.** The image (~4.7 GB) installs the pinned legacy ML stack and bakes in both model weights — `ColorizeArtistic_gen.pth` (~243 MB) and `ColorizeStable_gen.pth` (~833 MB) — plus the resnet backbones, so no download happens at request time. Subsequent builds are cached. CPU colorization is slow (seconds to a few minutes per image, no GPU in-container).

> **Native arm64 only.** The container is pinned to `--platform=linux/arm64`. torch's amd64 wheels use AVX and `SIGILL` under QEMU on Apple silicon, so never build/run it as amd64. On macOS, [Colima](https://github.com/abiosoft/colima) gives you a native aarch64 Docker daemon (`colima start`).

The API reaches the service via `DEOLDIFY_SERVICE_URL` (default `http://localhost:8137`). The container is **stateless and credential-free** — it never touches B2.

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

Frontend at `localhost:3000`, API at `localhost:8000`, and the DeOldify colorization container at `localhost:8137`. `pnpm dev` runs `pnpm doctor` first — a preflight check that catches common setup gotchas (wrong Node/Python version, missing venv, missing or placeholder `.env`, ports already taken) — then checks Docker is running and builds/starts the colorization container alongside web + api.

### 5. Try the happy path

1. **Ingest** a black-and-white image on the Ingest page — it lands in `archive/originals/`.
2. Go to **Restorations → New restoration**, pick that original, choose a model variant and render quality, and **Colorize**.
3. The restored rendition + a `metadata.json` are written to `archive/restored/<asset_id>/`. Open the restoration to compare original vs restored side by side.

## Compute (colorization service)

Colorization runs on **CPU inside the container** — there is no GPU passthrough, and DeOldify's legacy stack has no usable Apple MPS path. A still completes in seconds to a few minutes depending on `render_factor` and image size. The API's device helper reports the container's device by probing its `/health` endpoint and never hard-requires a GPU; if the service is unreachable it still reports CPU rather than crashing.

**Memory.** DeOldify renders internally at `render_factor * 16` px and the forward-pass activations grow with that area, so peak RAM is driven by `render_factor` and the model variant (the heavier `stable`/resnet101 peaks higher than `artistic`/resnet34), not by the input file size. Give the Docker VM **at least 4 GiB** (on Colima: `colima start --memory 4`). The render-quality presets (Draft / Balanced / High → `render_factor` 16 / 22 / 24) are further **clamped per variant** to a proven-safe ceiling — **artistic ≤ 24, stable ≤ 22** — because `stable` alone OOMs at `render_factor` 24 on a 4 GiB VM; the clamp keeps every selectable variant×preset combo (including `stable` + High) within budget and records the effective factor in each restoration's provenance. `render_factor` 28+ exceeds 4 GiB for either variant and the Linux OOM killer will SIGKILL (exit 137) the container mid-render; bump the VM's memory before raising the presets (`_RENDER_FACTORS` in `services/api/app/service/restoration.py`) or the per-variant ceilings (`VARIANT_MAX_RENDER_FACTOR` in `services/api/app/repo/deoldify_repo.py`).

Video colorization is deliberately out of scope for this synchronous flow — the API rejects video sources upstream and the container exposes only an image endpoint. See [tech-debt-tracker](docs/exec-plans/tech-debt-tracker.md) for the async-queue note.

## Tech Stack

- TypeScript, Next.js 16, React 19, Tailwind v4, shadcn/ui, Recharts
- TanStack Query — caching, dedup, retry for every fetch
- Python 3.11+, FastAPI, boto3, Pydantic v2, Pillow, httpx
- DeOldify (NoGAN), PyTorch, fastai — pinned legacy stack running in a separate `linux/arm64` container (`infra/deoldify/`), reached over HTTP
- Docker (Colima on macOS) for the colorization service
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
