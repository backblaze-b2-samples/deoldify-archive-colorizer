<!-- last_verified: 2026-06-30 -->
# Feature: Restore Pass (denoise + sharpen)

## Purpose
Optionally clean up the colorized output with a denoise and/or sharpen step, so scanned archival stills read more cleanly.

## Used By
- UI: the Denoise / Sharpen switches on `/restorations/new` and the Re-colorize form
- API: applied inside `POST /restorations` after colorization
- Worker: none (synchronous, in the create path)

## Core Functions
- `services/api/app/service/restore_pass.py` — `apply_restore_pass(image_bytes, *, denoise, sharpen)`
- Called by `services/api/app/service/restoration.py::_run_colorization`

## Canonical Files
- Pattern exemplar: `services/api/app/service/restore_pass.py`

## Inputs
- image_bytes: bytes (the colorized PNG from DeOldify)
- denoise: bool — median filter (knocks back scan grain)
- sharpen: bool — unsharp mask (recovers edge detail)

## Outputs
- PNG bytes after the requested steps (both off → input re-encoded unchanged)

## Flow
- After colorization, the service calls `apply_restore_pass` with the form flags
- Denoise applies a 3px median filter; sharpen applies an unsharp mask
- The result is what gets written as the restored rendition

## Why it lives in `service/`
- It is a pure, deterministic image transform built on Pillow (already a core dependency) — no model SDK. It is not a `repo/` adapter because it talks to nothing external.

## Edge Cases
- Both flags off → no-op (returns the input)
- Non-image bytes → Pillow raises; surfaced as a failed restoration with the error recorded

## Verification
- Exercised indirectly by `services/api/tests/test_restorations.py` (the restore pass is stubbed there so the lifecycle test stays independent of image decoding)
- Quick verify command: `pnpm test:api`
- Pass criteria: lifecycle tests green

## Related Docs
- [Colorization](colorization.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
