"""Time each step of search() on a few queries (models warmed up first). Reports median ms per step.

  python scripts/profile_search.py
"""
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qdrant_client import models  # noqa: E402

from app.retrieval import (DEFAULT_EMBEDDER, KB_COLLECTION, dense_name, embed_query, exact_id_hits,  # noqa: E402
                           get_client, plan_queries, rerank_hits, sparse_model, to_sparse)

QUERIES = [
    "Can we call the sunscreen waterproof?",
    "Có được gọi kem chống nắng là chống nước không?",
    "phi ship co dc hoan ko",
    "Khách hàng phàn nàn gì về kem chống nắng SPF 50?",
    "Which ad tests won for the toner?",
    "CP-05",
]


def timed(fn, *a, **kw):
    t = time.perf_counter()
    out = fn(*a, **kw)
    return out, (time.perf_counter() - t) * 1000


def run(query, candidates):
    t = {}
    plan, t["1. glossary + plan"] = timed(plan_queries, query)
    dense, t["2. embed query (e5-large)"] = timed(lambda: [embed_query(q) for q in plan["dense"]])
    sparse, t["3. embed query (BM25)"] = timed(lambda: [to_sparse(next(sparse_model().query_embed(q)))
                                                       for q in plan["bm25"]])
    prefetch = [models.Prefetch(query=d, using=dense_name(DEFAULT_EMBEDDER), limit=40) for d in dense]
    prefetch += [models.Prefetch(query=s, using="bm25", limit=40) for s in sparse]
    res, t["4. Qdrant query + RRF"] = timed(get_client().query_points, KB_COLLECTION, prefetch=prefetch,
                                            query=models.FusionQuery(fusion=models.Fusion.RRF),
                                            limit=candidates, with_payload=True)
    _, t["5. exact-ID lookup"] = timed(exact_id_hits, query, KB_COLLECTION)
    hits = [dict(p.payload) for p in res.points]
    _, t[f"6. rerank {candidates} candidates"] = timed(rerank_hits, query, hits)
    return t


def main():
    # warm-up: load all models once
    for c in (15, 30):
        run("warm up", c)
    for candidates in (15, 30):
        rows = [run(q, candidates) for q in QUERIES]
        print(f"\n=== rerank_candidates = {candidates} (median over {len(QUERIES)} queries, ms) ===")
        total_no_rr, total = 0, 0
        for step in rows[0]:
            med = statistics.median(r[step] for r in rows)
            total += med
            if not step.startswith("6."):
                total_no_rr += med
            print(f"  {step:32} {med:8.1f}")
        print(f"  {'total without rerank':32} {total_no_rr:8.1f}")
        print(f"  {'total with rerank':32} {total:8.1f}")
    get_client().close()


if __name__ == "__main__":
    main()
