<!-- last_verified: 2026-06-30 -->
# App Workflows

Archivist journeys inside the application: **ingest → colorize → compare → retain**.

## 1. Ingest a black-and-white master

- Archivist navigates to `/upload` (Ingest)
- Drops or selects scanned B&W stills (or short clips) in the dropzone
- Client validates size (max 500MB) and type
- Files are written to `archive/originals/` in B2 (the documented happy-path prefix)
- On success: toast + green checkmark; on failure: red status icon with the error
- See: [File Upload](features/file-upload.md)

## 2. Colorize an original (create a Restoration)

- Archivist navigates to `/restorations` → **New restoration** (`/restorations/new`)
- Picks a source original from a `Select` populated by `ListObjectsV2` of `archive/originals/`
- Chooses **model variant** (Artistic / Stable / Video), **render quality** (Draft / Balanced / High), and toggles **Denoise** / **Sharpen** — every finite field is a selector or switch; create-form defaults are shown as guidance only
- Submitting runs DeOldify locally and synchronously; the reused `generating-loader` shows a "Colorizing…" state while the POST is in flight
- The restored rendition + a `metadata.json` (provenance: model, render factor, restore flags, device, timestamps, status) are written to `archive/restored/<asset_id>/`
- On completion the archivist lands on the restoration detail page
- See: [Colorization](features/colorization.md), [Restore Pass](features/restore-pass.md)

## 3. Browse the Restoration Library

- Archivist navigates to `/restorations`
- A gallery scoped to `archive/restored/` shows each restoration with original + restored thumbnails, status, variant, and device
- This is separate from the full-bucket `/files` explorer (which shows every object)
- See: [Restoration Library](features/restoration-library.md)

## 4. Compare original vs restored, then re-colorize or delete

- Archivist opens `/restorations/<asset_id>`
- Side-by-side **Original (B&W)** vs **Restored (color)** compare, plus full provenance metadata
- **Re-colorize**: opens a form pre-filled with the current params (same source, new params); overwrites the rendition — no unbounded versioning
- **Delete**: removes ONLY the restored rendition + its `metadata.json`. The original master under `archive/originals/` is always retained — that's the archival point
- (There is no **edit**: a finished restoration is an immutable archival render; changing params means a new render via create or re-colorize.)

## 5. See the archive grow

- Archivist navigates to `/` (Dashboard)
- Archival data-growth metrics: assets restored, restorations today, total archive footprint, and a **data growth ratio**
- The storage-growth chart shows originals bytes vs restored bytes side by side — the data-doubling story made visible
- See: [Dashboard](features/dashboard.md)

## 6. Inspect every object at the byte level

- Archivist navigates to `/files`
- The full-bucket tree shows originals and restored renditions together, with preview / download / delete
- See: [Bucket Explorer](features/file-browser.md)
