"""Bilingual retrieval eval: does a Vietnamese question find the same chunks as the English one?

For every question in data/eval/retrieval_eval.jsonl, runs three variants
  en         English question
  vi         Vietnamese question
  vi_noacc   Vietnamese with accents stripped ("co duoc goi kem chong nang ...")
against each embedding model and search configuration, and reports
  hit@5  share of questions with at least one expected chunk in the top 5
  MRR    mean reciprocal rank of the first expected chunk (top 10)

  python scripts/eval_retrieval.py                                  # all models indexed in kb
  python scripts/eval_retrieval.py --models e5-large-multi --configs hybrid+glossary
Writes data/eval/results/retrieval_<timestamp>.{md,json}.
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.glossary import strip_accents  # noqa: E402
from app.retrieval import KB_COLLECTION, get_client, search  # noqa: E402

EVAL = ROOT / "data" / "eval" / "retrieval_eval.jsonl"
RESULTS = ROOT / "data" / "eval" / "results"

CONFIGS = {
    "dense": dict(use_bm25=False, use_glossary=False),
    "hybrid": dict(use_glossary=False),
    "hybrid+glossary": dict(),
    "hybrid+glossary+rerank": dict(rerank=True),
    "hybrid+glossary+rerank15": dict(rerank=True, rerank_candidates=15),
}
VARIANTS = {
    "en": lambda q: q["en"],
    "vi": lambda q: q["vi"],
    "vi_noacc": lambda q: strip_accents(q["vi"]),
}


def rank_of_first_hit(hits, expected):
    for i, h in enumerate(hits, 1):
        if any(h["chunk_id"].startswith(e) for e in expected):
            return i
    return None


def indexed_models():
    vectors = get_client().get_collection(KB_COLLECTION).config.params.vectors
    return [name.removeprefix("dense-") for name in vectors]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", help="comma-separated; default = every model indexed in kb")
    ap.add_argument("--configs", default=",".join(CONFIGS))
    args = ap.parse_args()

    questions = [json.loads(l) for l in EVAL.read_text(encoding="utf-8").splitlines() if l.strip()]
    models_ = args.models.split(",") if args.models else indexed_models()
    configs = args.configs.split(",")

    rows, misses = [], []
    for model in models_:
        for cfg in configs:
            for variant, make in VARIANTS.items():
                ranks, start = [], time.time()
                for q in questions:
                    hits = search(make(q), limit=10, embedder=model, **CONFIGS[cfg])
                    r = rank_of_first_hit(hits, q["expected"])
                    ranks.append(r)
                    if (r is None or r > 5) and cfg == configs[-1]:
                        misses.append({"model": model, "config": cfg, "variant": variant, "id": q["id"],
                                       "query": make(q), "got": [h["chunk_id"] for h in hits[:3]]})
                hit5 = sum(1 for r in ranks if r and r <= 5) / len(ranks)
                mrr = sum(1 / r for r in ranks if r) / len(ranks)
                ms = (time.time() - start) / len(ranks) * 1000
                rows.append({"model": model, "config": cfg, "variant": variant, "hit@5": hit5, "mrr": mrr, "ms": ms})
                print(f"{model:15} {cfg:16} {variant:9} hit@5 {hit5:.2f}  MRR {mrr:.2f}  {ms:.0f} ms/q", flush=True)

    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    (RESULTS / f"retrieval_{stamp}.json").write_text(json.dumps({"rows": rows, "misses": misses}, indent=2,
                                                                ensure_ascii=False), encoding="utf-8")
    md = [f"# Retrieval eval {stamp}", "", f"{len(questions)} questions x 3 variants. hit@5 (MRR).", "",
          "| Model | Config | en | vi | vi_noacc | vi / en |", "|---|---|---|---|---|---|"]
    for model in models_:
        for cfg in configs:
            r = {x["variant"]: x for x in rows if x["model"] == model and x["config"] == cfg}
            ratio = r["vi"]["hit@5"] / r["en"]["hit@5"] if r["en"]["hit@5"] else 0
            md.append(f"| {model} | {cfg} | " + " | ".join(f"{r[v]['hit@5']:.2f} ({r[v]['mrr']:.2f})"
                                                          for v in VARIANTS) + f" | {ratio:.0%} |")
    md += ["", f"## Misses ({configs[-1]})", "", "| Model | Variant | ID | Query | Top 3 |", "|---|---|---|---|---|"]
    md += [f"| {m['model']} | {m['variant']} | {m['id']} | {m['query']} | {', '.join(m['got'])} |" for m in misses]
    (RESULTS / f"retrieval_{stamp}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nreport: data/eval/results/retrieval_{stamp}.md")
    get_client().close()


if __name__ == "__main__":
    main()
