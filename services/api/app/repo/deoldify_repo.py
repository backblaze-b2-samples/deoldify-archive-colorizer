"""DeOldify model adapter — the ONLY place DeOldify / torch / fastai are imported.

Same containment invariant as boto3: heavy ML SDKs stay inside ``repo/`` so the
service/runtime layers depend only on plain functions and bytes. ``tests/
test_structure.py`` enforces this.

Everything here is fully local — there is no external API key. Weights download
on first use into a gitignored ``models/`` dir (~250 MB per variant).

Design notes that make this both correct and testable:

* Heavy imports (``torch``, ``deoldify``, ``cv2``) happen *inside* functions, not
  at module top level, so importing this module is cheap and network-free. The
  no-network signature guard test imports it and asserts the public API + device
  detection without ever downloading weights or constructing a model.
* ``detect_device`` picks the first available of CUDA -> Apple MPS -> CPU and
  defaults to CPU. DeOldify rides an older fastai/torch stack with weak MPS
  support, so MPS is treated as best-effort: if a colorizer build fails on MPS we
  fall back CUDA -> CPU rather than crashing.
* torch >= 2.x flipped ``torch.load`` to ``weights_only=True`` by default, which
  breaks DeOldify's legacy pickled ``.pth`` weights. ``_patch_torch_load_for_legacy_weights``
  forces ``weights_only=False`` for the model-load call so legacy checkpoints load.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Image model variants DeOldify ships. "video" uses the dedicated video model.
MODEL_VARIANTS = ("artistic", "stable", "video")

# Upstream weight files + their canonical download URLs. Kept here so the
# download is reproducible and documented in one place.
_WEIGHTS = {
    "artistic": (
        "ColorizeArtistic_gen.pth",
        "https://huggingface.co/spaces/aryadytm/photo-colorization/resolve/main/models/ColorizeArtistic_gen.pth",
    ),
    "stable": (
        "ColorizeStable_gen.pth",
        "https://huggingface.co/spaces/aryadytm/photo-colorization/resolve/main/models/ColorizeStable_gen.pth",
    ),
    "video": (
        "ColorizeVideo_gen.pth",
        "https://data.deepai.org/deoldify/ColorizeVideo_gen.pth",
    ),
}

# Render-factor presets surfaced in the UI as quality levels.
RENDER_PRESETS = {"draft": 21, "balanced": 30, "high": 35}


@dataclass(frozen=True)
class DeviceInfo:
    """Resolved compute device. ``kind`` is one of cuda/mps/cpu."""

    kind: str
    label: str


def detect_device() -> DeviceInfo:
    """Auto-detect the best available device: CUDA -> Apple MPS -> CPU.

    Never raises and never hard-requires a GPU — defaults to CPU. Importing
    torch here (inside the function) keeps module import cheap and network-free.
    """
    try:
        import torch
    except Exception:  # torch not installed (core deps only) -> CPU
        return DeviceInfo(kind="cpu", label="cpu (torch unavailable)")

    if torch.cuda.is_available():
        return DeviceInfo(kind="cuda", label="cuda")

    mps = getattr(getattr(torch, "backends", None), "mps", None)
    if mps is not None and mps.is_available():
        # DeOldify's older stack has weak MPS support; we expose it but the
        # colorizer builder will fall back CUDA -> CPU if a build fails on MPS.
        return DeviceInfo(kind="mps", label="mps (best-effort; may fall back to cpu)")

    return DeviceInfo(kind="cpu", label="cpu")


def _weights_dir() -> Path:
    from app.config import settings

    p = Path(settings.model_weights_dir)
    if not p.is_absolute():
        # Anchor at services/api/ (three levels up from this file).
        p = Path(__file__).resolve().parents[2] / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_weights(variant: str) -> Path:
    """Download the variant's weights into the gitignored models/ dir if absent.

    Returns the local path. Raises ValueError for an unknown variant and
    RuntimeError if the download fails.
    """
    if variant not in _WEIGHTS:
        raise ValueError(f"Unknown model variant: {variant!r}")
    filename, url = _WEIGHTS[variant]
    dest = _weights_dir() / filename
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    import urllib.request

    logger.info("Downloading DeOldify weights variant=%s -> %s", variant, dest)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(dest)
    except Exception as e:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to download weights for {variant!r}: {e}") from e
    return dest


def _patch_torch_load_for_legacy_weights() -> None:
    """Force weights_only=False so DeOldify's legacy pickled .pth weights load.

    torch >= 2.x defaults torch.load to weights_only=True, which refuses the
    arbitrary pickled objects in DeOldify's checkpoints. We register the known
    safe globals (best effort) and wrap torch.load to default weights_only=False.
    Idempotent — safe to call before each model load.
    """
    import torch

    serialization = getattr(torch, "serialization", None)
    add_safe_globals = getattr(serialization, "add_safe_globals", None)
    if callable(add_safe_globals):
        try:  # best effort — allowlist the numpy reconstruct path DeOldify uses
            import numpy.core.multiarray as ma

            add_safe_globals([ma._reconstruct])
        except Exception:
            pass

    if getattr(torch.load, "_deoldify_patched", False):
        return
    _orig_load = torch.load

    def _patched_load(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return _orig_load(*args, **kwargs)

    _patched_load._deoldify_patched = True  # type: ignore[attr-defined]
    torch.load = _patched_load  # type: ignore[assignment]


def colorize_image_bytes(
    image_bytes: bytes,
    *,
    variant: str = "artistic",
    render_factor: int = 30,
) -> bytes:
    """Colorize a single B&W image and return the PNG bytes of the result.

    Runs DeOldify's ImageColorizer fully locally. Honors device auto-detect
    (CUDA -> MPS -> CPU) with graceful MPS fallback. Network access only happens
    the first time, to fetch the weights.
    """
    from .deoldify_runtime import run_image_colorizer

    if variant == "video":
        variant = "artistic"  # video model colorizes frames, not lone stills
    ensure_weights(variant)
    return run_image_colorizer(
        image_bytes, variant=variant, render_factor=render_factor
    )


def encode_frames_to_mp4(frames_dir: str, fps: int = 24) -> bytes:
    """Encode a directory of colorized frames into an MP4 and return its bytes.

    Uses the bundled imageio-ffmpeg binary (NOT bare system ffmpeg, which on
    Homebrew ships without reliable codecs).
    """
    from .deoldify_runtime import encode_dir_to_mp4

    return encode_dir_to_mp4(frames_dir, fps=fps)
