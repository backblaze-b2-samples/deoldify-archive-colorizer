# Build plan — `deoldify-archive-colorizer`

Scaffolded from `vibe-coding-starter-kit` (the only valid source tree:
`.claude/scratch/vcsk-a7eb21fc-4cbc-46c0-82ab-c869cfb16e07/`). This plan is the
contract; the builder and reviewer both work against it.

---

## 1. Purpose

`deoldify-archive-colorizer` is a self-hosted B2 sample for film archives, museums,
and documentary producers who need to **restore and colorize black-and-white
historical footage**. An archival digitization team ingests scanned B&W frames or
clips into Backblaze B2 under `archive/originals/`, runs **DeOldify** locally (its
NoGAN deep-learning colorizer) on each asset, applies an optional denoise/sharpen
restore pass, and writes a full-color restored rendition + a provenance metadata
JSON to `archive/restored/<asset_id>/`. **Both** the original master and every
restored variant are retained in B2 as authoritative archival objects — so the
sample's headline story is *data doubling*: a 10 TB B&W archive becomes 20+ TB of
permanently-stored originals-plus-restorations. B2 is the single storage layer for
both, via the S3-compatible API with a custom user-agent and standard `B2_*` env
vars. Everything heavy runs locally on OSS — **no second API key, B2 credentials
only**.

---

## 2. Architecture delta from `vibe-coding-starter-kit`

The starter kit is the ceiling. Strip what this app doesn't need; keep the reusable
B2-backed scaffolding; add the colorization pipeline + restoration lifecycle.

### KEEP (as-is — part of the starter contract, do not strip/rename/replace)
- **UI kit / design system** — `apps/web/src/components/ui/**`, design tokens in
  `apps/web/src/app/globals.css`, the `/design` reference page. (Reuse the
  `generating-loader` for the "colorizing…" state.)
- **Bucket explorer (full-bucket browse)** — `/files` route, `apps/web/src/app/files/`,
  `apps/web/src/components/files/**`, and its sidebar entry. **NON-NEGOTIABLE KEEP** —
  never removable. It is the raw B2 surface that lets users see *every* object
  (originals + restored side by side at the byte level), which directly reinforces
  the data-doubling story.
- **Upload** — `/upload` route + `apps/web/src/components/upload/**` and its sidebar
  entry. (Default destination prefix adapted — see ADD/Adapt note below.)
- **Sidebar nav** itself + `/settings` + the Design System utility link.
- **Backend layering + structural tests** — `types→config→repo→service→runtime`,
  `tests/test_structure.py`, ruff/eslint config, 300-line limit, JSON logging,
  `/health`, `/metrics`. `boto3` stays confined to `repo/`; **DeOldify/torch imports
  must also be confined to `repo/`** (they are external SDKs — same invariant).
- **Single-source `.env`** loading, doctor preflight (`scripts/doctor.mjs`,
  `scripts/dev.sh`, `scripts/pick-port.mjs`) — adapt the env-var names it checks.
- **Metadata extraction** (`service/metadata.py`, Pillow) — KEEP, lightly reframed as
  "inspect ingested archival originals (dimensions, EXIF, checksum)". It's harmless
  reusable B2 surface; do not rebuild. (PDF/PyPDF2 path may stay; archives are
  image/video so it's simply unused — leave it rather than churn the module/tests.)

### TRIM (remove from starter)
- **Default dashboard semantics** — the generic "files uploaded / storage used"
  stats, `upload-chart`, and `recent-uploads-table` are illustrative defaults. Replace
  their *content* with restoration metrics (see ADD → Dashboard). Keep the
  `runtime→service→repo` + TanStack-Query wiring; swap what they compute.
- Starter screenshots in `docs/images/` and starter-specific copy in `README.md`,
  `docs/app-workflows.md` (rewritten, not deleted). Do **not** create new binary
  assets (screenshots/logos) — that's a later pipeline step.

### ADD (new for `deoldify-archive-colorizer`)
- **Primary entity: `Restoration`** — backend types + service + runtime router +
  frontend pages (full lifecycle, see §4).
- **DeOldify repo adapter** — `services/api/app/repo/deoldify_repo.py`: wraps DeOldify's
  ImageColorizer / VideoColorizer, device auto-detect (CUDA→MPS→CPU), weight loading.
  Keeps all `deoldify`/`torch`/`fastai` imports inside `repo/`.
- **Restore-pass helper** — denoise + sharpen on colorized output (OpenCV/Pillow),
  in `repo/` or a `service/`-level pure step as appropriate (no SDK in service).
- **MP4 encode helper** — encode colorized frames → MP4 using the **bundled
  `imageio-ffmpeg` binary**, NOT bare system `ffmpeg` (Homebrew ffmpeg ships without
  libass/codecs reliably). Document this.
- **Restoration Library (sample-specific scoped explorer)** — `/restorations` route:
  a gallery/list scoped to `archive/restored/` (+ paired originals), separate from the
  full-bucket `/files` explorer. This is the MANDATORY sample-specific asset explorer.
- **Restoration detail / compare view** — `/restorations/<asset_id>`: side-by-side
  original (B&W) vs restored (color), provenance metadata, Re-colorize + Delete
  actions.
- **Create flow** — `/restorations/new`: pick a source original + colorization params,
  submit → runs colorization synchronously → stores restored render + metadata JSON.
- **Adapt Upload default prefix** to `archive/originals/` (single config constant) so
  the documented happy-path layout is produced by the kept Upload page. The Upload
  page UI/components stay; only the default destination prefix changes. Document it.

---

## 3. B2 surface (S3-compatible only — no b2-native)

All via the kept `repo/b2_client.py` boto3 client (custom UA, standard `B2_*` vars):

| Operation | Used for |
|-----------|----------|
| `PutObject` | write ingested originals (`archive/originals/`), restored MP4/image + `metadata.json` (`archive/restored/<asset_id>/`) |
| `GetObject` / `generate_presigned_url` | fetch original bytes for colorization; serve original/restored previews + downloads in the UI |
| `ListObjectsV2` (prefix) | list originals (create-flow source picker), list restored (Restoration Library), dashboard aggregates |
| `HeadObject` | metadata / existence checks |
| `DeleteObject` | delete a restored rendition (scoped to `archive/restored/<asset_id>/` — **never** deletes the original master) |

**No b2-native API anywhere.** Standard #1 (S3 default) satisfied. Standard #2: custom
UA `deoldify-archive-colorizer` on the S3 client. Standard #3: env-var rename (see §6).

---

## 4. Key features

### Primary-entity lifecycle — entity = `Restoration`

A `Restoration` = one B&W source original + its colorized/restored rendition +
provenance metadata (model variant, render factor, restore flags, model version,
device, timestamps). Stored as the object set under `archive/restored/<asset_id>/`
(rendition file + `metadata.json`); `asset_id` derives from the source key.

| Verb | Built? | Surface |
|------|--------|---------|
| **create** | ✅ | `/restorations/new` form → `POST /restorations` (select source original + params; runs colorization; writes restored render + metadata.json). |
| **read** | ✅ | `/restorations` library (list, scoped to `archive/restored/`) + `/restorations/<asset_id>` detail with original-vs-restored compare + metadata. |
| **run** | ✅ | "Re-colorize" on the detail page → `POST /restorations/<asset_id>/rerun` (re-render the SAME original with changed params; overwrites that asset's restored output — no unbounded versioning). |
| **delete** | ✅ | `DELETE /restorations/<asset_id>` from library/detail; removes ONLY the restored rendition + its metadata.json (original master is retained — that's the point). |
| **edit** | ❌ omitted (justified) | A finished restoration is an **immutable archival render** — original + colorized output + provenance metadata are authoritative objects; editing a completed render would corrupt its archival fidelity. Changing parameters means producing a new render, which is exactly what **create** (new asset) and **run/re-colorize** (same asset, new params) already cover. So edit is intentionally not user-accessible. → record in `omitted_ui_verbs`. |

**Backend wiring per new endpoint touches the 3 canonical layers** (router in
`runtime/restorations.py` → `lib/api-client.ts` → `lib/queries.ts`), business logic in
`service/restoration.py`, all SDK/model calls in `repo/`.

**Processing model:** synchronous on submit. Default/verifiable path is a **single
still image** (DeOldify `ImageColorizer`) which completes in seconds–low-minutes on
CPU; **short video clips** (`VideoColorizer` → MP4 via imageio-ffmpeg) supported as the
heavier path. Asset type inferred from the source key's content type. Frontend shows
the kept `generating-loader` while the POST is in flight. A `status`
(`completed`/`failed`) field is stored in metadata for realism. (Async job queue is
explicitly out of scope — note in `docs/exec-plans/tech-debt-tracker.md`.)

### Feature list (seeds README + `docs/features/<feature>.md`)
1. **Colorization (DeOldify, local)** — NoGAN colorization of B&W frames/clips; the
   marquee feature.
2. **Restore pass** — optional denoise + sharpen on the colorized output.
3. **Restoration Library** — `archive/restored/`-scoped explorer + original-vs-restored
   compare.
4. **Archival data-growth dashboard** — originals bytes vs restored bytes, total assets
   restored, restorations today, storage-growth chart. Visualizes the data-doubling
   story.
5. **Ingest** — upload B&W originals to `archive/originals/` (kept Upload page).
6. **Full bucket explorer** — kept `/files` view over the whole bucket.

### External API provider — **NONE (fully local)**

| Feature | Provider/model | deployment | Est. cost / full demo run | Key env var |
|---------|----------------|------------|---------------------------|-------------|
| Colorization | **DeOldify** (jantic/DeOldify, NoGAN; Artistic + Stable image models, Video model) | **`local`** | **$0** (on-device; B2 storage only) | none — B2 creds only |
| Restore pass | OpenCV/Pillow (denoise/sharpen) | `local` | $0 | none |

**`deployment: local` hard rule:** default to **CPU**, auto-detect a GPU at runtime —
first available of **CUDA → Apple MPS → CPU**, never hard-require a GPU. **Caveat:**
DeOldify (fastai/older torch stack) has weak/no MPS support → on Apple silicon it
effectively falls back **CUDA → CPU**; the device helper must detect this gracefully
and not crash on MPS. Record this in the plan and the colorization feature doc.

**Dependency / install notes (carry into requirements + verify step):**
- DeOldify is **not** a cleanly-maintained PyPI package — vendor the `deoldify`
  package from a **pinned git ref** (or a pinned working PyPI release if one resolves)
  and **pin** `torch`/`torchvision`/`fastai` to a known-good window. **Unpinned
  torch/fastai/huggingface is a false-green** (boots + tests pass, model load fails on
  a fresh clone) — pin everything in the ML requirements file.
- **torch ≥2.x `weights_only=True` default** breaks loading DeOldify's legacy `.pth`
  weights → load with `weights_only=False` or `torch.serialization.add_safe_globals`
  before the model-load site.
- **Model weights** (`ColorizeArtistic_gen.pth` / `ColorizeStable_gen.pth` /
  `ColorizeVideo_gen.pth`, ~250 MB) download on first run into a **gitignored**
  `models/` dir; document the download + source URLs.
- **ffmpeg** via bundled **`imageio-ffmpeg`** binary, not bare system `ffmpeg`.
- Keep heavy ML deps in a **separate `requirements-ml.txt`** (pinned) so the core API
  deps stay light; document the two-step install. Add a **no-network signature/import
  guard test** for `deoldify_repo` (assert the adapter's public functions + device
  detection without downloading weights or running the model) so the build's test
  suite stays fast and deterministic; true end-to-end colorization is validated by the
  later `verify` pipeline step.

### Form UX conventions

**Create form (`/restorations/new`)** — selectors for every finite field; safe
defaults surfaced as placeholder / `FormDescription` (guidance only, **no autofill
button**). Mirror `apps/web/src/components/settings/settings-form.tsx`.

| Field | Control | Default (shown as guidance) |
|-------|---------|------------------------------|
| Source original | `Select` (populated from `ListObjectsV2` of `archive/originals/`) | — (user picks; description: "Pick an ingested B&W master from `archive/originals/`.") |
| Model variant | `Select` — Artistic / Stable (image) · Video (clips) | Artistic ("best for most archival stills") |
| Render quality | `Select` of presets → render_factor (e.g. Draft 21 / Balanced 30 / High 35) | Balanced ("good detail/speed tradeoff for a first run") |
| Denoise | `Switch` | on |
| Sharpen | `Switch` | off |

**Run / Re-colorize form (detail page)** — same selector rules; **pre-filled with the
restoration's current params** (it's "run with new params", not editing the artifact).
No create-style default hints needed (opens populated).

**No edit form** (edit verb omitted, see §4 table).

---

## 5. Doc transforms

- `README.md` → full rewrite to the colorizer narrative (keep the agent-first /
  starter-kit framing, B2 setup with **standard env names**, commands table, data-
  doubling story). Update UTM `utm_content` tag to `deoldify-archive-colorizer`.
- `AGENTS.md`, `ARCHITECTURE.md` → update repo map, add DeOldify repo-adapter invariant
  (model SDK imports confined to `repo/`), Restoration data flow, env-var names.
- `docs/app-workflows.md` → archivist journeys: ingest → colorize → compare → retain.
- `docs/features/`:
  - **rewrite** `dashboard.md` → archival data-growth metrics.
  - **keep/reframe** `file-upload.md` (→ ingest originals), `file-browser.md` (→ bucket
    explorer), `metadata-extraction.md` (→ inspect originals).
  - **add** `colorization.md`, `restore-pass.md`, `restoration-library.md` (use
    `docs/features/_template.md`; set `last_verified`).
- `docs/exec-plans/tech-debt-tracker.md` → note async job queue + multi-version
  restorations as deferred.
- Move this plan to `docs/exec-plans/completed/initial-scaffold.md` on PASS (Phase 5).

---

## 6. Rename / standards table

| From (`vibe-coding-starter-kit`) | To (`deoldify-archive-colorizer`) |
|---|---|
| package `name` `vibe-coding-starter-kit`; workspace filter `@vibe-coding-starter-kit/web` | `deoldify-archive-colorizer`; `@deoldify-archive-colorizer/web` (root `package.json`, `apps/web/package.json`, `pnpm-workspace.yaml`, all `pnpm --filter` refs, `test:e2e` install hint) |
| `APP_NAME = "OSS Starter Kit"`, `APP_DESCRIPTION` (app-config.ts) | `APP_NAME = "DeOldify Archive Colorizer"`, archival-colorizer description |
| FastAPI `title="OSS Starter Kit API"` / description (main.py) | `title="DeOldify Archive Colorizer API"`, colorizer description |
| `user_agent_extra="b2ai-oss-start"` (b2_client.py) | `user_agent_extra="deoldify-archive-colorizer"` (Standard #2: custom UA on every S3 client) |
| Header/branding fallbacks (header.tsx, any hardcoded "oss-starter-kit"/"Page") | derive title from `APP_NAME` + route; no hardcoded starter name |
| infra/railway service names, image tags, workflow slugs | `deoldify-archive-colorizer` slug |

### Standard #3 — env-var rename (NON-NEGOTIABLE; touches settings.py, main.py, b2_client.py, .env.example, scripts/doctor.mjs, README, AGENTS/ARCHITECTURE)

| Starter (non-standard) | Standard #3 name | Notes |
|---|---|---|
| `B2_KEY_ID` | `B2_APPLICATION_KEY_ID` | rename everywhere |
| `B2_APPLICATION_KEY` | `B2_APPLICATION_KEY` | unchanged |
| `B2_BUCKET_NAME` | `B2_BUCKET_NAME` | unchanged |
| `B2_ENDPOINT` | `B2_REGION` | store region (e.g. `us-west-004`); construct endpoint `https://s3.{B2_REGION}.backblazeb2.com` in `config`/`repo`. |
| `b2_public_url` / (none) | `B2_PUBLIC_URL_BASE` | optional public base URL for object links |

Update `main.py` `REQUIRED_B2_SETTINGS` + `PLACEHOLDER_VALUES`, `settings.py` fields +
endpoint-from-region property, `b2_client.py` client construction, `.env.example`
(placeholders only — never real secrets), `scripts/doctor.mjs` env checks, and the
README setup section to the standard names. This is the #1 known starter-kit deviation
and a hard b2-doctor requirement.

---

## 7. Non-negotiable checklist for the builder
- [ ] Standard #3 env names migrated everywhere (no lingering `B2_KEY_ID`/`B2_ENDPOINT`).
- [ ] Custom UA `deoldify-archive-colorizer` on the S3 client; S3 API only (no b2-native).
- [ ] `boto3` AND `deoldify`/`torch`/`fastai` imports confined to `repo/`.
- [ ] Bucket explorer `/files` KEPT; sample-specific `/restorations` scoped explorer ADDED.
- [ ] Restoration verbs create/read/run/delete built; edit omitted with the §4 justification recorded.
- [ ] DeOldify deps pinned in `requirements-ml.txt`; device autodetect CUDA→MPS→CPU (MPS caveat handled); weights gitignored; imageio-ffmpeg for encode; torch `weights_only` trap handled.
- [ ] No-network signature/import guard test for `deoldify_repo`.
- [ ] `pnpm lint`, `pnpm build`, `pnpm lint:api`, `pnpm test:api`, `pnpm check:structure` all green; files <300 lines; docs updated same-change.
- [ ] No new binary assets, no remote push, no sibling-sample edits.
