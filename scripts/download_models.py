"""Download and load every model the search pipeline uses (~3.5 GB on first run), so the first question
in the UI is not slowed down by downloads. Models go to FASTEMBED_CACHE_PATH (see .env.example).

  python scripts/download_models.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.retrieval import DEFAULT_EMBEDDER, EMBEDDERS, RERANK_MODEL, SPARSE_MODEL, dense_model, reranker, sparse_model  # noqa: E402

for label, load in ((f"dense  {EMBEDDERS[DEFAULT_EMBEDDER]['model']}", dense_model),
                    (f"sparse {SPARSE_MODEL}", sparse_model),
                    (f"rerank {RERANK_MODEL}", reranker)):
    t = time.time()
    load()
    print(f"ok  {label}  ({time.time() - t:.0f}s)", flush=True)
