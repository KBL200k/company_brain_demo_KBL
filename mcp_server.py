"""MCP server for the Company Brain knowledge base (stdio transport).

Exposes the full RAG pipeline (`ask`) and the individual retrieval tools, so any MCP client
(Claude Code, Claude Desktop, ...) can use them. Requires the Qdrant server to be running
(qdrant_server/start_qdrant.bat).

  python mcp_server.py            # run over stdio (what MCP clients launch)
Registered for Claude Code in .mcp.json.
"""
import sys
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from app import history, tools  # noqa: E402
from app.llm import DEFAULT_PROVIDER, PROVIDERS, available_providers  # noqa: E402
from app.rag import answer  # noqa: E402
from app.router import route  # noqa: E402

server = MCPServer(
    name="company-brain",
    instructions=(
        "Internal knowledge base of Glow Recipe (fruit skincare lines only): products, real Sephora reviews and "
        "insights, brand voice, marketing claims policy, FDA/FTC rules, return/shipping policies, SOPs and creative "
        "test learnings. Use `ask` for a complete, cited answer; use the other tools to look things up directly. "
        "Cite results by their ids (chunk_id, review_id, product/<id>)."
    ),
)

Provider = Literal["claude", "openai", "gemini"]


@server.tool()
def ask(question: str, provider: Provider | None = None, conversation_id: str | None = None) -> dict:
    """Answer a question about the brand end to end: routing, retrieval, a cited answer and verification.
    Out-of-scope questions are declined. Works in Vietnamese or English.

    Args:
        question: The question, Vietnamese or English.
        provider: LLM to use: claude, openai or gemini. Defaults to the server's LLM_PROVIDER.
        conversation_id: Continue a saved conversation so follow-ups ("what about the mini?") are understood.
            Pass "new" (or an unknown id) to start one; the result's conversation_id is the one to reuse.
            Omit for a one-off question that is not saved.
    """
    if not conversation_id:
        return answer(question, provider=provider)
    if conversation_id == "new" or not history.conversation_exists(conversation_id):
        conversation_id = history.create_conversation(question)
    context = history.recent_turns(history.get_messages(conversation_id))
    history.add_message(conversation_id, "user", question)
    result = answer(question, provider=provider, history=context)
    history.add_message(conversation_id, "assistant", result["answer"], result)
    return {**result, "conversation_id": conversation_id}


@server.tool()
def route_question(question: str, provider: Provider | None = None) -> dict:
    """Classify a question (route, in/out of scope, language, products mentioned) without answering it."""
    return route(question, provider)


@server.tool()
def search_knowledge(query: str, doc_types: list[str] | None = None, product_ids: list[str] | None = None,
                     limit: int = 6) -> dict:
    """Hybrid search (multilingual embeddings + BM25 + rerank) over the knowledge base.

    Args:
        query: What to look for.
        doc_types: Optional filter: product, catalog, customer_research, brand, brand_compliance, regulation,
            policy, sop, creative_learnings, template.
        product_ids: Optional product filter, e.g. ["P481989"].
        limit: Number of passages (default 6).
    """
    return tools.search_knowledge(query, doc_types=doc_types, product_ids=product_ids, limit=limit)


@server.tool()
def search_reviews(query: str, product_id: str | None = None, rating_min: int | None = None,
                   rating_max: int | None = None, skin_type: str | None = None,
                   exclude_incentivized: bool = False, limit: int = 5) -> dict:
    """Search real customer reviews with optional filters; returns verbatim text and review_id."""
    return tools.search_reviews(query, product_id=product_id, rating_min=rating_min, rating_max=rating_max,
                                skin_type=skin_type, exclude_incentivized=exclude_incentivized, limit=limit)


@server.tool()
def lookup_products(product_line: str | None = None, product_type: str | None = None, active: str | None = None,
                    max_price: float | None = None, min_price: float | None = None,
                    name_contains: str | None = None, include_minis: bool = True) -> dict:
    """Exact catalog lookup: counts, lists, prices, sizes, minis, types, actives (aha, bha, retinoid, ...)."""
    return tools.lookup_products(product_line=product_line, product_type=product_type, active=active,
                                 max_price=max_price, min_price=min_price, name_contains=name_contains,
                                 include_minis=include_minis)


@server.tool()
def get_document(doc_or_chunk_id: str) -> dict:
    """Full text of a chunk (e.g. brand/claims-policy#cp-05) or a whole document (e.g. sop/review-response)."""
    return tools.get_document(doc_or_chunk_id)


@server.tool()
def check_claims(text: str, product_ids: list[str] | None = None) -> dict:
    """Check marketing copy against the claims policy; returns violations with rule IDs and severity."""
    return tools.check_claims(text, product_ids=product_ids)


@server.tool()
def list_providers() -> dict:
    """Which LLM providers have credentials configured, and the default."""
    return {"providers": list(PROVIDERS), "configured": available_providers(), "default": DEFAULT_PROVIDER}


if __name__ == "__main__":
    server.run("stdio")
