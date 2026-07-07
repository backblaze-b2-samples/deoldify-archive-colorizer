<!-- last_verified: 2026-06-30 -->
# Tech Debt Tracker

Known tech debt items. Agents update this when they discover or create tech debt.

| Description | Impact | Proposed Resolution | Priority | Status |
|---|---|---|---|---|
| Colorization runs synchronously in the request | Long requests for large stills / any video clip; no way to queue many assets | Add an async job queue (e.g. a worker + a `pending`/`running` status on the restoration) so the create POST returns immediately and the UI polls | Medium | Open (out of scope for this sample) |
| One rendition per asset (re-colorize overwrites) | No history of prior colorization params/results for the same source | Multi-version restorations: write `restored-v{n}.png` + keep prior metadata; expose a versions list on the detail page | Low | Open (deliberately deferred — keeps storage bounded) |
| Video colorization not wired into the synchronous flow | Video sources are rejected at create time | Add a `POST /colorize-video` endpoint to the `infra/deoldify/` container that drives DeOldify's `VideoColorizer` + encodes frames → MP4 (ffmpeg is already in the image), and call it from a job worker | Medium | Open (heavier path) |
| `datetime.utcnow()` deprecated in Python 3.12+ | Naive datetimes, future breakage | Replace with `datetime.now(UTC)` in `repo/b2_client.py`, `service/metadata.py` | High | Resolved |
| S3 client recreated on every API call | Connection pool wasted, added latency | Cache client as module-level singleton via `lru_cache` | High | Resolved |
| `get_upload_stats()` pagination broken at 1000 objects | Stats silently wrong for large buckets | Check `IsTruncated` + use `ContinuationToken` | High | Resolved |
| `record_upload()` never called | `/metrics` always reports 0 uploads | Call from `runtime/upload.py` after successful upload | Medium | Resolved |
| Metrics counters not thread-safe | Race conditions under concurrent requests | Use `threading.Lock` (matches `service/files.py` pattern) | Medium | Resolved |
| `_humanize_bytes` duplicated in Python (repo + service) | DRY violation, drift risk | Extract to `app/types/formatting.py` shared util | Medium | Resolved |
| `humanizeBytes` duplicated in TypeScript | DRY violation | Extract to `lib/utils.ts` | Low | Open |
| `formatDate` duplicated in TypeScript | DRY violation | Extract to `lib/utils.ts` | Low | Open |
| No test harness for feature specs | No automated verification | Add pytest fixtures + test files per feature | Medium | Resolved (partial — tests added for upload, files, activity, errors) |

## 2026-07-07 — verify (sample-3-verify) nitpicks

Non-goal-blocking items found during end-to-end UX verification. The default first-time-user path (upload B&W → colorize with the default Artistic/Balanced preset → see color in library + detail/compare, persisted to B2) passed reliably; these are backlog polish.

- **Colorizer detail (`/restorations/[assetId]`) — Stable variant memory limit on the CPU container.** OBSERVED: switching from a just-run Artistic restoration to the heavier Stable (resnet101) model can OOM-kill the ~3.8 GiB CPU colorizer container on the first attempt (cold evict+rebuild peak), showing "Colorization failed … it likely ran out of memory". → It is gracefully handled (actionable error + Re-colorize) and recovers on retry (the crash-restart clears the model cache, so the rebuild-from-empty fits); Stable is also capped to render_factor 22 and works warm/from-empty. Root cause is torch's CPU caching allocator retaining the evicted model's memory (`malloc_trim` can't reclaim torch-pooled memory) on a small VM. Proposed: give the container more RAM for Stable (documented in RELIABILITY.md), or lower Stable's ceiling further, or serialize a proactive worker restart on variant switch.
- **Restore pass (denoise/sharpen) has no independent evidence of running.** OBSERVED: the optional Pillow restore pass is attested only by the requested flag echoed back in provenance ("Restore pass: denoise=true sharpen=false"), with no distinct output/log line. Proposed: emit a structured log line and/or surface a small "restore pass applied" indicator on the detail page.
- **Library grid + dashboard slow first paint under load.** OBSERVED: on first navigation the ~20 concurrent presigned-URL thumbnail fetches leave the grid blank / dashboard skeletons for ~3–5s before settling (then all paint correctly). Proposed: lazy-load thumbnails below the fold / cap concurrency / add a longer-lived cache of presigned URLs.
- **Dashboard counts failed restorations in "Assets Restored" / "Restorations Today".** OBSERVED: a failed restoration (metadata only, no rendition) still increments the restored tallies, mildly inflating the data-doubling story (the Storage Growth *bytes* bar correctly excludes it). Proposed: count only `status == "completed"` for those two tiles.
- **Storage Growth chart Y-axis labels clipped.** OBSERVED: axis labels render as "6 / 2 / 8 / 4 / 0" (leading chars cut, almost certainly "1.6 / 1.2 / 0.8 / 0.4 / 0 MB"). Proposed: widen the chart's left margin / axis width.
- **Sidebar nav orders Restorations above Ingest.** OBSERVED: the workflow's first step (Ingest) is listed below the second (Restorations) in the sidebar; the dashboard CTAs are correctly ordered (Ingest first). Proposed: reorder the sidebar to Dashboard → Ingest → Restorations → Files → Settings.
