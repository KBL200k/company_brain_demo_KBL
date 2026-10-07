"""Held-out validation of search. Not used for tuning: the dev set (retrieval_eval.jsonl) chose the
model and glossary; this set checks the result on questions written separately.

Three parts:
  A. kb       data/eval/val_kb.jsonl        53 questions x {en, vi, vi_noacc, vi_chat}
              hit@1, hit@5, MRR@10 overall, per variant and per category
  B. reviews  data/eval/val_reviews.jsonl   15 filtered queries x {en, vi, vi_noacc}
              precision@5 (a hit is relevant if the review text matches the item's regex label)
              and filter violations (hits that break the requested filter; must be 0)
  C. scope    data/eval/val_negative.jsonl  12 out-of-scope questions x {en, vi}
              top-1 dense cosine for in-scope (part A) vs out-of-scope questions, to see whether a
              similarity threshold can tell "nothing relevant in the KB" apart

  python scripts/eval_search_val.py
  python scripts/eval_search_val.py --rerank [--candidates 15]   # with cross-encoder rerank
Writes data/eval/results/val_<timestamp>.{md,json}.
"""
import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.glossary import strip_accents  # noqa: E402
from app.retrieval import (DEFAULT_EMBEDDER, KB_COLLECTION, REVIEWS_COLLECTION, build_filter,  # noqa: E402
                           dense_name, embed_query, get_client, search)

EVAL = ROOT / "data" / "eval"
RESULTS = EVAL / "results"
SEARCH_KW = {}  # extra search() arguments, set from the command line (rerank, rerank_candidates)


def load(name):
    return [json.loads(l) for l in (EVAL / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def check_labels(items):
    """Every expected prefix must match at least one real chunk, or a miss would be a typo, not a search error."""
    with open(ROOT / "data" / "index" / "chunks.jsonl", encoding="utf-8") as f:
        ids = [json.loads(l)["chunk_id"] for l in f]
    bad = [(q["id"], e) for q in items for e in q["expected"] if not any(i.startswith(e) for i in ids)]
    if bad:
        sys.exit(f"expected chunk(s) not found in index: {bad}")


def first_hit_rank(hits, expected):
    for i, h in enumerate(hits, 1):
        if any(h["chunk_id"].startswith(e) for e in expected):
            return i
    return None


def top_dense_cosine(query, collection=KB_COLLECTION):
    res = get_client().query_points(collection, query=embed_query(query), using=dense_name(DEFAULT_EMBEDDER),
                                    limit=1, with_payload=["chunk_id"])
    return res.points[0].score, res.points[0].payload["chunk_id"]


def violates(hit, flt):
    for key, val in flt.items():
        if key.endswith("_lte") and not hit[key[:-4]] <= val:
            return True
        if key.endswith("_gte") and not hit[key[:-4]] >= val:
            return True
        if key == "product_ids" and val not in hit["product_ids"]:
            return True
        if key not in ("product_ids",) and not key.endswith(("_lte", "_gte")) and hit.get(key) != val:
            return True
    return False


def part_a(items):
    variants = {"en": lambda q: q["en"], "vi": lambda q: q["vi"],
                "vi_noacc": lambda q: strip_accents(q["vi"]), "vi_chat": lambda q: q["vi_chat"]}
    runs, cosines, rerank_tops = [], [], []
    for q in items:
        for v, make in variants.items():
            text = make(q)
            hits = search(text, limit=10, **SEARCH_KW)
            r = first_hit_rank(hits, q["expected"])
            runs.append({"id": q["id"], "category": q["category"], "variant": v, "query": text, "rank": r,
                         "top3": [h["chunk_id"] for h in hits[:3]]})
            if v in ("en", "vi"):
                cosines.append(top_dense_cosine(text)[0])
                if "rerank_score" in hits[0]:
                    rerank_tops.append(hits[0]["rerank_score"])
        print(f"  A {q['id']} " + " ".join(f"{x['variant']}={x['rank']}" for x in runs[-4:]), flush=True)
    return runs, cosines, rerank_tops


def metrics(rows):
    n = len(rows)
    return {"n": n,
            "hit@1": sum(1 for r in rows if r["rank"] == 1) / n,
            "hit@5": sum(1 for r in rows if r["rank"] and r["rank"] <= 5) / n,
            "mrr": sum(1 / r["rank"] for r in rows if r["rank"]) / n}


def part_b(items):
    rows = []
    for q in items:
        pattern = re.compile(q["relevant"], re.I)
        flt = q["filter"]
        for v, text in (("en", q["en"]), ("vi", q["vi"]), ("vi_noacc", strip_accents(q["vi"]))):
            hits = search(text, collection=REVIEWS_COLLECTION, limit=5, query_filter=build_filter(**flt), **SEARCH_KW)
            rel = [bool(pattern.search(h["display_text"])) for h in hits]
            rows.append({"id": q["id"], "variant": v, "query": text, "n_hits": len(hits),
                         "precision@5": sum(rel) / 5, "violations": sum(violates(h, flt) for h in hits),
                         "irrelevant": [h["chunk_id"] for h, ok in zip(hits, rel) if not ok]})
        print(f"  B {q['id']} " + " ".join(f"{r['variant']}={r['precision@5']:.1f}" for r in rows[-3:]), flush=True)
    return rows


def separation(in_scope, out_scope):
    """Best single threshold: maximize accuracy of "score >= t means in scope"."""
    cands = sorted(set(in_scope + out_scope))
    best = max(cands, key=lambda t: sum(c >= t for c in in_scope) + sum(c < t for c in out_scope))
    acc = (sum(c >= best for c in in_scope) + sum(c < best for c in out_scope)) / (len(in_scope) + len(out_scope))
    return {"threshold": best, "accuracy": acc,
                  "in_scope_kept": sum(c >= best for c in in_scope) / len(in_scope),
                  "out_scope_rejected": sum(c < best for c in out_scope) / len(out_scope),
                  "in_scope": {"min": min(in_scope), "median": statistics.median(in_scope), "max": max(in_scope)},
                  "out_scope": {"min": min(out_scope), "median": statistics.median(out_scope), "max": max(out_scope)}}


def part_c(items, in_cos, in_rerank):
    rows = []
    for q in items:
        for v in ("en", "vi"):
            score, top = top_dense_cosine(q[v])
            row = {"id": q["id"], "variant": v, "query": q[v], "reason": q["reason"], "cosine": score, "top": top}
            if in_rerank:
                hit = search(q[v], limit=1, **SEARCH_KW)[0]
                row.update(rerank=hit["rerank_score"], rerank_top=hit["chunk_id"])
            rows.append(row)
    summary = separation(in_cos, [r["cosine"] for r in rows])
    summary_rr = separation(in_rerank, [r["rerank"] for r in rows]) if in_rerank else None
    return rows, summary, summary_rr


def fmt(m):
    return f"{m['hit@1']:.2f} / {m['hit@5']:.2f} / {m['mrr']:.2f}"


def main():
    kb_items, rv_items, neg_items = load("val_kb.jsonl"), load("val_reviews.jsonl"), load("val_negative.jsonl")
    ap = argparse.ArgumentParser()
    ap.add_argument("--rerank", action="store_true")
    ap.add_argument("--candidates", type=int, default=30)
    args = ap.parse_args()
    if args.rerank:
        SEARCH_KW.update(rerank=True, rerank_candidates=args.candidates)
    setup = ("hybrid (dense + BM25) + Vietnamese glossary + exact-ID lookup"
             + (f" + cross-encoder rerank of top {args.candidates}" if args.rerank else ""))

    check_labels(kb_items)
    print(f"model: {DEFAULT_EMBEDDER}; {setup}")
    a_rows, in_cos, in_rr = part_a(kb_items)
    b_rows = part_b(rv_items)
    c_rows, c_sum, c_sum_rr = part_c(neg_items, in_cos, in_rr)

    md = [f"# Search validation ({datetime.now():%Y-%m-%d %H:%M})", "",
          f"Embedding model: `{DEFAULT_EMBEDDER}`, {setup}.",
          "Held-out set: not used to choose the model or write the glossary.", "",
          "## A. Knowledge base: hit@1 / hit@5 / MRR", "",
          "| Variant | n | hit@1 / hit@5 / MRR |", "|---|---|---|"]
    by_v = defaultdict(list)
    for r in a_rows:
        by_v[r["variant"]].append(r)
    for v, rows in by_v.items():
        md.append(f"| {v} | {len(rows)} | {fmt(metrics(rows))} |")
    md.append(f"| **all** | {len(a_rows)} | **{fmt(metrics(a_rows))}** |")

    md += ["", "| Category | " + " | ".join(by_v) + " |", "|---|" + "---|" * len(by_v)]
    for cat in dict.fromkeys(r["category"] for r in a_rows):
        cells = [f"{metrics([r for r in by_v[v] if r['category'] == cat])['hit@5']:.2f}" for v in by_v]
        md.append(f"| {cat} | " + " | ".join(cells) + " |")

    misses = [r for r in a_rows if not r["rank"] or r["rank"] > 5]
    md += ["", f"### Misses (not in top 5): {len(misses)}", "", "| ID | Variant | Query | Top 3 |", "|---|---|---|---|"]
    md += [f"| {r['id']} | {r['variant']} | {r['query']} | {', '.join(r['top3'])} |" for r in misses]

    md += ["", "## B. Reviews: precision@5 with filters", "",
           "| Variant | mean precision@5 | filter violations | queries with < 5 hits |", "|---|---|---|---|"]
    for v in ("en", "vi", "vi_noacc"):
        rows = [r for r in b_rows if r["variant"] == v]
        md.append(f"| {v} | {statistics.mean(r['precision@5'] for r in rows):.2f} | "
                  f"{sum(r['violations'] for r in rows)} | {sum(r['n_hits'] < 5 for r in rows)} |")
    md += ["", "| ID | Query (vi) | en | vi | vi_noacc |", "|---|---|---|---|---|"]
    for q in rv_items:
        r = {x["variant"]: x for x in b_rows if x["id"] == q["id"]}
        md.append(f"| {q['id']} | {q['vi']} | {r['en']['precision@5']:.1f} | {r['vi']['precision@5']:.1f} | "
                  f"{r['vi_noacc']['precision@5']:.1f} |")

    md += ["", "## C. Out-of-scope detection (top-1 dense cosine)", "",
           "| | min | median | max |", "|---|---|---|---|",
           f"| in-scope (A, en+vi) | {c_sum['in_scope']['min']:.3f} | {c_sum['in_scope']['median']:.3f} | {c_sum['in_scope']['max']:.3f} |",
           f"| out-of-scope | {c_sum['out_scope']['min']:.3f} | {c_sum['out_scope']['median']:.3f} | {c_sum['out_scope']['max']:.3f} |",
           "",
           f"Best single threshold: **{c_sum['threshold']:.3f}**, accuracy {c_sum['accuracy']:.0%} "
           f"(keeps {c_sum['in_scope_kept']:.0%} of in-scope, rejects {c_sum['out_scope_rejected']:.0%} of out-of-scope).",
           "", "| ID | Variant | Reason | Query | cosine | top chunk |", "|---|---|---|---|---|---|"]
    md += [f"| {r['id']} | {r['variant']} | {r['reason']} | {r['query']} | {r['cosine']:.3f} | {r['top']} |"
           for r in sorted(c_rows, key=lambda r: -r["cosine"])]
    if c_sum_rr:
        md += ["", "## C2. Out-of-scope detection (top-1 rerank score, 0-1)", "",
               "| | min | median | max |", "|---|---|---|---|",
               f"| in-scope (A, en+vi) | {c_sum_rr['in_scope']['min']:.3f} | {c_sum_rr['in_scope']['median']:.3f} | {c_sum_rr['in_scope']['max']:.3f} |",
               f"| out-of-scope | {c_sum_rr['out_scope']['min']:.3f} | {c_sum_rr['out_scope']['median']:.3f} | {c_sum_rr['out_scope']['max']:.3f} |",
               "",
               f"Best single threshold: **{c_sum_rr['threshold']:.3f}**, accuracy {c_sum_rr['accuracy']:.0%} "
               f"(keeps {c_sum_rr['in_scope_kept']:.0%} of in-scope, rejects {c_sum_rr['out_scope_rejected']:.0%} of out-of-scope).",
               "", "| ID | Variant | Query | rerank | top chunk |", "|---|---|---|---|---|"]
        md += [f"| {r['id']} | {r['variant']} | {r['query']} | {r['rerank']:.3f} | {r['rerank_top']} |"
               for r in sorted(c_rows, key=lambda r: -r["rerank"])]

    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M") + ("-rerank" if args.rerank else "")
    (RESULTS / f"val_{stamp}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (RESULTS / f"val_{stamp}.json").write_text(json.dumps({"kb": a_rows, "reviews": b_rows, "scope": c_rows,
                                                           "scope_summary": c_sum, "scope_summary_rerank": c_sum_rr, "setup": setup}, indent=2, ensure_ascii=False),
                                               encoding="utf-8")
    print("\n".join(md[:40]))
    print(f"\nreport: data/eval/results/val_{stamp}.md")
    get_client().close()


if __name__ == "__main__":
    main()
