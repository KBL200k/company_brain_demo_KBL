"""Turn the knowledge base into search-ready chunks.

Output (data/index/):
  chunks.jsonl          main index: products, research, brand, compliance, policies, SOPs, creative
  reviews_chunks.jsonl  review index: one chunk per review
  products.csv          structured table for exact questions (price, actives, ratings)
  banned_phrases.json   deterministic guard list derived from brand/claims-policy

Chunk schema:
  chunk_id      "<doc_id>#<section>"  - stable, used in citations
  doc_id, title, doc_type, source_type, product_ids, meta
  text          contextual header + content, used for embedding / BM25
  display_text  original content, used when quoting a source
"""
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "data" / "kb"
OUT = ROOT / "data" / "index"

MAX_TOKENS = 500
OVERLAP_TOKENS = 80   # only for sections split by split_long; whole sections need no overlap
PRODUCT_ID = re.compile(r"\bP\d{6}\b")


# ---------- helpers ----------

def n_tokens(text):
    return len(text) // 4  # rough estimate, good enough for size checks


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def split_frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            v = v.strip().strip('"')
            if v.startswith("[") and v.endswith("]"):
                v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
            meta[k.strip()] = v
    return meta, text[m.end():]


def strip_banner(body):
    """Drop the '> **SYNTHETIC DOCUMENT** ...' banner; source_type metadata carries that fact."""
    return re.sub(r"^> \*\*SYNTHETIC DOCUMENT\.?\*\*.*?\n\n", "", body.lstrip(), flags=re.S)


def split_sections(body, level=2):
    """Split markdown on headings of the given level. Returns (heading, content) pairs;
    text before the first heading gets heading None."""
    marker = "#" * level + " "
    sections, heading, buf = [], None, []
    for line in body.splitlines():
        if line.startswith(marker):
            sections.append((heading, "\n".join(buf).strip()))
            heading, buf = line[len(marker):].strip(), []
        else:
            buf.append(line)
    sections.append((heading, "\n".join(buf).strip()))
    return [(h, c) for h, c in sections if c or h]


def parse_table(lines):
    rows = [l for l in lines if l.strip().startswith("|")]
    if len(rows) < 3:
        return None, []
    cells = lambda l: [c.strip() for c in l.strip().strip("|").split("|")]
    return cells(rows[0]), [cells(r) for r in rows[2:]]


def tables_to_sentences(content):
    """Rewrite markdown tables as 'Header: value; ...' lines; embeddings handle prose better than pipes."""
    out, block = [], []

    def flush():
        header, rows = parse_table(block)
        if header:
            for r in rows:
                out.append("; ".join(f"{h}: {v}" for h, v in zip(header, r) if v and v != "-") + ".")
        else:
            out.extend(block)
        block.clear()

    for line in content.splitlines():
        if line.strip().startswith("|"):
            block.append(line)
        else:
            if block:
                flush()
            out.append(line)
    if block:
        flush()
    return "\n".join(out)


def make_chunk(meta, title, section, display, extra=None, text_body=None):
    header = f"{title} > {section}" if section else title
    body = text_body if text_body is not None else tables_to_sentences(display)
    pids = sorted(set(PRODUCT_ID.findall(display)) | set(meta.get("_product_ids", [])))
    return {
        "chunk_id": f"{meta['doc_id']}#{slug(section) if section else 'overview'}",
        "doc_id": meta["doc_id"],
        "title": header,
        "doc_type": meta.get("doc_type"),
        "source_type": meta.get("source_type"),
        "source": meta.get("source"),
        "product_ids": pids,
        "meta": extra or {},
        "text": f"{header}\n\n{body}".strip(),
        "display_text": display.strip(),
    }


def tail_overlap(prev_part):
    """Last ~OVERLAP_TOKENS of the previous part, cut on paragraph / line boundaries.
    For a table, the column header plus the last 2 rows, so the rows still read as a table."""
    paras = [p for p in re.split(r"\n\s*\n", prev_part.strip()) if p.strip()]
    if not paras:
        return ""
    last = paras[-1].splitlines()
    if last[0].startswith("|") and len(last) > 4:
        return "\n".join(last[:2] + last[-2:])
    # walk back across paragraphs (a heading often ends one part while its items start the next)
    lines = "\n\n".join(p for p in paras if not p.lstrip().startswith("|")).splitlines()
    taken = []
    for line in reversed(lines):
        if taken and n_tokens("\n".join([line] + taken)) > OVERLAP_TOKENS:
            break
        taken.insert(0, line)
    return "\n".join(taken)


def split_long(chunk):
    """Split an oversized chunk on paragraph boundaries, keeping lists and tables intact.
    Parts 2..n start with an overlap from the end of the previous part (embedded text only;
    display_text stays exactly the part, so citations don't repeat content)."""
    if n_tokens(chunk["text"]) <= MAX_TOKENS:
        return [chunk]
    paras, parts, cur = [], [], ""
    for p in re.split(r"\n\s*\n", chunk["display_text"]):
        lines = p.splitlines()
        if n_tokens(tables_to_sentences(p)) > MAX_TOKENS - 40 and len(lines) > 3 and lines[0].startswith("|"):
            # long table: split into row groups, repeating the header on each
            head, rows, size = lines[:2], lines[2:], 8
            paras += ["\n".join(head + rows[i:i + size]) for i in range(0, len(rows), size)]
        else:
            paras.append(p)
    for p in paras:
        # measure what gets embedded, leaving room for the header and the next part's overlap
        if cur and n_tokens(tables_to_sentences(cur + p)) > MAX_TOKENS - 40 - OVERLAP_TOKENS:
            parts.append(cur)
            cur = ""
        cur += p + "\n\n"
    parts.append(cur)
    out = []
    for i, part in enumerate(parts, 1):
        c = dict(chunk, display_text=part.strip(), chunk_id=f"{chunk['chunk_id']}-{i}",
                 meta=dict(chunk.get("meta") or {}, part=i, parts=len(parts)))
        body = tables_to_sentences(part)
        if i > 1:
            overlap = tail_overlap(parts[i - 2])
            if overlap:
                body = f"[...] {tables_to_sentences(overlap)}\n\n{body}"
                c["meta"].update(overlap_from=out[-1]["chunk_id"], overlap_tokens=n_tokens(overlap))
        c["text"] = f"{chunk['title']} (part {i}/{len(parts)})\n\n{body}".strip()
        out.append(c)
    return out


# ---------- per-type chunkers ----------

def chunk_generic(meta, body):
    """Brand, compliance, policies, SOPs, templates: one chunk per H2 section."""
    title = meta.get("title", meta["doc_id"])
    chunks = []
    for heading, content in split_sections(strip_banner(body)):
        content = re.sub(r"^# .*\n?", "", content).strip()  # drop the H1, it's in the title
        if not content:
            continue
        chunks.append(make_chunk(meta, title, heading, content))
    return chunks


def chunk_product(meta, body):
    """Two chunks: facts + highlights, and ingredients (long INCI lists dilute embeddings)."""
    title = meta["title"]
    meta["_product_ids"] = [meta["product_id"]]
    info, _, ingredients = body.partition("## Ingredients")
    info = re.sub(r"^# .*\n", "", info.strip()).strip()
    extra = {
        "product_line": meta.get("product_line"),
        "actives": meta.get("actives") or [],
        "otc_drug": meta.get("otc_drug") == "true",
        "price_usd": float(meta["price_usd"]),
        "full_size_product_id": meta.get("full_size_product_id"),
    }
    return [
        make_chunk(meta, title, None, info, extra),
        make_chunk(meta, title, "Ingredients", ingredients.strip(), extra),
    ]


def chunk_research(meta, body):
    meta["_product_ids"] = PRODUCT_ID.findall(meta.get("scope", ""))
    extra = {"scope": meta.get("scope")}
    return [dict(c, meta=extra) for c in chunk_generic(meta, body)]


def chunk_claims_policy(meta, body):
    """One chunk per rule, with rule_id / severity / applies_to for filtering."""
    chunks = []
    for c in chunk_generic(meta, body):
        m = re.search(r"\b(CP-\d{2})\b.*\((BLOCK|REVIEW|GUIDE)\)", c["title"])
        if m:
            c["chunk_id"] = f"{meta['doc_id']}#{m.group(1).lower()}"
            c["meta"] = {"rule_id": m.group(1), "severity": m.group(2), "applies_to": c["product_ids"] or ["all"]}
        chunks.append(c)
    return chunks


def chunk_creative_learnings(meta, body):
    """Test log table -> one chunk per test; other sections -> one chunk each."""
    title = meta["title"]
    chunks = []
    for heading, content in split_sections(strip_banner(body)):
        content = re.sub(r"^# .*\n?", "", content).strip()
        if heading == "Test log":
            header, rows = parse_table(content.splitlines())
            for r in rows:
                row = dict(zip(header, r))
                display = "\n".join(f"- **{h}:** {v}" for h, v in row.items())
                tid = row["Test ID"]
                c = make_chunk(meta, title, f"Test {tid}", display,
                               {"test_id": tid, "status": row.get("Status"), "result": row.get("Result")})
                c["chunk_id"] = f"{meta['doc_id']}#{tid.lower()}"
                chunks.append(c)
        elif content:
            chunks.append(make_chunk(meta, title, heading, content))
    return chunks


CHUNKERS = {
    "product": chunk_product,
    "customer_research": chunk_research,
    "brand_compliance": chunk_claims_policy,
    "creative_learnings": chunk_creative_learnings,
}


# ---------- reviews / products table / guard list ----------

def build_review_chunks():
    reviews = pd.read_json(KB / "reviews.jsonl", lines=True)
    out = []
    for r in reviews.itertuples():
        title = r.review_title if isinstance(r.review_title, str) else ""
        out.append({
            "chunk_id": r.review_id,
            "doc_id": r.review_id,
            "title": f"Review of {r.product_name} ({r.product_id}), {r.rating}★",
            "doc_type": "review",
            "source_type": "real",
            "product_ids": [r.product_id],
            "meta": {
                "rating": int(r.rating),
                "is_recommended": None if pd.isna(r.is_recommended) else bool(r.is_recommended),
                "skin_type": r.skin_type if isinstance(r.skin_type, str) else None,
                "skin_tone": r.skin_tone if isinstance(r.skin_tone, str) else None,
                "incentivized": bool(r.incentivized),
                "submission_time": r.submission_time.strftime("%Y-%m-%d"),
                "year": int(r.submission_time.year),
            },
            "text": f"{title}. {r.review_text}".strip(". ").strip(),
            "display_text": r.review_text,
        })
    return out, reviews


def build_products_table(reviews):
    rows = []
    for f in sorted((KB / "products").glob("*.md")):
        meta, body = split_frontmatter(f.read_text(encoding="utf-8"))
        grab = lambda pat: (m.group(1).strip() if (m := re.search(pat, body)) else None)
        rating = re.search(r"Sephora rating \(as listed on Sephora\):\*\* ([\d.]+) / 5 from (\d+)", body)
        owner = meta.get("full_size_product_id") or meta["product_id"]
        own = reviews[reviews.product_id == owner]
        rows.append({
            "product_id": meta["product_id"],
            "name": meta["title"],
            "product_line": meta["product_line"],
            "category": grab(r"\*\*Category:\*\* (.+)"),
            "price_usd": float(meta["price_usd"]),
            "size": grab(r"\*\*Size:\*\* (.+)"),
            "actives": "|".join(meta.get("actives") or []),
            "otc_drug": meta["otc_drug"] == "true",
            "full_size_product_id": meta.get("full_size_product_id"),
            "flags": grab(r"\*\*Flags:\*\* (.+)"),
            "highlights": "|".join(re.findall(r"^- (.+)$", body.split("## Highlights")[1].split("##")[0], re.M)),
            "sephora_rating": float(rating.group(1)) if rating else None,
            "sephora_review_count": int(rating.group(2)) if rating else None,
            "kb_review_count": len(own),
            "kb_avg_rating": round(own.rating.mean(), 2) if len(own) else None,
            "kb_recommend_pct": round(own.is_recommended.mean() * 100, 1) if len(own) else None,
            "kb_incentivized_pct": round(own.incentivized.mean() * 100, 1) if len(own) else None,
            "doc_id": meta["doc_id"],
        })
    return pd.DataFrame(rows)


# Curated from brand/claims-policy. Patterns are regexes matched case-insensitively against generated copy.
# applies_to: "all" or a list of product IDs.
BANNED = [
    ("CP-01", "BLOCK", "all", r"\b(cures?|treats?|treatment for|heals?)\b", "disease/treatment claim"),
    ("CP-01", "BLOCK", "all", r"\b(eczema|rosacea|psoriasis|dermatitis)\b", "names a medical condition"),
    ("CP-01", "BLOCK", "all", r"\brepairs? (your |the )?(skin )?barrier\b", "structure/function claim"),
    ("CP-01", "BLOCK", "all", r"\b(anti-inflammatory|regenerates? cells|boosts? collagen)\b", "drug-like claim"),
    ("CP-02", "BLOCK", ["P482535", "P504125", "P458219", "P467762"],
     r"\b(treats? acne|acne treatment|clears? (up )?(breakouts|acne)|gets? rid of pimples|prevents? breakouts)\b",
     "acne-treatment claim on BHA product"),
    ("CP-02", "BLOCK", ["P482535", "P504125", "P458219", "P467762"],
     r"\b(no breakouts|won'?t break you out)\b", "promises no breakouts"),
    ("CP-03", "BLOCK", "all", r"\b(fades? melasma|reduces? melanin|lightening|whitening|bleach\w*|removes? hyperpigmentation)\b",
     "pigment drug claim"),
    ("CP-05", "BLOCK", ["P481989"], r"\b(sunblock|waterproof|sweatproof)\b", "prohibited sunscreen term"),
    ("CP-05", "BLOCK", ["P481989"], r"\b(all[- ]day protection|no need to reapply)\b", "sunscreen duration claim"),
    ("CP-05", "BLOCK", ["P481989"], r"\b(no|zero) white cast\b|\binvisible on all skin tones\b", "absolute white-cast claim"),
    ("CP-05", "BLOCK", ["P481989"], r"\bwon'?t pill\b", "contradicted by reviews"),
    ("CP-05", "REVIEW", ["P481989"], r"\b(water[- ]resistant|broad[- ]spectrum)\b", "needs test result in claims register"),
    ("CP-06", "REVIEW", "all", r"\b(clinically (proven|tested|shown)|dermatologist[- ](tested|recommended|approved))\b",
     "needs study ID"),
    ("CP-06", "REVIEW", "all", r"\b\d{1,3}\s?% of (users|people|women|participants)\b|\bresults in \d+ days\b",
     "quantified efficacy claim"),
    ("CP-08", "BLOCK", ["P447791"], r"\b(erases? wrinkles|reverses? aging|botox in a jar|anti-aging treatment)\b",
     "retinol overclaim"),
    ("CP-09", "BLOCK", "all", r"\b(chemical[- ]free|non[- ]toxic|toxin[- ]free|100% natural|safe for everyone)\b",
     "misleading clean claim"),
    ("CP-12", "REVIEW", "all", r"(#1\b|\bnumber one\b|\bbest[- ]selling\b|\bthe best\b|\bbetter than\b|\bthe only\b)",
     "comparative/superlative claim"),
    ("VOICE", "GUIDE", "all", r"\b(flawless|perfect skin|flaws|problem skin|bad skin|miracle)\b", "off-voice word"),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    chunks = []
    for path in sorted(KB.rglob("*.md")):
        if path.name == "README.md":
            continue
        meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        chunker = CHUNKERS.get(meta.get("doc_type"), chunk_generic)
        for c in chunker(meta, body):
            chunks.extend(split_long(c))

    dupes = [k for k, n in Counter(c["chunk_id"] for c in chunks).items() if n > 1]
    assert not dupes, f"duplicate chunk ids: {dupes}"

    with open(OUT / "chunks.jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    review_chunks, reviews = build_review_chunks()
    with open(OUT / "reviews_chunks.jsonl", "w", encoding="utf-8") as f:
        for c in review_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    build_products_table(reviews).to_csv(OUT / "products.csv", index=False)

    banned = [{"rule_id": r, "severity": s, "applies_to": a, "pattern": p, "reason": why}
              for r, s, a, p, why in BANNED]
    (OUT / "banned_phrases.json").write_text(json.dumps(banned, indent=2), encoding="utf-8")

    # report
    df = pd.DataFrame({"type": [c["doc_type"] for c in chunks], "tok": [n_tokens(c["text"]) for c in chunks]})
    print(f"main index: {len(chunks)} chunks")
    print(df.groupby("type").tok.agg(["count", "median", "max"]).to_string())
    rt = pd.Series([n_tokens(c["text"]) for c in review_chunks])
    print(f"review index: {len(review_chunks)} chunks, tokens median {rt.median():.0f}, max {rt.max()}")
    print(f"products.csv: {len(reviews.product_id.unique())} products with reviews; banned patterns: {len(banned)}")


if __name__ == "__main__":
    main()
