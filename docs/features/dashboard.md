<!-- last_verified: 2026-06-30 -->
# Feature: Dashboard (archival data growth)

## Purpose
Visualize the data-doubling story: how a B&W archive grows into originals plus colorized restorations, all retained in B2.

## Used By
- UI: `/` page (dashboard home)
- API: `GET /restorations/stats`, `GET /restorations`

## Core Functions
- `apps/web/src/components/dashboard/stats-cards.tsx` — 4 stat cards (assets restored, restorations today, archive footprint, data growth ratio)
- `apps/web/src/components/dashboard/upload-chart.tsx` — storage-growth bar chart: originals MB vs restored MB
- `apps/web/src/components/dashboard/recent-uploads-table.tsx` — most recent restorations
- `apps/web/src/lib/api-client.ts` — `getRestorationStats()`, `getRestorations()`
- `services/api/app/runtime/restorations.py` — `GET /restorations/stats` handler
- `services/api/app/service/restoration.py` — `get_restoration_stats()` business logic
- `services/api/app/repo/b2_client.py` — `list_files()` data access

## Canonical Files
- Stat cards: `apps/web/src/components/dashboard/stats-cards.tsx`
- Stats service logic: `services/api/app/service/restoration.py`

## Inputs
- None (dashboard loads data automatically)

## Outputs
- `GET /restorations/stats` → `RestorationStats` (total_restorations, restorations_today, originals_bytes/human, restored_bytes/human, total_bytes/human, growth_ratio)
- `GET /restorations` → `Restoration[]` for the recent-restorations table (newest first)

## Flow
- Page loads → fetches restoration stats + recent restorations
- Stat cards display assets restored, restorations today, total archive footprint, and data growth ratio (`total_bytes / originals_bytes`)
- Storage-growth chart shows originals MB vs restored MB side by side
- Recent restorations table links to each detail page with variant, updated time, status

## Edge Cases
- API unavailable → inline error states with retry
- No data yet → empty chart + empty table messages
- Large object count → stats aggregation lists up to 1000 objects per prefix (extend with pagination if the archive grows beyond that)

## UX States
- Loading: skeleton placeholders for cards, chart, table
- Empty: "No archive data yet" / "No restorations yet"
- Loaded: populated cards, chart, table

## Verification
- Test files: `services/api/tests/test_restorations.py`
- Required cases: stats aggregation, recent restorations, API error fallback
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: all pytest tests green, no ruff violations

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [App Workflows](../app-workflows.md)
