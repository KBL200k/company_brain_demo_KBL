"""Quick sanity check of hybrid retrieval: run sample queries and print the top hits.

  python scripts/search_demo.py                 # built-in sample queries
  python scripts/search_demo.py "your question"  # ad-hoc query on the kb collection
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.retrieval import KB_COLLECTION, REVIEWS_COLLECTION, build_filter, get_client, search  # noqa: E402

SAMPLES = [
    # (label, query, collection, filter kwargs, chunk we expect near the top)
    ("exact rule id", "CP-05", KB_COLLECTION, {}, "brand/claims-policy#cp-05"),
    ("compliance, natural wording", "can we call the sunscreen waterproof?", KB_COLLECTION, {},
     "brand/claims-policy#cp-05"),
    ("product facts", "which serum has salicylic acid", KB_COLLECTION, {}, "product/P482535"),
    ("customer insight", "what do customers complain about with the SPF 50", KB_COLLECTION,
     {"product_ids": "P481989"}, "research/insights-P481989"),
    ("SOP", "a customer says the toner burned her skin, what do I do", KB_COLLECTION, {},
     "sop/adverse-event-escalation"),
    ("creative learning", "which ad tests won for the toner", KB_COLLECTION, {}, "creative/learnings-2023#ct-08"),
    ("policy", "how many days do customers have to return a product", KB_COLLECTION, {}, "policy/returns"),
    ("review evidence", "pilling under makeup", REVIEWS_COLLECTION,
     {"product_ids": "P481989", "rating_lte": 2}, None),
    ("review evidence, no incentivized", "makes my skin glow", REVIEWS_COLLECTION,
     {"product_ids": "P466123", "incentivized": False}, None),
]


def show(label, query, collection, filt, expect, limit=5):
    hits = search(query, collection=collection, limit=limit, query_filter=build_filter(**filt))
    found = expect is None or any(h["chunk_id"].startswith(expect) for h in hits)
    mark = "" if expect is None else ("  OK" if found else f"  MISS (expected {expect})")
    print(f"\n### [{label}] {query!r} {filt or ''}{mark}")
    for h in hits:
        extra = f" {h.get('rating')}★ {h.get('skin_type')}" if collection == REVIEWS_COLLECTION else ""
        snippet = h["display_text"].replace("\n", " ")[:90]
        print(f"  {h['score']:.3f}  {h['chunk_id']:<48}{extra}  {snippet}")
    return found


def main():
    if len(sys.argv) > 1:
        show("ad-hoc", " ".join(sys.argv[1:]), KB_COLLECTION, {}, None, limit=8)
    else:
        results = [show(*s) for s in SAMPLES]
        checked = [r for r, s in zip(results, SAMPLES) if s[4]]
        print(f"\n{sum(checked)}/{len(checked)} queries returned the expected chunk in the top 5")
    get_client().close()


if __name__ == "__main__":
    main()
