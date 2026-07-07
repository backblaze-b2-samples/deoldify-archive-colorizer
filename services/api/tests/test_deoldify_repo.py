"""Signature / import + HTTP-contract guard for the DeOldify repo adapter.

The adapter no longer runs any ML in-process — the legacy DeOldify stack lives in
the ``infra/deoldify/`` container and this module is a thin HTTP client to it.
These tests assert:

  * Importing app.repo.deoldify_repo never pulls torch/deoldify/fastai/cv2 (the
    heavy stack must not leak back into this API).
  * The public surface (colorize_image_bytes / detect_device + signatures) is
    stable for the service layer.
  * The HTTP contract: colorize POSTs to the service and maps errors to
    RuntimeError; detect_device probes /health and NEVER raises.

The network is fully stubbed (monkeypatched httpx) so the suite stays fast and
hermetic. True end-to-end colorization is validated by the `verify` pipeline step
against the running container.
"""

import inspect

from app.repo import deoldify_repo


def test_module_imports_without_heavy_sdks():
    """Importing the adapter must not pull torch/deoldify/cv2/fastai."""
    import sys

    for mod in ("torch", "torchvision", "deoldify", "cv2", "fastai"):
        assert mod not in sys.modules, (
            f"{mod} was imported by the adapter — the DeOldify model stack must "
            "live only in the infra/deoldify container, never in this API"
        )


def test_public_api_present():
    for name in ("colorize_image_bytes", "detect_device"):
        assert hasattr(deoldify_repo, name), f"missing public function {name}"


def test_colorize_signature():
    sig = inspect.signature(deoldify_repo.colorize_image_bytes)
    params = sig.parameters
    assert "image_bytes" in params
    assert params["variant"].default == "artistic"
    assert params["render_factor"].default == 22


def test_model_variants_and_presets():
    # "video" is intentionally NOT offered (still-image build only), and every
    # render preset is bounded to fit the colorizer container's memory budget so
    # none can OOM-crash the service.
    assert deoldify_repo.MODEL_VARIANTS == ("artistic", "stable")
    assert deoldify_repo.RENDER_PRESETS == {"draft": 16, "balanced": 22, "high": 24}


def test_variant_render_factor_ceilings():
    # Per-variant memory ceilings: the heavier "stable" (resnet101) OOMs at 24 on
    # the CPU container, so it is capped at 22; "artistic" (resnet34) fits at 24.
    assert deoldify_repo.VARIANT_MAX_RENDER_FACTOR == {"artistic": 24, "stable": 22}


def test_clamp_render_factor_caps_stable_high():
    # The "high" preset (24) must be clamped to 22 for stable so it never OOMs,
    # while artistic keeps 24 and values already under a ceiling pass through.
    assert deoldify_repo.clamp_render_factor("stable", 24) == 22
    assert deoldify_repo.clamp_render_factor("stable", 22) == 22
    assert deoldify_repo.clamp_render_factor("stable", 16) == 16
    assert deoldify_repo.clamp_render_factor("artistic", 24) == 24
    assert deoldify_repo.clamp_render_factor("artistic", 16) == 16
    # Unknown variant falls back to the lowest ceiling (fail-safe).
    assert deoldify_repo.clamp_render_factor("mystery", 99) == 22


class _FakeResp:
    def __init__(self, status_code=200, content=b"", json_body=None, text=""):
        self.status_code = status_code
        self.content = content
        self._json = json_body
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise deoldify_repo.httpx.HTTPStatusError(
                "err", request=None, response=None
            )

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


def test_detect_device_healthy(monkeypatch):
    monkeypatch.setattr(
        deoldify_repo.httpx,
        "get",
        lambda *a, **k: _FakeResp(json_body={"device": "cpu", "status": "ok"}),
    )
    info = deoldify_repo.detect_device()
    assert info.kind == "cpu"
    assert isinstance(info.label, str) and info.label


def test_detect_device_never_raises_when_service_down(monkeypatch):
    def _boom(*a, **k):
        raise deoldify_repo.httpx.ConnectError("connection refused")

    monkeypatch.setattr(deoldify_repo.httpx, "get", _boom)
    info = deoldify_repo.detect_device()
    assert info.kind == "cpu"
    assert "unavailable" in info.label


def test_colorize_posts_and_returns_png(monkeypatch):
    captured = {}

    def _fake_post(url, **kwargs):
        captured["url"] = url
        captured["data"] = kwargs.get("data")
        captured["files"] = kwargs.get("files")
        return _FakeResp(status_code=200, content=b"\x89PNG-colorized")

    monkeypatch.setattr(deoldify_repo.httpx, "post", _fake_post)
    out = deoldify_repo.colorize_image_bytes(
        b"bw-bytes", variant="stable", render_factor=21
    )
    assert out == b"\x89PNG-colorized"
    assert captured["url"].endswith("/colorize")
    assert captured["data"]["variant"] == "stable"
    assert captured["data"]["render_factor"] == "21"


def test_colorize_disconnect_maps_to_actionable_memory_hint(monkeypatch):
    import pytest

    def _fake_post(url, **kwargs):
        raise deoldify_repo.httpx.RemoteProtocolError(
            "Server disconnected without sending a response."
        )

    monkeypatch.setattr(deoldify_repo.httpx, "post", _fake_post)
    with pytest.raises(RuntimeError) as ei:
        deoldify_repo.colorize_image_bytes(b"x", render_factor=35)
    assert "memory" in str(ei.value).lower()


def test_colorize_raises_runtime_error_on_non_200(monkeypatch):
    import pytest

    monkeypatch.setattr(
        deoldify_repo.httpx,
        "post",
        lambda *a, **k: _FakeResp(status_code=500, json_body={"detail": "boom"}),
    )
    with pytest.raises(RuntimeError) as ei:
        deoldify_repo.colorize_image_bytes(b"x")
    assert "boom" in str(ei.value)
