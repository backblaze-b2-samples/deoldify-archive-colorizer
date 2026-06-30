import logging

from fastapi import APIRouter, HTTPException

from app.service.files import FileKeyError, FileNotFoundError, get_preview_url
from app.service.restoration import (
    RestorationError,
    create_restoration,
    delete_restoration,
    get_restoration,
    get_restoration_stats,
    list_restorations,
    list_source_originals,
    rerun_restoration,
)
from app.types import (
    CreateRestorationRequest,
    RerunRestorationRequest,
    Restoration,
    RestorationStats,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/restorations", response_model=list[Restoration])
async def list_restorations_endpoint():
    return list_restorations()


@router.get("/restorations/sources")
async def list_sources_endpoint():
    """Ingested B&W masters that can be colorized (create-form source picker)."""
    return {"sources": list_source_originals()}


@router.get("/restorations/stats", response_model=RestorationStats)
async def restoration_stats_endpoint():
    return RestorationStats(**get_restoration_stats())


@router.post("/restorations", response_model=Restoration)
async def create_restoration_endpoint(body: CreateRestorationRequest):
    try:
        return create_restoration(body.source_key, body.params)
    except RestorationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/restorations/{asset_id}", response_model=Restoration)
async def get_restoration_endpoint(asset_id: str):
    record = get_restoration(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Restoration not found")
    return record


@router.post("/restorations/{asset_id}/rerun", response_model=Restoration)
async def rerun_restoration_endpoint(asset_id: str, body: RerunRestorationRequest):
    try:
        return rerun_restoration(asset_id, body.params)
    except RestorationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.delete("/restorations/{asset_id}")
async def delete_restoration_endpoint(asset_id: str):
    try:
        delete_restoration(asset_id)
    except RestorationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None
    logger.info("Restoration deleted: asset_id=%s", asset_id)
    return {"deleted": True, "asset_id": asset_id}


@router.get("/restorations/{asset_id}/preview")
async def restoration_preview_endpoint(asset_id: str, target: str = "rendition"):
    """Presigned preview URL for an asset's original or restored rendition."""
    record = get_restoration(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Restoration not found")
    key = record.source_key if target == "source" else record.rendition_key
    try:
        return {"url": get_preview_url(key)}
    except FileKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
