"""Download only the files a model needs (skips ONNX/OpenVINO/TF duplicates).

Usage: uv run python scripts/download_models.py [repo_id ...]
Defaults to the configured embedding + reranker models.
"""

from __future__ import annotations

import sys

from huggingface_hub import snapshot_download

from app.core.config import get_settings

PATTERNS = [
    "*.json",
    "*.txt",
    "*.model",
    "model.safetensors",
    "sentencepiece.bpe.model",
    "1_Pooling/*",
]


def main() -> None:
    s = get_settings()
    repos = sys.argv[1:] or [s.embedding_model, s.reranker_model]
    for repo in repos:
        print(f"↓ {repo}", flush=True)
        path = snapshot_download(repo, allow_patterns=PATTERNS)
        print(f"  ✓ {path}", flush=True)


if __name__ == "__main__":
    main()
