"""Tools over the knowledge base. Written once and used by three callers:
  - the RAG pipeline (app/rag.py) for route-specific retrieval,
  - Claude, as client tools during answer generation (TOOL_SPECS + run_tool),
  - the MCP server (mcp_server.py), for external clients such as Claude Desktop / Claude Code.
Every tool returns a JSON-serializable dict.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.glossary import expand, strip_accents
from app.retrieval import KB_COLLECTION, REVIEWS_COLLECTION, build_filter, search

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "index"

DOC_TYPES = ["product", "catalog", "customer_research", "brand", "brand_compliance", "regulation", "policy", "sop",
             "creative_learnings", "template"]


# ---------- data loaded once ----------

@lru_cache
def products_table():
    df = pd.read_csv(INDEX / "products.csv")
    df["actives"] = df["actives"].fillna("")
    df["category"] = df["category"].fillna("")
    return df


@lru_cache
def chunks_by_id():
    with open(INDEX / "chunks.jsonl", encoding="utf-8") as f:
        return {c["chunk_id"]: c for c in map(json.loads, f)}


@lru_cache
def banned_rules():
    return json.loads((INDEX / "banned_phrases.json").read_text(encoding="utf-8"))


# ---------- product name resolution ----------

# words that appear in many product names and do not identify a product on their own
_GENERIC = {"glow", "watermelon", "plum", "avocado", "strawberry", "guava", "blueberry", "papaya", "mini", "with",
            "and", "the", "acid", "hyaluronic", "niacinamide", "aha", "bha", "pha", "vitamin", "c", "oil", "free",
            "skin", "moisture", "barrier", "smooth"}


def _tokens(text):
    return set(re.findall(r"[a-z0-9]+", text))


def resolve_products(text):
    """Product IDs named or clearly described in free text (English or Vietnamese).
    Scores each product by the distinctive words of its name found in the text; the product line
    (fruit) must match when the text names one. Minis are returned only when "mini" is mentioned."""
    df = products_table()
    norm = strip_accents(text).lower()
    words = _tokens(norm + " " + expand(text).lower())
    lines_named = {l for l in df.product_line.unique() if l.lower() in words}
    wants_mini = "mini" in words
    scored = []
    for r in df.itertuples():
        name_words = _tokens(r.name.lower())
        distinctive = name_words - _GENERIC
        hits = distinctive & words
        if lines_named and r.product_line not in lines_named:
            continue
        is_mini = r.name.lower().startswith("mini ")
        if is_mini and not wants_mini:
            continue
        score = len(hits) + (0.5 if r.product_line in lines_named else 0)
        if hits:
            scored.append((score, r.product_id))
    if not scored:
        return []
    best = max(s for s, _ in scored)
    return [pid for s, pid in scored if s == best and best >= 1]


# ---------- tools ----------

def _hit(h, text_limit=1500):
    out = {k: h.get(k) for k in ("chunk_id", "doc_id", "title", "doc_type", "source_type", "source", "product_ids")}
    out["text"] = (h.get("display_text") or "")[:text_limit]
    if "rerank_score" in h:
        out["relevance"] = round(h["rerank_score"], 3)
    return out


def search_knowledge(query, doc_types=None, product_ids=None, limit=6, rerank=True, extra_queries=(),
                     rerank_candidates=15, **search_flags):
    """Hybrid search over the knowledge base (products, catalog, customer insights, brand, claims policy,
    regulations, policies, SOPs, creative learnings).
    search_flags: use_dense, use_bm25, use_glossary, prefetch_limit (see app.retrieval.search)."""
    doc_types = [d for d in (doc_types or []) if d in DOC_TYPES] or None
    flt = build_filter(doc_type=doc_types, product_ids=product_ids or None)
    kw = dict(collection=KB_COLLECTION, limit=limit, rerank=rerank, rerank_candidates=rerank_candidates,
              extra_queries=tuple(extra_queries), **search_flags)
    hits = search(query, query_filter=flt, **kw)
    if not hits and flt is not None:  # filters too narrow: retry unfiltered rather than return nothing
        hits = search(query, **kw)
    results = [_hit(h) for h in hits]
    return {"query": query, "count": len(results), "top_relevance": max((r.get("relevance", 0) for r in results), default=0),
            "results": results}


def search_reviews(query, product_id=None, rating_min=None, rating_max=None, skin_type=None,
                   exclude_incentivized=False, limit=5, **search_flags):
    """Search real customer reviews, optionally filtered. Returns verbatim review text with review_id."""
    flt = build_filter(product_ids=product_id, rating_gte=rating_min, rating_lte=rating_max, skin_type=skin_type,
                       incentivized=False if exclude_incentivized else None)
    hits = search(query, collection=REVIEWS_COLLECTION, limit=limit, query_filter=flt, **search_flags)
    return {"query": query, "count": len(hits), "results": [
        {"review_id": h["chunk_id"], "product_id": h["product_ids"][0], "rating": h.get("rating"),
         "skin_type": h.get("skin_type"), "incentivized": h.get("incentivized"), "date": h.get("submission_time"),
         "text": h["display_text"][:800]} for h in hits]}


def lookup_products(product_line=None, product_type=None, active=None, max_price=None, min_price=None,
                    name_contains=None, product_ids=None, include_minis=True):
    """Exact, structured lookup over the product catalog: filter by line, type, active ingredient, price.
    Use for counting, listing, prices, sizes and comparisons - never estimate these from search results."""
    df = products_table().copy()
    if product_ids:  # a product and its mini sizes
        df = df[df.product_id.isin(product_ids) | df.full_size_product_id.isin(product_ids)]
    if product_line:
        df = df[df.product_line.str.lower() == product_line.lower()]
    if product_type:
        df = df[df.category.str.lower().str.contains(product_type.lower(), regex=False)
                | df.name.str.lower().str.contains(product_type.lower(), regex=False)]
    if active:
        df = df[df.actives.str.contains(active.lower(), regex=False)]
    if max_price is not None:
        df = df[df.price_usd <= float(max_price)]
    if min_price is not None:
        df = df[df.price_usd >= float(min_price)]
    if name_contains:
        df = df[df.name.str.lower().str.contains(name_contains.lower(), regex=False)]
    if not include_minis:
        df = df[df.full_size_product_id.isna()]
    rows = []
    for r in df.sort_values(["product_line", "name"]).itertuples():
        rows.append({"product_id": r.product_id, "name": r.name, "line": r.product_line, "category": r.category,
                     "price_usd": r.price_usd, "size": r.size if isinstance(r.size, str) else None,
                     "actives": [a for a in r.actives.split("|") if a and a != "fragrance"],
                     "contains_fragrance": "fragrance" in r.actives, "otc_drug": bool(r.otc_drug),
                     "mini_of": r.full_size_product_id if isinstance(r.full_size_product_id, str) else None,
                     "sephora_rating": r.sephora_rating, "reviews_in_kb": int(r.kb_review_count),
                     "avg_rating_in_kb": r.kb_avg_rating if r.kb_review_count else None,
                     "source": f"product/{r.product_id}"})
    distinct = sum(1 for r in rows if not r["mini_of"])
    return {"count_listings": len(rows), "count_distinct_products": distinct,
            "count_minis": len(rows) - distinct, "products": rows,
            "note": "Catalog covers the 7 fruit lines only; lip balm and kits are not in the knowledge base."}


def get_document(doc_or_chunk_id):
    """Full text of one chunk (e.g. brand/claims-policy#cp-05) or of a whole document (e.g. brand/claims-policy)."""
    chunks = chunks_by_id()
    if doc_or_chunk_id in chunks:
        c = chunks[doc_or_chunk_id]
        return {"id": doc_or_chunk_id, "title": c["title"], "source_type": c["source_type"], "text": c["display_text"]}
    parts = [c for c in chunks.values() if c["doc_id"] == doc_or_chunk_id]
    if not parts:
        return {"error": f"no document or chunk with id {doc_or_chunk_id!r}"}
    text = "\n\n".join(f"### {c['title']}\n{c['display_text']}" for c in parts)
    return {"id": doc_or_chunk_id, "source_type": parts[0]["source_type"], "chunks": [c["chunk_id"] for c in parts],
            "text": text[:12000]}


def check_claims(text, product_ids=None):
    """Check marketing copy against the claims policy (banned / review-required phrases).
    Deterministic regex check; returns each violation with its rule ID and severity."""
    product_ids = set(product_ids or [])
    found = []
    for rule in banned_rules():
        applies = rule["applies_to"] == "all" or not product_ids or product_ids & set(rule["applies_to"])
        if not applies:
            continue
        for m in re.finditer(rule["pattern"], text, re.I):
            found.append({"rule_id": rule["rule_id"], "severity": rule["severity"], "matched": m.group(0),
                          "reason": rule["reason"], "policy": f"brand/claims-policy#{rule['rule_id'].lower()}"
                          if rule["rule_id"].startswith("CP") else "brand/voice-guide#vocabulary"})
    blocking = [f for f in found if f["severity"] == "BLOCK"]
    return {"ok": not blocking, "blocking": len(blocking), "needs_review": sum(f["severity"] == "REVIEW" for f in found),
            "violations": found}


# ---------- tool definitions (provider-neutral; app/llm.py adapts them per vendor) ----------

TOOL_SPECS = [
    {
        "name": "search_knowledge",
        "description": "Search the company knowledge base (products, catalog, customer-insight reports, brand and "
                       "voice guide, marketing claims policy, FDA/FTC regulations, return/shipping policies, SOPs, "
                       "creative test learnings). Returns passages with chunk_id to cite.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "What to look for, in English for best results."},
            "doc_types": {"type": "array", "items": {"type": "string", "enum": DOC_TYPES},
                          "description": "Optional: restrict to these document types."},
            "product_ids": {"type": "array", "items": {"type": "string"}, "description": "Optional, e.g. P481989."},
        }, "required": ["query"]},
    },
    {
        "name": "search_reviews",
        "description": "Search real Sephora customer reviews (2018-2023) for evidence and verbatim quotes. "
                       "Filter by product, rating range, skin type; exclude reviews from free-product programs.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"},
            "product_id": {"type": "string"},
            "rating_min": {"type": "integer", "minimum": 1, "maximum": 5},
            "rating_max": {"type": "integer", "minimum": 1, "maximum": 5},
            "skin_type": {"type": "string", "enum": ["dry", "oily", "combination", "normal"]},
            "exclude_incentivized": {"type": "boolean"},
        }, "required": ["query"]},
    },
    {
        "name": "lookup_products",
        "description": "Exact structured lookup in the product catalog. Use for counts, lists, prices, sizes, "
                       "minis, product types and active ingredients instead of estimating from passages.",
        "parameters": {"type": "object", "properties": {
            "product_line": {"type": "string", "enum": ["Watermelon", "Plum", "Avocado", "Strawberry", "Guava",
                                                        "Blueberry", "Papaya"]},
            "product_type": {"type": "string", "description": "e.g. serum, cleanser, moisturizer, sunscreen, eye"},
            "active": {"type": "string", "enum": ["aha", "bha", "retinoid", "sunscreen_filter", "fragrance"]},
            "max_price": {"type": "number"},
            "min_price": {"type": "number"},
            "name_contains": {"type": "string"},
            "include_minis": {"type": "boolean"},
        }},
    },
    {
        "name": "get_document",
        "description": "Read the full text of a chunk (id with '#') or a whole document (doc_id) found earlier.",
        "parameters": {"type": "object", "properties": {"doc_or_chunk_id": {"type": "string"}},
                         "required": ["doc_or_chunk_id"]},
    },
    {
        "name": "check_claims",
        "description": "Check draft marketing copy against the claims policy before showing it. Returns violations "
                       "with rule IDs (BLOCK must be rewritten, REVIEW needs regulatory sign-off).",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"},
            "product_ids": {"type": "array", "items": {"type": "string"}},
        }, "required": ["text"]},
    },
]

TOOLS = {"search_knowledge": search_knowledge, "search_reviews": search_reviews, "lookup_products": lookup_products,
         "get_document": get_document, "check_claims": check_claims}


def run_tool(name, args):
    """Execute a tool call from Claude. Errors are returned (not raised) so they can go back as is_error results."""
    if name not in TOOLS:
        return {"error": f"unknown tool {name}"}, True
    try:
        return TOOLS[name](**args), False
    except Exception as e:  # noqa: BLE001 - report any tool failure back to the model
        return {"error": f"{type(e).__name__}: {e}"}, True
