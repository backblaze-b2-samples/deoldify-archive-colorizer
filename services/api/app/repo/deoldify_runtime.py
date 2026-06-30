"""Heavy DeOldify model invocation + MP4 encode. Imported lazily by deoldify_repo.

Kept separate so deoldify_repo's public surface stays importable without pulling
in torch/fastai/cv2 at module load (the no-network guard test relies on that).
This module is only imported when a real colorization actually runs.

All heavy SDK imports (torch, deoldify, cv2, imageio_ffmpeg) live here, inside
``repo/`` — same containment invariant as boto3.
"""

from __future__ import annotations

import io
import logging
import subprocess
import tempfile
from pathlib import Path

from .deoldify_repo import (
    DeviceInfo,
    _patch_torch_load_for_legacy_weights,
    _weights_dir,
    detect_device,
)

logger = logging.getLogger(__name__)


def _configure_device(device: DeviceInfo) -> None:
    """Point DeOldify's device manager at the resolved device.

    DeOldify exposes a global device singleton. CUDA selects a GPU id; anything
    else (MPS best-effort, CPU) maps to CPU in DeOldify's enum, which is the
    safe, always-available path.
    """
    from deoldify import device as deoldify_device
    from deoldify.device_id import DeviceId

    target = DeviceId.GPU0 if device.kind == "cuda" else DeviceId.CPU
    deoldify_device.set(device=target)


def _build_image_colorizer(variant: str):
    """Construct a DeOldify ImageColorizer for the variant with device fallback.

    Tries the auto-detected device first; if a non-CPU build fails (e.g. DeOldify
    on Apple MPS), falls back to CPU rather than crashing.
    """
    from deoldify.visualize import (
        get_image_colorizer,
        get_stable_image_colorizer,
    )

    _patch_torch_load_for_legacy_weights()
    root = _weights_dir().parent  # DeOldify expects models/ under this root
    artistic = variant != "stable"

    def _make():
        if artistic:
            return get_image_colorizer(root_folder=root, artistic=True)
        return get_stable_image_colorizer(root_folder=root)

    dev = detect_device()
    try:
        _configure_device(dev)
        return _make()
    except Exception as e:
        if dev.kind == "cpu":
            raise
        logger.warning(
            "Colorizer build failed on device=%s (%s); falling back to CPU",
            dev.kind,
            e,
        )
        _force_cpu()
        return _make()


def _force_cpu() -> None:
    from deoldify import device as deoldify_device
    from deoldify.device_id import DeviceId

    deoldify_device.set(device=DeviceId.CPU)


def run_image_colorizer(
    image_bytes: bytes, *, variant: str, render_factor: int
) -> bytes:
    """Colorize one image in-process and return PNG bytes of the result."""
    from PIL import Image

    colorizer = _build_image_colorizer(variant)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "source.png"
        Image.open(io.BytesIO(image_bytes)).convert("RGB").save(src)
        result = colorizer.get_transformed_image(
            str(src), render_factor=render_factor, watermarked=False
        )
        out = io.BytesIO()
        result.save(out, format="PNG")
        return out.getvalue()


def _ffmpeg_binary() -> str:
    """Resolve the bundled imageio-ffmpeg binary (not bare system ffmpeg)."""
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def encode_dir_to_mp4(frames_dir: str, *, fps: int = 24) -> bytes:
    """Encode numbered PNG frames in a dir into an H.264 MP4; return its bytes."""
    ffmpeg = _ffmpeg_binary()
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "out.mp4"
        cmd = [
            ffmpeg,
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(Path(frames_dir) / "frame_%06d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(out_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out_path.read_bytes()
