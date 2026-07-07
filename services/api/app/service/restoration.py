"""Restoration lifecycle business logic.

A Restoration = one B&W source original + its colorized/restored rendition +
provenance metadata, stored as the object set under
``archive/restored/<asset_id>/``. All B2 + model calls go through ``repo/``;
this layer holds the orchestration and validation.

Processing is synchronous on submit (single still is the verifiable path; short
clips are the heavier video path). An async job queue is deliberately out of
scope — see docs/exec-plans/tech-debt-tracker.md.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime

from app.config import settings
from app.repo import (
    clamp_render_factor,
    colorize_image_bytes,
    delete_file,
    detect_device,
    get_file_metadata,
    get_object_bytes,
    list_files,
    upload_file,
)
from app.service.restore_pass import apply_restore_pass
from app.types import Restoration, RestorationParams
from app.types.formatting import humanize_bytes

logger = logging.getLogger(__name__)

MODEL_VERSION = "DeOldify NoGAN (jantic/DeOldify)"
# Render-factor per quality preset. Bounded so no preset OOM-kills the colorizer
# container on the default ~4 GiB budget (render_factor 28+ exceeds it). See
# docs/RELIABILITY.md; keep in lockstep with deoldify_repo.RENDER_PRESETS.
_RENDER_FACTORS = {"draft": 16, "balanced": 22, "high": 24}
_VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv")


class RestorationError(Exception):
    """Raised when a restoration request is invalid or cannot be served."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def asset_id_for(source_key: str) -> str:
    """Stable, filesystem-safe asset id derived from the source key.

    Re-running the same original therefore overwrites the same asset (no
    unbounded versioning), which is the documented run/re-colorize behavior.
    """
    digest = hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:12]
    stem = source_key.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    safe_stem = "".join(c if c.isalnum() or c in "-_" else "-" for c in stem)[:40]
    return f"{safe_stem}-{digest}" if safe_stem else digest


def _media_type(source_key: str) -> str:
    return "video" if source_key.lower().endswith(_VIDEO_EXTENSIONS) else "image"


def _restored_dir(asset_id: str) -> str:
    return f"{settings.restored_prefix}{asset_id}/"


def list_source_originals() -> list[dict]:
    """List ingested B&W masters under archive/originals/ for the source picker."""
    files = list_files(prefix=settings.originals_prefix, max_keys=1000)
    return [
        {
            "key": f.key,
            "filename": f.filename,
            "size_human": f.size_human,
            "content_type": f.content_type,
        }
        for f in files
        if not f.key.endswith("/")
    ]


def _run_colorization(
    source_bytes: bytes, params: RestorationParams, render_factor: int
) -> tuple[bytes, str]:
    """Colorize at the given (already variant-clamped) render_factor; returns (bytes, device)."""
    device = detect_device()
    colorized = colorize_image_bytes(
        source_bytes,
        variant=params.model_variant,
        render_factor=render_factor,
    )
    restored = apply_restore_pass(
        colorized, denoise=params.denoise, sharpen=params.sharpen
    )
    return restored, device.label


def _persist(
    *,
    asset_id: str,
    source_key: str,
    rendition_bytes: bytes,
    render_factor: int,
    device: str,
    params: RestorationParams,
    status: str,
    source_size: int,
    error: str | None,
    created_at: datetime,
) -> Restoration:
    """Write the rendition + metadata.json to B2 and return the Restoration."""
    media_type = _media_type(source_key)
    ext = "mp4" if media_type == "video" else "png"
    rendition_key = f"{_restored_dir(asset_id)}restored.{ext}"
    metadata_key = f"{_restored_dir(asset_id)}metadata.json"
    now = datetime.now(UTC)

    rendition_size = 0
    if status == "completed":
        content_type = "video/mp4" if media_type == "video" else "image/png"
        upload_file(rendition_bytes, rendition_key, content_type)
        rendition_size = len(rendition_bytes)

    record = Restoration(
        asset_id=asset_id,
        source_key=source_key,
        rendition_key=rendition_key,
        metadata_key=metadata_key,
        media_type=media_type,
        params=params,
        status=status,
        error=error,
        model_version=MODEL_VERSION,
        device=device,
        render_factor=render_factor,
        source_size_bytes=source_size,
        rendition_size_bytes=rendition_size,
        created_at=created_at,
        updated_at=now,
    )
    upload_file(
        record.model_dump_json(indent=2).encode("utf-8"),
        metadata_key,
        "application/json",
    )
    return record


def create_restoration(source_key: str, params: RestorationParams) -> Restoration:
    """Colorize a source original and persist the rendition + provenance.

    Synchronous. On model failure the metadata.json is still written with
    status="failed" so the asset is visible and inspectable in the library.
    """
    if not source_key.startswith(settings.originals_prefix):
        raise RestorationError(
            f"Source must be an ingested original under {settings.originals_prefix}"
        )
    meta = get_file_metadata(source_key)
    if meta is None:
        raise RestorationError("Source original not found", status_code=404)
    if _media_type(source_key) == "video":
        raise RestorationError(
            "Video colorization is the heavier path and is not enabled in this "
            "build's synchronous flow; pick an image master.",
            status_code=400,
        )

    asset_id = asset_id_for(source_key)
    created_at = datetime.now(UTC)
    source_bytes = get_object_bytes(source_key)
    # Effective render_factor = preset clamped to the variant's memory ceiling,
    # resolved ONCE before the render so what we send and what we record match.
    render_factor = clamp_render_factor(
        params.model_variant, _RENDER_FACTORS[params.render_quality]
    )
    try:
        rendition, device = _run_colorization(source_bytes, params, render_factor)
        return _persist(
            asset_id=asset_id,
            source_key=source_key,
            rendition_bytes=rendition,
            render_factor=render_factor,
            device=device,
            params=params,
            status="completed",
            source_size=meta.size_bytes,
            error=None,
            created_at=created_at,
        )
    except Exception as e:
        logger.error("Colorization failed for %s: %s", source_key, e, exc_info=True)
        return _persist(
            asset_id=asset_id,
            source_key=source_key,
            rendition_bytes=b"",
            render_factor=render_factor,
            device=detect_device().label,
            params=params,
            status="failed",
            source_size=meta.size_bytes,
            error=str(e),
            created_at=created_at,
        )


def rerun_restoration(asset_id: str, params: RestorationParams) -> Restoration:
    """Re-colorize the SAME source with new params, overwriting the rendition."""
    existing = get_restoration(asset_id)
    if existing is None:
        raise RestorationError("Restoration not found", status_code=404)
    return create_restoration(existing.source_key, params)


def get_restoration(asset_id: str) -> Restoration | None:
    """Load a restoration's provenance from its metadata.json."""
    try:
        raw = get_object_bytes(f"{_restored_dir(asset_id)}metadata.json")
    except RuntimeError:
        return None
    try:
        return Restoration.model_validate_json(raw)
    except Exception:
        return None


def list_restorations() -> list[Restoration]:
    """List all restorations by reading each asset's metadata.json."""
    files = list_files(prefix=settings.restored_prefix, max_keys=1000)
    records: list[Restoration] = []
    for f in files:
        if not f.key.endswith("/metadata.json"):
            continue
        try:
            raw = get_object_bytes(f.key)
            records.append(Restoration.model_validate_json(raw))
        except Exception:
            logger.warning("Skipping unreadable restoration metadata: %s", f.key)
    records.sort(key=lambda r: r.updated_at, reverse=True)
    return records


def delete_restoration(asset_id: str) -> None:
    """Delete ONLY the restored rendition + metadata.json.

    The source master under archive/originals/ is never touched — retaining it
    is the entire point of the archive.
    """
    record = get_restoration(asset_id)
    if record is None:
        raise RestorationError("Restoration not found", status_code=404)
    delete_file(record.rendition_key)
    delete_file(record.metadata_key)


def get_restoration_stats() -> dict:
    """Aggregate the archival data-growth metrics for the dashboard."""
    originals = list_files(prefix=settings.originals_prefix, max_keys=1000)
    restored = list_files(prefix=settings.restored_prefix, max_keys=1000)

    originals_bytes = sum(f.size_bytes for f in originals if not f.key.endswith("/"))
    # Count only rendition files (exclude metadata.json) toward "restored bytes".
    rendition_files = [
        f
        for f in restored
        if not f.key.endswith("/") and not f.key.endswith("metadata.json")
    ]
    restored_bytes = sum(f.size_bytes for f in rendition_files)
    total_bytes = originals_bytes + restored_bytes

    metadata_files = [f for f in restored if f.key.endswith("/metadata.json")]
    today = datetime.now(UTC).date()
    restorations_today = sum(
        1 for f in metadata_files if f.uploaded_at.date() == today
    )
    ratio = (total_bytes / originals_bytes) if originals_bytes else 1.0

    return {
        "total_restorations": len(metadata_files),
        "restorations_today": restorations_today,
        "originals_bytes": originals_bytes,
        "originals_human": humanize_bytes(originals_bytes),
        "restored_bytes": restored_bytes,
        "restored_human": humanize_bytes(restored_bytes),
        "total_bytes": total_bytes,
        "total_human": humanize_bytes(total_bytes),
        "growth_ratio": round(ratio, 2),
    }


def parse_metadata_json(raw: bytes) -> dict:
    """Helper for tooling/tests — parse a metadata.json into a plain dict."""
    return json.loads(raw)
