<!-- last_verified: 2026-06-30 -->
# Tech Debt Tracker

Known tech debt items. Agents update this when they discover or create tech debt.

| Description | Impact | Proposed Resolution | Priority | Status |
|---|---|---|---|---|
| Colorization runs synchronously in the request | Long requests for large stills / any video clip; no way to queue many assets | Add an async job queue (e.g. a worker + a `pending`/`running` status on the restoration) so the create POST returns immediately and the UI polls | Medium | Open (out of scope for this sample) |
| One rendition per asset (re-colorize overwrites) | No history of prior colorization params/results for the same source | Multi-version restorations: write `restored-v{n}.png` + keep prior metadata; expose a versions list on the detail page | Low | Open (deliberately deferred — keeps storage bounded) |
| Video colorization not wired into the synchronous flow | Video sources are rejected at create time | Drive `VideoColorizer` from a job worker; encode frames → MP4 via the bundled `imageio-ffmpeg` (`encode_frames_to_mp4` already in the adapter) | Medium | Open (heavier path) |
| `datetime.utcnow()` deprecated in Python 3.12+ | Naive datetimes, future breakage | Replace with `datetime.now(UTC)` in `repo/b2_client.py`, `service/metadata.py` | High | Resolved |
| S3 client recreated on every API call | Connection pool wasted, added latency | Cache client as module-level singleton via `lru_cache` | High | Resolved |
| `get_upload_stats()` pagination broken at 1000 objects | Stats silently wrong for large buckets | Check `IsTruncated` + use `ContinuationToken` | High | Resolved |
| `record_upload()` never called | `/metrics` always reports 0 uploads | Call from `runtime/upload.py` after successful upload | Medium | Resolved |
| Metrics counters not thread-safe | Race conditions under concurrent requests | Use `threading.Lock` (matches `service/files.py` pattern) | Medium | Resolved |
| `_humanize_bytes` duplicated in Python (repo + service) | DRY violation, drift risk | Extract to `app/types/formatting.py` shared util | Medium | Resolved |
| `humanizeBytes` duplicated in TypeScript | DRY violation | Extract to `lib/utils.ts` | Low | Open |
| `formatDate` duplicated in TypeScript | DRY violation | Extract to `lib/utils.ts` | Low | Open |
| No test harness for feature specs | No automated verification | Add pytest fixtures + test files per feature | Medium | Resolved (partial — tests added for upload, files, activity, errors) |
