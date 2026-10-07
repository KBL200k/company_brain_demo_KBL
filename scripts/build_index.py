"""Load data/index/*.jsonl into Qdrant (two collections: kb, reviews).

Each point gets one dense vector per embedding model ("dense-<key>", cosine) plus a sparse BM25
vector ("bm25", IDF). Chunk `meta` fields are flattened into the payload so they can be filtered on.

Usage:
  python scripts/build_index.py                          # both collections, default model (EMBED_MODEL)
  python scripts/build_index.py --kb-only                # skip the 26k reviews
  python scripts/build_index.py --reviews-only
  python scripts/build_index.py --kb-only --models bge-small-en,minilm-multi,e5-large-multi   # model bake-off
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from qdrant_client import models  # noqa: E402

from app.retrieval import (DEFAULT_EMBEDDER, EMBEDDERS, KB_COLLECTION, REVIEWS_COLLECTION,  # noqa: E402
                           dense_name, embed_documents, get_client, point_id, sparse_model, to_sparse)

INDEX = ROOT / "data" / "index"
BATCH = 256

KEYWORD_FIELDS = {
    KB_COLLECTION: ["doc_id", "doc_type", "source_type", "product_ids", "rule_id", "severity", "test_id",
                    "product_line"],
    REVIEWS_COLLECTION: ["product_ids", "skin_type", "skin_tone"],
}
OTHER_FIELDS = {
    REVIEWS_COLLECTION: {"rating": models.PayloadSchemaType.INTEGER, "year": models.PayloadSchemaType.INTEGER,
                         "incentivized": models.PayloadSchemaType.BOOL},
}


def load(name):
    with open(INDEX / name, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def payload(chunk):
    p = {k: v for k, v in chunk.items() if k != "meta"}
    p.update(chunk.get("meta") or {})
    return p


def recreate(client, name, keys):
    if client.collection_exists(name):
        client.delete_collection(name)
    client.create_collection(
        name,
        vectors_config={dense_name(k): models.VectorParams(size=EMBEDDERS[k]["dim"], distance=models.Distance.COSINE)
                        for k in keys},
        sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
        # ~27k points fit comfortably in 2 segments; the default (one per CPU core) makes every
        # write touch many files, which is slow on Windows disks.
        optimizers_config=models.OptimizersConfigDiff(default_segment_number=2),
    )
    for field in KEYWORD_FIELDS.get(name, []):
        client.create_payload_index(name, field, models.PayloadSchemaType.KEYWORD)
    for field, schema in OTHER_FIELDS.get(name, {}).items():
        client.create_payload_index(name, field, schema)


def index(name, chunks, keys):
    client = get_client()
    recreate(client, name, keys)
    # Sort by length so each batch pads to a similar size (~3x faster on CPU than random order).
    chunks = sorted(chunks, key=lambda c: len(c["text"]))
    start = time.time()
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        texts = [c["text"] for c in batch]
        dense = {k: embed_documents(texts, k) for k in keys}
        sparse = list(sparse_model().embed(texts, batch_size=64))
        client.upsert(name, points=[
            models.PointStruct(
                id=point_id(c["chunk_id"]),
                vector={**{dense_name(k): dense[k][j] for k in keys}, "bm25": to_sparse(sparse[j])},
                payload=payload(c),
            )
            for j, c in enumerate(batch)
        ])
        done = i + len(batch)
        if done % (BATCH * 10) < BATCH or done == len(chunks):
            print(f"  {name}: {done}/{len(chunks)} ({time.time() - start:.0f}s)", flush=True)
    print(f"{name}: {client.count(name).count} points, vectors: {', '.join(dense_name(k) for k in keys)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb-only", action="store_true")
    ap.add_argument("--reviews-only", action="store_true")
    ap.add_argument("--models", default=DEFAULT_EMBEDDER, help="comma-separated keys from app.retrieval.EMBEDDERS")
    args = ap.parse_args()
    keys = args.models.split(",")
    unknown = [k for k in keys if k not in EMBEDDERS]
    if unknown:
        sys.exit(f"unknown model(s): {unknown}; choose from {list(EMBEDDERS)}")

    if not args.reviews_only:
        index(KB_COLLECTION, load("chunks.jsonl"), keys)
    if not args.kb_only:
        index(REVIEWS_COLLECTION, load("reviews_chunks.jsonl"), keys)
    get_client().close()


if __name__ == "__main__":
    main()
