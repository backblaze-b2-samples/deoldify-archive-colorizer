<!-- last_verified: 2026-06-30 -->
# Feature: Restoration Library

## Purpose
Browse colorized restorations scoped to `archive/restored/`, and compare each one against its original B&W master — the mandatory sample-specific asset explorer, separate from the full-bucket `/files` view.

## Used By
- UI: `/restorations` (gallery), `/restorations/<asset_id>` (detail / compare)
- API: `GET /restorations`, `GET /restorations/<asset_id>`, `GET /restorations/<asset_id>/preview`, `DELETE /restorations/<asset_id>`, `POST /restorations/<asset_id>/rerun`

## Core Functions
- `apps/web/src/components/restorations/restoration-library.tsx` — gallery of restoration cards
- `apps/web/src/components/restorations/restoration-detail.tsx` — side-by-side compare + provenance + actions
- `apps/web/src/components/restorations/restoration-thumb.tsx` — fetches a presigned preview URL and paints the actual image/video
- `services/api/app/runtime/restorations.py` — routes
- `services/api/app/service/restoration.py` — `list_restorations()`, `get_restoration()`, `delete_restoration()`, `rerun_restoration()`

## Inputs
- None for the list (loads automatically)
- `asset_id` (path) for detail / preview / delete / rerun

## Outputs
- List: `Restoration[]` (each read from its `metadata.json`)
- Preview: `{ url }` — presigned URL for the source or rendition surface
- Delete: removes ONLY `restored.{png,mp4}` + `metadata.json`; the original master is retained

## Flow
- Library lists all `metadata.json` objects under `archive/restored/`, newest first
- Each card shows the original + restored thumbnails (both painted via presigned preview URLs), status, variant, device
- Detail page shows the side-by-side compare, full provenance, and Re-colorize / Delete actions
- Re-colorize opens a form pre-filled with the current params (run-with-new-params, not editing the artifact)

## Edge Cases
- Failed restoration → card shows "No rendition"; detail shows "Colorization failed — re-colorize to try again"
- Unreadable/legacy metadata.json → skipped from the list (logged), never crashes the gallery
- Preview URL unavailable → thumbnail shows an "image off" placeholder

## UX States
- Loading: skeleton grid
- Empty: "No restorations yet" with a New restoration CTA
- Error: inline error with retry

## Verification
- Test files: `services/api/tests/test_restorations.py` (list, get, delete-scope, rerun)
- Required cases: delete removes only rendition + metadata (never the source), list reads metadata.json
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: lifecycle tests green; build green with the `/restorations` routes

## Related Docs
- [Colorization](colorization.md)
- [App Workflows](../app-workflows.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
