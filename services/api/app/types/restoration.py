from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Finite-option fields the UI surfaces as selectors/switches.
ModelVariant = Literal["artistic", "stable", "video"]
RenderQuality = Literal["draft", "balanced", "high"]
RestorationStatus = Literal["completed", "failed"]


class RestorationParams(BaseModel):
    """Colorization parameters chosen on the create / re-colorize form."""

    model_variant: ModelVariant = "artistic"
    render_quality: RenderQuality = "balanced"
    denoise: bool = True
    sharpen: bool = False


class CreateRestorationRequest(BaseModel):
    """POST body for /restorations — the source original + params."""

    source_key: str = Field(..., min_length=1)
    params: RestorationParams = RestorationParams()


class RerunRestorationRequest(BaseModel):
    """POST body for /restorations/<asset_id>/rerun — new params, same source."""

    params: RestorationParams


class Restoration(BaseModel):
    """One B&W source original + its colorized rendition + provenance.

    Persisted as the object set under ``archive/restored/<asset_id>/`` (the
    rendition file plus a ``metadata.json`` mirroring this model).
    """

    asset_id: str
    source_key: str
    rendition_key: str
    metadata_key: str
    media_type: Literal["image", "video"]
    params: RestorationParams
    status: RestorationStatus
    error: str | None = None
    # Provenance
    model_version: str
    device: str
    render_factor: int
    source_size_bytes: int = 0
    rendition_size_bytes: int = 0
    created_at: datetime
    updated_at: datetime


class RestorationStats(BaseModel):
    """Archival data-growth metrics for the dashboard."""

    total_restorations: int
    restorations_today: int
    originals_bytes: int
    originals_human: str
    restored_bytes: int
    restored_human: str
    total_bytes: int
    total_human: str
    growth_ratio: float
