"""Restoration lifecycle tests — repo calls (B2 + model) are monkeypatched so
the suite stays fast and never touches the network or downloads weights."""

from datetime import UTC, datetime

import pytest

from app.repo.deoldify_repo import DeviceInfo
from app.service import restoration as svc
from app.types import FileMetadata, RestorationParams


def _meta(key: str, size: int = 1024) -> FileMetadata:
    return FileMetadata(
        key=key,
        filename=key.rsplit("/", 1)[-1],
        folder="archive/originals/",
        size_bytes=size,
        size_human="1.0 KB",
        content_type="image/png",
        uploaded_at=datetime.now(UTC),
        url=None,
    )


def _patch_happy_path(monkeypatch, uploaded: dict):
    monkeypatch.setattr(svc, "get_file_metadata", lambda key: _meta(key))
    monkeypatch.setattr(svc, "get_object_bytes", lambda key: b"fake-bw-bytes")
    monkeypatch.setattr(
        svc, "detect_device", lambda: DeviceInfo(kind="cpu", label="cpu")
    )
    monkeypatch.setattr(
        svc,
        "colorize_image_bytes",
        lambda b, **kw: b"fake-color-png",
    )
    # The restore pass runs real Pillow filters; stub it so the test stays
    # independent of image decoding (colorization itself is already stubbed).
    monkeypatch.setattr(
        svc, "apply_restore_pass", lambda b, **kw: b"fake-restored-png"
    )

    def _fake_upload(data, key, content_type):
        uploaded[key] = (data, content_type)
        return _meta(key, size=len(data))

    monkeypatch.setattr(svc, "upload_file", _fake_upload)


def test_asset_id_is_stable_and_safe():
    a = svc.asset_id_for("archive/originals/scan 01.tiff")
    b = svc.asset_id_for("archive/originals/scan 01.tiff")
    assert a == b
    assert all(c.isalnum() or c in "-_" for c in a)


def test_create_writes_rendition_and_metadata(monkeypatch):
    uploaded: dict = {}
    _patch_happy_path(monkeypatch, uploaded)

    record = svc.create_restoration(
        "archive/originals/scan.png", RestorationParams()
    )

    assert record.status == "completed"
    assert record.media_type == "image"
    assert record.rendition_key.endswith("restored.png")
    assert record.metadata_key.endswith("metadata.json")
    assert record.device == "cpu"
    assert record.render_factor == 30  # balanced
    # Both the rendition and the metadata.json were written to B2.
    assert record.rendition_key in uploaded
    assert record.metadata_key in uploaded
    assert uploaded[record.metadata_key][1] == "application/json"


def test_create_rejects_source_outside_originals(monkeypatch):
    monkeypatch.setattr(svc, "get_file_metadata", lambda key: _meta(key))
    with pytest.raises(svc.RestorationError):
        svc.create_restoration("uploads/scan.png", RestorationParams())


def test_create_records_failure_status_when_model_raises(monkeypatch):
    uploaded: dict = {}
    _patch_happy_path(monkeypatch, uploaded)

    def _boom(b, **kw):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(svc, "colorize_image_bytes", _boom)

    record = svc.create_restoration(
        "archive/originals/scan.png", RestorationParams()
    )
    assert record.status == "failed"
    assert "model exploded" in (record.error or "")
    # metadata.json still written so the asset is visible in the library
    assert record.metadata_key in uploaded
    # but no rendition was uploaded on failure
    assert record.rendition_key not in uploaded


def test_delete_only_removes_rendition_and_metadata(monkeypatch):
    deleted: list[str] = []
    record = svc.Restoration(
        asset_id="scan-abc123",
        source_key="archive/originals/scan.png",
        rendition_key="archive/restored/scan-abc123/restored.png",
        metadata_key="archive/restored/scan-abc123/metadata.json",
        media_type="image",
        params=RestorationParams(),
        status="completed",
        model_version="DeOldify",
        device="cpu",
        render_factor=30,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr(svc, "get_restoration", lambda aid: record)
    monkeypatch.setattr(svc, "delete_file", lambda key: deleted.append(key))

    svc.delete_restoration("scan-abc123")

    assert record.rendition_key in deleted
    assert record.metadata_key in deleted
    # The source master is NOT among the deletions — that's the whole point.
    assert record.source_key not in deleted


@pytest.mark.asyncio
async def test_create_endpoint(client, monkeypatch):
    uploaded: dict = {}
    _patch_happy_path(monkeypatch, uploaded)
    resp = await client.post(
        "/restorations",
        json={"source_key": "archive/originals/scan.png"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["source_key"] == "archive/originals/scan.png"
