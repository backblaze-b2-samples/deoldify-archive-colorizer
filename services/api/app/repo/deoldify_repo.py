"""DeOldify colorization adapter — HTTP client to the colorization microservice.

The legacy DeOldify stack (fastai-v1 / torch-1.11 / Pillow<10) is irreconcilable
with this API's modern fastai-2 / torch-2 / Python-3.11 environment, so it runs
in its own native linux/arm64 container (see ``infra/deoldify/``). This adapter is
the ONLY seam that talks to it: it POSTs image bytes and gets colorized PNG bytes
back. No torch / deoldify / fastai is imported anywhere in this API anymore — the
model stack lives entirely in the container.

Design notes:

* This module imports only ``httpx`` (a light HTTP client) and stdlib, so
  importing it stays cheap and network-free. ``tests/test_deoldify_repo.py``
  asserts the heavy SDKs are never pulled in at import time.
* ``detect_device`` probes the service's ``/health`` and NEVER raises — on any
  error it reports CPU with a "service unavailable" label, preserving the
  original always-returns-a-DeviceInfo contract for the service layer.
* ``colorize_image_bytes`` raises ``RuntimeError`` on a non-200 so that
  ``service.restoration.create_restoration`` records status="failed" with a
  clear message (its except-clause depends on this).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Image model variants DeOldify ships and this synchronous still-image flow
# supports. (The dedicated "video" model is intentionally not exposed — this
# build colorizes lone stills, not frames.)
MODEL_VARIANTS = ("artistic", "stable")

# Render-factor presets surfaced in the UI as quality levels. Kept in lockstep
# with service.restoration._RENDER_FACTORS. Values are bounded so no preset can
# OOM-kill the colorizer container on the default ~4 GiB budget (render_factor
# 28+ exceeds it); see that module's comment and docs/RELIABILITY.md.
RENDER_PRESETS = {"draft": 16, "balanced": 22, "high": 24}

# Per-variant render_factor ceilings for the CPU container's ~3.8 GiB budget.
# The heavier "stable" model (resnet101) OOM-crashes at render_factor 24 (the
# "high" preset) even on a single still, while "artistic" (resnet34) fits at 24.
# The effective render_factor is clamped to these ceilings before the render so
# no selectable variant x preset combo (e.g. stable + High) can crash the
# service. See docs/RELIABILITY.md.
VARIANT_MAX_RENDER_FACTOR = {"artistic": 24, "stable": 22}


def clamp_render_factor(variant: str, render_factor: int) -> int:
    """Cap render_factor at the variant's memory ceiling (see the map above).

    Unknown variants fall back to the lowest ceiling so an unexpected value can
    never exceed a safe budget.
    """
    ceiling = VARIANT_MAX_RENDER_FACTOR.get(
        variant, min(VARIANT_MAX_RENDER_FACTOR.values())
    )
    return min(render_factor, ceiling)

# Timeouts: connect fast, but allow a long read — CPU colorization of a large
# scan can take minutes in-container with no GPU.
_COLORIZE_TIMEOUT = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=10.0)
_HEALTH_TIMEOUT = httpx.Timeout(3.0)


@dataclass(frozen=True)
class DeviceInfo:
    """Resolved compute device. ``kind`` is one of cuda/mps/cpu."""

    kind: str
    label: str


def _service_url() -> str:
    from app.config import settings

    return settings.deoldify_service_url.rstrip("/")


def detect_device() -> DeviceInfo:
    """Report the colorization service's compute device via its /health probe.

    Never raises. The container runs on CPU (no GPU passthrough), so this is
    effectively always CPU; if the service is unreachable we still return a
    valid CPU DeviceInfo rather than crashing the caller.
    """
    try:
        resp = httpx.get(f"{_service_url()}/health", timeout=_HEALTH_TIMEOUT)
        resp.raise_for_status()
        device = str(resp.json().get("device", "cpu")) or "cpu"
        kind = device if device in {"cuda", "mps", "cpu"} else "cpu"
        return DeviceInfo(kind=kind, label=device)
    except Exception as e:  # contract: never raise — always return a DeviceInfo
        logger.warning("DeOldify service /health probe failed: %s", e)
        return DeviceInfo(kind="cpu", label="cpu (service unavailable)")


def colorize_image_bytes(
    image_bytes: bytes,
    *,
    variant: str = "artistic",
    render_factor: int = 22,
) -> bytes:
    """Colorize a single B&W image via the service; return the result PNG bytes.

    POSTs the bytes to ``{deoldify_service_url}/colorize``. Raises RuntimeError
    on any transport error or non-200 response so the restoration service records
    a failed status with a human-readable message.
    """
    url = f"{_service_url()}/colorize"
    try:
        resp = httpx.post(
            url,
            files={"file": ("source.png", image_bytes, "image/png")},
            data={"variant": variant, "render_factor": str(render_factor)},
            timeout=_COLORIZE_TIMEOUT,
        )
    except httpx.RemoteProtocolError as e:
        # The service closed the connection without a response — the classic
        # signature of the colorizer being OOM-killed (SIGKILL 137) mid-render
        # at a high render_factor. Surface an actionable hint instead of the
        # raw "Server disconnected without sending a response".
        raise RuntimeError(
            "DeOldify service was interrupted mid-render — it likely ran out of "
            "memory. Try a lower render quality, or give the colorizer container "
            f"more RAM. (transport error: {e})"
        ) from e
    except httpx.HTTPError as e:
        raise RuntimeError(f"DeOldify service request failed: {e}") from e

    if resp.status_code != 200:
        detail = _error_detail(resp)
        raise RuntimeError(
            f"DeOldify service returned {resp.status_code}: {detail}"
        )
    return resp.content


def _error_detail(resp: httpx.Response) -> str:
    """Extract a human-readable detail from a non-200 service response."""
    try:
        body = resp.json()
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])
    except Exception:
        pass
    return (resp.text or "").strip()[:500] or "no response body"
