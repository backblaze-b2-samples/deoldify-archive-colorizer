# DeOldify colorization microservice — native linux/arm64 ONLY.
#
# The legacy DeOldify stack (fastai-v1 / torch-1.11 / Pillow<10) cannot coexist
# with the modern API's fastai-2 / torch-2 / Python-3.11 environment, so it lives
# here in its own container. Build/run with --platform=linux/arm64 (torch's amd64
# wheels use AVX and SIGILL under QEMU on Apple silicon).
FROM --platform=linux/arm64 python:3.9-slim

WORKDIR /app

# Native libs the stack needs on slim Debian:
#   git            -> clone DeOldify
#   ffmpeg         -> ffmpeg-python (harmless for the image-only path)
#   libgomp1       -> torch/opencv OpenMP runtime
#   curl/ca-certs  -> download model weights at build time
# NOTE: opencv-python-HEADLESS needs neither libGL nor glib, so libgl1 /
# libglib2.0-0 are intentionally omitted (smaller image).
RUN apt-get update && apt-get install -y --no-install-recommends \
      git ffmpeg libgomp1 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ---- Pin the numeric base BEFORE anything can pull numpy 2.x ----
RUN pip install --no-cache-dir "numpy==1.23.5" "Pillow==9.5.0"

# ---- torch + torchvision (CPU) ----
# cp39 matches torch-1.11.0-cp39-cp39-manylinux2014_aarch64.whl on the CPU index.
RUN pip install --no-cache-dir torch==1.11.0 torchvision==0.12.0 \
      --extra-index-url https://download.pytorch.org/whl/cpu

# ---- fastai 1.0.60 WITHOUT its deps ----
# fastai v1 hard-pins spacy<2.1, whose compiled deps (thinc/blis/murmurhash)
# have no aarch64/cp39 wheels. DeOldify's IMAGE colorizer is vision-only and
# never imports fastai.text/spacy, so we install --no-deps and hand-pick the
# vision-path deps in requirements.txt. Never let fastai pull the `typing`
# backport on py3.9 -> it breaks stdlib typing.
RUN pip install --no-cache-dir fastai==1.0.60 --no-deps

# ---- DeOldify itself: clone, do NOT `pip install .` (its setup.py feeds an
# --extra-index-url line into install_requires and breaks). Use PYTHONPATH. ----
RUN git clone --depth 1 https://github.com/jantic/DeOldify /opt/DeOldify
ENV PYTHONPATH=/opt/DeOldify
WORKDIR /opt/DeOldify

# ---- Pre-bake model weights (no network at request time) ----
# Placed BEFORE the requirements/pip + server layers so that editing those cheap
# layers never forces a ~1 GB weights re-download. Artistic (243 MB) from the
# spike-proven BunnyCDN mirror; Stable (833 MB, larger resnet101 backbone) from a
# HuggingFace mirror. Both are overridable build-args.
ARG ARTISTIC_WEIGHTS_URL=https://data.deepai.org/deoldify/ColorizeArtistic_gen.pth
ARG STABLE_WEIGHTS_URL=https://huggingface.co/spensercai/DeOldify/resolve/main/ColorizeStable_gen.pth
RUN mkdir -p /opt/DeOldify/models \
    && curl -fL --retry 3 -o /opt/DeOldify/models/ColorizeArtistic_gen.pth "$ARTISTIC_WEIGHTS_URL" \
    && curl -fL --retry 3 -o /opt/DeOldify/models/ColorizeStable_gen.pth  "$STABLE_WEIGHTS_URL"

# ---- Everything else, constrained so numpy stays < 2 ----
COPY constraints.txt /tmp/constraints.txt
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -c /tmp/constraints.txt -r /tmp/requirements.txt

# ---- Build both colorizers once: validates the weights load AND caches the
# resnet backbones (resnet34 / resnet101) into /root/.cache/torch/hub. ----
RUN python -c "import warnings; warnings.filterwarnings('ignore'); \
from deoldify import device; from deoldify.device_id import DeviceId; device.set(device=DeviceId.CPU); \
from deoldify.visualize import get_image_colorizer, get_stable_image_colorizer; \
from pathlib import Path; r=Path('/opt/DeOldify'); \
get_image_colorizer(root_folder=r, artistic=True); \
get_stable_image_colorizer(root_folder=r); \
print('PREBAKE_OK')"

# server.py copied LAST so editing it doesn't invalidate the heavy layers above.
COPY server.py /opt/DeOldify/server.py

EXPOSE 8137
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8137"]
