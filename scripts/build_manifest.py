"""Validate cross-links in the knowledge base and write data/kb/manifest.json.

Checks:
  - every doc has doc_id / doc_type / source_type, and doc_ids are unique
  - every doc_id referenced (in `related` or in the body) exists
  - every review_id referenced exists, and quoted review text matches the review verbatim
Exit code 1 if anything is broken.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "data" / "kb"

DOC_REF = re.compile(r"\b((?:product|research|brand|compliance|policy|sop|creative)/[A-Za-z0-9-]+)")
REVIEW_REF = re.compile(r"review/P\d+-\d{5}")
QUOTE_WITH_ID = re.compile(r"[\"']([^\"'\n]{20,}?)(?:\.\.\.)?[\"'][^\n\[\(]{0,40}?[\[\(](review/P\d+-\d{5})[\]\)]")


def parse_frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    meta = {}
    if not m:
        return meta
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            v = v.strip().strip('"')
            if v.startswith("[") and v.endswith("]"):
                v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
            meta[k.strip()] = v
    return meta


def main():
    reviews = {}
    with open(KB / "reviews.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            reviews[r["review_id"]] = r

    docs = []
    for path in sorted(KB.rglob("*.md")):
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        meta = parse_frontmatter(text)
        docs.append({"path": path, "text": text, "meta": meta})

    errors = []
    ids = Counter(d["meta"].get("doc_id") for d in docs)
    for doc_id, n in ids.items():
        if n > 1:
            errors.append(f"duplicate doc_id {doc_id}")
    known = set(ids)

    for d in docs:
        rel = d["path"].relative_to(KB).as_posix()
        meta = d["meta"]
        for key in ("doc_id", "doc_type", "source_type"):
            if not meta.get(key):
                errors.append(f"{rel}: missing {key}")
        refs = set(meta.get("related") or []) | set(DOC_REF.findall(d["text"]))
        refs.discard(meta.get("doc_id"))
        for ref in sorted(refs):
            if ref.endswith("-"):  # wildcard mention such as "research/insights-*"
                continue
            if ref not in known:
                errors.append(f"{rel}: broken link -> {ref}")
        for rid in set(REVIEW_REF.findall(d["text"])):
            if rid not in reviews:
                errors.append(f"{rel}: unknown review id {rid}")
        for quote, rid in QUOTE_WITH_ID.findall(d["text"]):
            if rid in reviews:
                body = re.sub(r"\s+", " ", reviews[rid]["review_text"])
                if quote.strip() not in body:
                    errors.append(f"{rel}: quote does not match {rid}: \"{quote[:60]}\"")

    manifest = [{
        "doc_id": d["meta"].get("doc_id"),
        "path": d["path"].relative_to(KB).as_posix(),
        "doc_type": d["meta"].get("doc_type"),
        "source_type": d["meta"].get("source_type"),
        "title": d["meta"].get("title"),
        "source": d["meta"].get("source"),
        "related": d["meta"].get("related") or [],
    } for d in docs]
    manifest.append({
        "doc_id": "reviews", "path": "reviews.jsonl", "doc_type": "review_collection", "source_type": "real",
        "title": f"{len(reviews)} Sephora customer reviews (one per line, id = review_id)",
        "source": "https://www.kaggle.com/datasets/nadyinky/sephora-products-and-skincare-reviews", "related": [],
    })
    (KB / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    counts = Counter((m["source_type"], m["doc_type"]) for m in manifest)
    print(f"{len(manifest)} entries in manifest")
    for (st, dt), n in sorted(counts.items()):
        print(f"  {st:9} {dt:20} {n}")
    if errors:
        print(f"\n{len(errors)} problem(s):")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print("All links, review ids and quotes verified.")


if __name__ == "__main__":
    main()
