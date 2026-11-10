# syntax=docker/dockerfile:1.7
# VidAsk API + worker image.
# TORCH_VARIANT=cpu (default, ~1 GB smaller) or cu124 for NVIDIA GPUs.
FROM python:3.11-slim AS base

ARG TORCH_VARIANT=cpu
ARG EXTRAS="--extra vision"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models/hf \
    UV_SYSTEM_PYTHON=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./

# Export the locked dependency set, then install it with the matching PyTorch wheel
# index so the CPU image does not pull multi-GB CUDA wheels.
RUN uv export --frozen --no-hashes --no-dev --no-emit-project ${EXTRAS} > /tmp/requirements.txt \
    && uv pip install -r /tmp/requirements.txt \
       --extra-index-url https://download.pytorch.org/whl/${TORCH_VARIANT} \
       --index-strategy unsafe-best-match

COPY app ./app
COPY scripts ./scripts
RUN uv pip install --no-deps .

RUN useradd -m -u 1000 vidask && mkdir -p /data /models && chown -R vidask /data /models
USER vidask

ENV DATA_DIR=/data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
