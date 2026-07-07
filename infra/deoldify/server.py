"""DeOldify colorization microservice (FastAPI, CPU-only).

This is the ONLY place the legacy DeOldify / fastai-v1 / torch-1.11 stack runs.
It is deliberately stateless and credential-free: it knows nothing about B2 or
boto3. The modern Python-3.11 API fetches the B&W original from B2, POSTs the
bytes here, and persists the returned PNG back to B2.

Why a separate process at all: DeOldify's image colorizer requires the fastai-v1
API (torch 1.11 / fastai 1.0.60 / Pillow<10), which is irreconcilable with the
modern API's fastai-2 / torch-2 / Python-3.11 environment. Isolating it in an
arm64 container is the only way both stacks coexist.

Colorizers are built lazily and cached, but only ONE variant is ever resident
at a time: the ~3.8 GiB container cannot hold two ~2 GiB models plus a forward
pass without being OOM-killed, so switching variants evicts and frees the
previously-cached model before building the new one. The first request for a
given variant (or the first after a switch) pays the model-load cost (~seconds;
weights + the resnet backbone are baked into the image at build time, so no
network at request time).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import gc
import io
import logging
import threading
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("deoldify-service")

# DeOldify convention: `from deoldify import device` and set the device BEFORE
# importing deoldify.visualize (which pulls in fastai/torch). Force CPU — there
# is no GPU in this container and DeOldify's stack has no usable MPS path.
from deoldify import device as deoldify_device  # noqa: E402
from deoldify.device_id import DeviceId  # noqa: E402

deoldify_device.set(device=DeviceId.CPU)

from deoldify.visualize import (  # noqa: E402
    get_image_colorizer,
    get_stable_image_colorizer,
)
from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import JSONResponse, Response  # noqa: E402
from PIL import Image  # noqa: E402

# DeOldify expects `<root>/models/<weight>.pth`. Weights are baked here at build.
DEOLDIFY_ROOT = Path("/opt/DeOldify")

VARIANTS = ("artistic", "stable")

_colorizers: dict[str, object] = {}
_build_lock = threading.Lock()


def _release_memory() -> None:
    """Free unreferenced Python objects AND return the freed heap to the OS.

    `gc.collect()` alone is not enough here: an evicted ~2 GiB DeOldify model is
    dropped at the Python level but glibc retains the freed arenas in the
    process RSS, so building the next model on top would push peak memory past
    the ~3.8 GiB container ceiling and get it OOM-killed. `malloc_trim(0)` forces
    glibc to release that freed memory back to the OS. No-op if the C library has
    no `malloc_trim` (e.g. musl).
    """
    gc.collect()
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6")
        libc.malloc_trim(0)
    except (OSError, AttributeError):  # pragma: no cover - platform dependent
        pass


app = FastAPI(
    title="DeOldify Colorization Service",
    description="Stateless CPU image colorization over HTTP (legacy DeOldify stack).",
    version="1.0.0",
)


def _normalize_variant(variant: str) -> str:
    """Map anything that isn't 'stable' to 'artistic' (incl. legacy 'video')."""
    v = (variant or "").strip().lower()
    return "stable" if v == "stable" else "artistic"


def _get_colorizer(variant: str):
    """Build + return the DeOldify colorizer for a variant (thread-safe, lazy).

    Single-slot cache: at most one model is resident at a time. If a different
    variant is currently cached, it is evicted and freed BEFORE the new one is
    built, so peak memory is one model plus one forward pass — never two models.
    Alternating variants re-pays the ~seconds model-load cost, which is an
    acceptable trade for this single-user sample versus an OOM crash.
    """
    variant = _normalize_variant(variant)
    cached = _colorizers.get(variant)
    if cached is not None:
        return cached
    with _build_lock:
        cached = _colorizers.get(variant)
        if cached is not None:
            return cached
        # Evict + free any other resident variant before building this one, so
        # two ~2 GiB models never coexist and OOM-kill the container.
        if _colorizers:
            evicted = list(_colorizers.keys())
            _colorizers.clear()
            _release_memory()
            logger.info("Evicted cached colorizer(s)=%s before building %s", evicted, variant)
        logger.info("Building DeOldify colorizer variant=%s (first use)", variant)
        deoldify_device.set(device=DeviceId.CPU)  # re-assert CPU before build
        if variant == "stable":
            colorizer = get_stable_image_colorizer(root_folder=DEOLDIFY_ROOT)
        else:
            colorizer = get_image_colorizer(root_folder=DEOLDIFY_ROOT, artistic=True)
        _colorizers[variant] = colorizer
        logger.info("Colorizer ready variant=%s", variant)
        return colorizer


@app.get("/health")
async def health() -> JSONResponse:
    """Liveness + capability probe. Always CPU in this container."""
    return JSONResponse(
        {"status": "ok", "device": "cpu", "variants": list(VARIANTS)}
    )


@app.post("/colorize")
def colorize(
    file: UploadFile = File(...),
    variant: str = Form("artistic"),
    render_factor: int = Form(30),
) -> Response:
    """Colorize a single B&W image on CPU and return the PNG bytes.

    Sync `def` so FastAPI runs it in a worker thread — the CPU-bound render
    never blocks the event loop, keeping /health responsive during a render.
    """
    resolved = _normalize_variant(variant)
    try:
        raw = file.file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Empty file upload.")
        try:
            source = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as e:  # noqa: BLE001
            raise HTTPException(
                status_code=400, detail=f"Not a decodable image: {e}"
            ) from e

        colorizer = _get_colorizer(resolved)

        # get_transformed_image takes a path; write the source to a temp file.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            src_path = Path(tmp) / "source.png"
            source.save(src_path)
            result = colorizer.get_transformed_image(
                str(src_path),
                render_factor=int(render_factor),
                watermarked=False,
            )
            out = io.BytesIO()
            result.save(out, format="PNG")
            payload = out.getvalue()
            del result

        # Release the forward-pass buffers (fastai/torch tensors + the decoded
        # image) so idle memory returns to the one-model baseline between renders.
        _release_memory()

        logger.info(
            "Colorized variant=%s render_factor=%s in_bytes=%s out_bytes=%s",
            resolved,
            render_factor,
            len(raw),
            len(payload),
        )
        return Response(
            content=payload,
            media_type="image/png",
            headers={"X-Deoldify-Device": "cpu"},
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("Colorization failed")
        raise HTTPException(status_code=500, detail=f"Colorization failed: {e}") from e
