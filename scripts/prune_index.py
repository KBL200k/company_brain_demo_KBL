"""Delete points from Qdrant that are no longer in data/index/*.jsonl (no re-embedding).

Use after narrowing the data (e.g. EXCLUDED_LINES in prepare_data.py): review_ids are stable,
so removing the dropped ones is enough.

  python scripts/prune_index.py            # dry run: show what would be deleted
  python scripts/prune_index.py --apply
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from qdrant_client import models  # noqa: E402

from app.retrieval import KB_COLLECTION, REVIEWS_COLLECTION, get_client, point_id  # noqa: E402

FILES = {KB_COLLECTION: "chunks.jsonl", REVIEWS_COLLECTION: "reviews_chunks.jsonl"}


def main():
    apply = "--apply" in sys.argv
    client = get_client()
    for collection, fname in FILES.items():
        with open(ROOT / "data" / "index" / fname, encoding="utf-8") as f:
            wanted = {point_id(json.loads(line)["chunk_id"]) for line in f}
        stale, offset = [], None
        while True:
            points, offset = client.scroll(collection, limit=2000, offset=offset,
                                           with_payload=["chunk_id", "product_ids"], with_vectors=False)
            stale += [p for p in points if p.id not in wanted]
            if offset is None:
                break
        by_product = Counter(pid for p in stale for pid in p.payload.get("product_ids") or ["-"])
        print(f"{collection}: {client.count(collection).count} points, {len(stale)} stale, "
              f"{len(wanted)} expected. Stale by product: {dict(by_product)}")
        if apply and stale:
            ids = [p.id for p in stale]
            for i in range(0, len(ids), 1000):
                client.delete(collection, points_selector=models.PointIdsList(points=ids[i:i + 1000]))
            print(f"  deleted {len(ids)} -> {client.count(collection).count} points")
    client.close()


if __name__ == "__main__":
    main()
