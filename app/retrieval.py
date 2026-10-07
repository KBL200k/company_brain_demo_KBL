"""Hybrid, cross-lingual retrieval over Qdrant.

Per query, several searches run in one Qdrant call and are fused with RRF:
  - dense  : multilingual embedding of the original query (works for Vietnamese or English)
  - bm25   : keyword match on the original query (exact terms, product names, IDs)
  - bm25   : keyword match on English terms from the Vietnamese glossary (app/glossary.py)
  - extra  : optional rewritten queries (e.g. an LLM's English rewrite), dense + bm25 each
Exact rule / test IDs (CP-05, CT-03) are looked up by payload filter and put first.

Optional rerank (rerank=True): the fused top `rerank_candidates` are re-scored by a multilingual
cross-encoder that reads query and chunk together, then re-sorted. Each hit gets `rerank_score`
(sigmoid of the cross-encoder logit, 0-1), which unlike the RRF score is comparable across queries.

Each embedding model is stored as its own named vector ("dense-<key>"), so models can be compared
on the same collection and switched with EMBED_MODEL.

Connects to a Qdrant server at QDRANT_URL (default http://127.0.0.1:6333, started with
qdrant_server/start_qdrant.bat; dashboard at /dashboard). Set QDRANT_URL=local to use embedded
local mode instead (data in data/qdrant/, no server, no dashboard, single process only).
"""
import os
import re
import uuid
from functools import lru_cache
from pathlib import Path

import math

from dotenv import load_dotenv
from fastembed import SparseTextEmbedding, TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder
from qdrant_client import QdrantClient, models

from app.glossary import expand, is_vietnamese

ROOT = Path(__file__).resolve().parent.parent
QDRANT_PATH = ROOT / "data" / "qdrant"

load_dotenv(ROOT / ".env")
# fastembed reads FASTEMBED_CACHE_PATH when a model is created; resolve a relative path against the project
# so models live in e.g. ./models_cache instead of the OS temp dir (which Windows may clean up).
if os.getenv("FASTEMBED_CACHE_PATH") and not os.path.isabs(os.environ["FASTEMBED_CACHE_PATH"]):
    os.environ["FASTEMBED_CACHE_PATH"] = str((ROOT / os.environ["FASTEMBED_CACHE_PATH"]).resolve())

EMBEDDERS = {
    # key: model, dim, prefixes the model was trained with
    "bge-small-en": {"model": "BAAI/bge-small-en-v1.5", "dim": 384,
                     "query_prefix": "Represent this sentence for searching relevant passages: ", "doc_prefix": ""},
    "minilm-multi": {"model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "dim": 384,
                     "query_prefix": "", "doc_prefix": ""},
    "mpnet-multi": {"model": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2", "dim": 768,
                    "query_prefix": "", "doc_prefix": ""},
    "e5-large-multi": {"model": "intfloat/multilingual-e5-large", "dim": 1024,
                       "query_prefix": "query: ", "doc_prefix": "passage: "},
}
DEFAULT_EMBEDDER = os.getenv("EMBED_MODEL", "e5-large-multi")
SPARSE_MODEL = "Qdrant/bm25"
RERANK_MODEL = "jinaai/jina-reranker-v2-base-multilingual"

KB_COLLECTION = "kb"
REVIEWS_COLLECTION = "reviews"


@lru_cache
def get_client():
    url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
    if url == "local":
        return QdrantClient(path=str(QDRANT_PATH))
    return QdrantClient(url=url, api_key=os.getenv("QDRANT_API_KEY"), timeout=60)


@lru_cache
def dense_model(key=DEFAULT_EMBEDDER):
    return TextEmbedding(EMBEDDERS[key]["model"])


@lru_cache
def sparse_model():
    return SparseTextEmbedding(SPARSE_MODEL)


@lru_cache
def reranker():
    return TextCrossEncoder(RERANK_MODEL)


def rerank_hits(query, hits, glossary_hint=True):
    """Re-score hits with the cross-encoder and sort by it. For Vietnamese queries the glossary's
    English terms are appended, which helps with accent-less or abbreviated input."""
    if not hits:
        return hits
    q = query
    if glossary_hint and is_vietnamese(query):
        terms = expand(query)
        if terms:
            q = f"{query} ({terms})"
    logits = list(reranker().rerank(q, [h["text"] for h in hits], batch_size=16))
    for h, logit in zip(hits, logits):
        h["rerank_score"] = 1 / (1 + math.exp(-logit))
    return sorted(hits, key=lambda h: -h["rerank_score"])


def dense_name(key):
    return f"dense-{key}"


def embed_documents(texts, key=DEFAULT_EMBEDDER, batch_size=32):
    prefix = EMBEDDERS[key]["doc_prefix"]
    return [v.tolist() for v in dense_model(key).embed([prefix + t for t in texts], batch_size=batch_size)]


def embed_query(text, key=DEFAULT_EMBEDDER):
    return next(dense_model(key).embed([EMBEDDERS[key]["query_prefix"] + text])).tolist()


def point_id(chunk_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def to_sparse(emb):
    return models.SparseVector(indices=emb.indices.tolist(), values=emb.values.tolist())


def build_filter(**conditions):
    """build_filter(product_ids="P481989", rating_lte=2, doc_type=["sop", "policy"])

    - list value  -> match any
    - *_lte/_gte  -> range
    - None values are ignored
    """
    must = []
    for key, value in conditions.items():
        if value is None:
            continue
        if key.endswith(("_lte", "_gte")):
            field, op = key[:-4], key[-3:]
            must.append(models.FieldCondition(key=field, range=models.Range(**{op: value})))
        elif isinstance(value, (list, tuple, set)):
            must.append(models.FieldCondition(key=key, match=models.MatchAny(any=list(value))))
        else:
            must.append(models.FieldCondition(key=key, match=models.MatchValue(value=value)))
    return models.Filter(must=must) if must else None


ID_FIELDS = {"rule_id": re.compile(r"\bCP-\d{2}\b", re.I), "test_id": re.compile(r"\bCT-\d{2}\b", re.I)}


def exact_id_hits(query, collection):
    """Chunks whose rule_id / test_id is named in the query. BM25 splits "CP-05" into "cp" + "05",
    and many docs mention CP-05 in passing, so the rule itself can rank low; an exact lookup fixes that."""
    if collection != KB_COLLECTION:
        return []
    hits = []
    for field, pattern in ID_FIELDS.items():
        ids = sorted({m.upper() for m in pattern.findall(query)})
        if ids:
            points, _ = get_client().scroll(collection, scroll_filter=build_filter(**{field: ids}),
                                            limit=len(ids) * 2, with_payload=True)
            hits += [dict(p.payload, score=1.0, match="exact_id") for p in points]
    return hits


def plan_queries(query, extra_queries=(), use_glossary=True, use_dense=True, use_bm25=True):
    """Which searches to run. Returned for transparency (shown in debug output / eval reports)."""
    dense, sparse = [], []
    for q in [query, *extra_queries]:
        if use_dense:
            dense.append(q)
        if use_bm25:
            sparse.append(q)
    if use_glossary and use_bm25 and is_vietnamese(query):
        terms = expand(query)
        if terms:
            sparse.append(terms)
    return {"dense": dense, "bm25": sparse}


def search(query, collection=KB_COLLECTION, limit=8, query_filter=None, prefetch_limit=40,
           embedder=DEFAULT_EMBEDDER, extra_queries=(), use_glossary=True, use_dense=True, use_bm25=True,
           rerank=False, rerank_candidates=30):
    """Exact ID lookup + multi-query hybrid search, optionally reranked by a cross-encoder.
    Returns payload dicts with an added 'score' (RRF; 1.0 for exact-ID hits) and, when rerank=True,
    'rerank_score' (0-1)."""
    fused_limit = max(limit, rerank_candidates) if rerank else limit
    plan = plan_queries(query, extra_queries, use_glossary, use_dense, use_bm25)
    prefetch = [models.Prefetch(query=embed_query(q, embedder), using=dense_name(embedder),
                                filter=query_filter, limit=prefetch_limit) for q in plan["dense"]]
    prefetch += [models.Prefetch(query=to_sparse(next(sparse_model().query_embed(q))), using="bm25",
                                 filter=query_filter, limit=prefetch_limit) for q in plan["bm25"]]
    res = get_client().query_points(
        collection_name=collection,
        prefetch=prefetch,
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=fused_limit,
        with_payload=True,
    )
    exact = exact_id_hits(query, collection)
    seen = {h["chunk_id"] for h in exact}
    hybrid = [dict(p.payload, score=p.score) for p in res.points if p.payload["chunk_id"] not in seen]
    if rerank:
        hybrid = rerank_hits(query, hybrid)
        exact = rerank_hits(query, exact)  # scored too, but exact-ID hits stay on top
    return (exact + hybrid)[:limit]
