"""Optional restore pass: denoise + sharpen on a colorized still.

Pure image transform built on Pillow (already a core dependency, used by
metadata extraction). No model SDK here — this is a deterministic post-process
applied after DeOldify colorization, gated by the create-form switches.
"""

from __future__ import annotations

import io


def apply_restore_pass(
    image_bytes: bytes, *, denoise: bool, sharpen: bool
) -> bytes:
    """Return PNG bytes after the requested denoise / sharpen steps.

    Both flags off is a no-op (returns the input re-encoded as PNG). Denoise
    uses a light median filter to knock back scan grain; sharpen uses an
    unsharp mask to recover edge detail.
    """
    if not denoise and not sharpen:
        return image_bytes

    from PIL import Image, ImageFilter

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if denoise:
        img = img.filter(ImageFilter.MedianFilter(size=3))
    if sharpen:
        img = img.filter(
            ImageFilter.UnsharpMask(radius=2, percent=120, threshold=3)
        )
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
