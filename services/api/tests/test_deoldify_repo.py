"""No-network signature / import guard for the DeOldify repo adapter.

Asserts the adapter's public API + device detection WITHOUT downloading weights
or constructing a model, so the test suite stays fast and deterministic. True
end-to-end colorization is validated by the later `verify` pipeline step.

Two things this protects:
  * Importing app.repo.deoldify_repo must be cheap and network-free (heavy
    torch/deoldify/cv2 imports are deferred into functions, not module top level).
  * The public surface (function names + signatures + device-detect contract)
    stays stable for the service layer that calls it.
"""

import inspect

from app.repo import deoldify_repo


def test_module_imports_without_heavy_sdks():
    """Importing the adapter must not pull torch/deoldify/cv2 at module load."""
    import sys

    # The adapter module is already imported above; none of the heavy SDKs
    # should have been imported as a side effect of importing it.
    for mod in ("torch", "deoldify", "cv2", "fastai"):
        assert mod not in sys.modules, (
            f"{mod} was imported at module load — heavy SDK imports must be "
            "deferred into functions to keep the adapter import network-free"
        )


def test_public_api_present():
    for name in ("colorize_image_bytes", "encode_frames_to_mp4", "detect_device"):
        assert hasattr(deoldify_repo, name), f"missing public function {name}"


def test_colorize_signature():
    sig = inspect.signature(deoldify_repo.colorize_image_bytes)
    params = sig.parameters
    assert "image_bytes" in params
    assert params["variant"].default == "artistic"
    assert params["render_factor"].default == 30


def test_detect_device_contract():
    """detect_device never raises and returns a kind in cuda/mps/cpu."""
    info = deoldify_repo.detect_device()
    assert info.kind in {"cuda", "mps", "cpu"}
    assert isinstance(info.label, str) and info.label


def test_model_variants_and_presets():
    assert deoldify_repo.MODEL_VARIANTS == ("artistic", "stable", "video")
    assert deoldify_repo.RENDER_PRESETS == {"draft": 21, "balanced": 30, "high": 35}


def test_ensure_weights_rejects_unknown_variant():
    import pytest

    with pytest.raises(ValueError):
        deoldify_repo.ensure_weights("not-a-real-variant")
