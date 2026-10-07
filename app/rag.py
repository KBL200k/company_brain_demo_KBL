"""The RAG pipeline: route -> retrieve (per route) -> relevance gate -> generate -> verify.

  answer("Có được gọi kem chống nắng là chống nước không?")
  answer("Write a caption for Dew Drops", provider="gemini")
  answer(q, settings=Settings(provider="openai", model="gpt-5-mini", top_k=8, search_mode="dense"))

Returns a dict with the answer, route, sources, confidence and a trace of every step. Works without an
LLM (rule router + extractive answer), so the system can be tested before any API key is configured.
"""
import json
import re
import time

from app.glossary import expand, strip_accents
from app.llm import LLMRefused, LLMUnavailable, get_llm
from app.router import route
from app.settings import Settings
from app.tools import (TOOL_SPECS, check_claims, get_document, lookup_products, run_tool, search_knowledge,
                       search_reviews)

# Relevance gates (Settings.out_of_scope_gate / no_info_gate) use the rerank score. Without rerank there is
# no score comparable across questions, so only the router decides scope.
LINES = ["Watermelon", "Plum", "Avocado", "Strawberry", "Guava", "Blueberry", "Papaya"]

# what to retrieve for each route: knowledge-base doc types, review search, structured lookup, claims check
PLANS = {
    "product_catalog": {"doc_types": ["product", "catalog"], "lookup": True},
    "customer_insight": {"doc_types": ["customer_research", "catalog"], "reviews": 3, "product_filter": True},
    "review_evidence": {"doc_types": ["customer_research"], "reviews": 8, "product_filter": True, "kb_limit": 3},
    "compliance": {"doc_types": ["brand_compliance", "regulation", "sop"], "claims": True},
    "sop_policy": {"doc_types": ["sop", "policy", "regulation"]},
    "creative": {"doc_types": ["creative_learnings", "customer_research"]},
    "brand": {"doc_types": ["brand", "catalog"]},
    "generation": {"doc_types": None, "reviews": 4, "lookup": True, "always": [
        "brand/claims-policy#quick-lookup-by-product", "brand/voice-guide#vocabulary", "brand/voice-guide#channel-formats"]},
    "unknown": {"doc_types": None},
}

SYSTEM = """You are Company Brain, the internal knowledge assistant of Glow Recipe, a DTC skincare brand.
Your users are the marketing, creative and customer-care teams.

Grounding
- Answer only from the <sources> in the message and from tool results. Never use outside knowledge.
- Cite every factual statement with the source id in square brackets, e.g. [brand/claims-policy#cp-05],
  [product/P481989], [review/P481989-21808]. Use only ids that appear in the sources or tool results.
- If the sources do not answer the question, say plainly that the knowledge base does not have enough
  information, and name what is missing. Do not guess.
- Counts, prices, sizes and product lists must come from lookup_products results, not from estimates.

Sources
- source_type real: public data (Sephora catalog and reviews, FDA/FTC texts, glowrecipe.com).
- source_type derived: statistics computed from reviews; percentages are directional.
- source_type synthetic: internal company documents (claims policy, SOPs, voice guide, creative test log).
  Present them as internal policy or internal test results, not as public facts.
- Reviews marked incentivized came from free-product programs; say so if you quote one.

Style
- Reply in the language of the question (Vietnamese or English). Keep review quotes verbatim in English; when
  replying in Vietnamese, add a short Vietnamese paraphrase.
- Lead with the direct answer, then the supporting points. Be concise.

Compliance
- Any marketing copy you write must follow brand/claims-policy and brand/voice-guide. Before writing any reply
  text, call check_claims with the full draft as its argument and fix every BLOCK violation; then write the
  complete final answer once, from the beginning. Do not write part of the answer before or between tool calls.
  List REVIEW items as needing regulatory sign-off.
- No medical advice: for skin reactions, point to the adverse-event SOP.

Conversation
- Earlier turns may be given in <conversation>. Use them to understand follow-up questions ("what about the mini?",
  "make it shorter"), but take facts only from <sources> and tool results, not from earlier answers.

You can call tools to look further when the given sources are not enough."""

MODE_INSTRUCTIONS = {
    "strict": """Answer mode: STRICT. This question is about processes, policies, rules or product facts, where a
wrong answer is not acceptable.
- State only what the sources say. Do not infer, generalize, combine sources into new conclusions, or add advice
  that is not in the sources.
- End every sentence with its citation [id].
- Keep the wording close to the source and copy numbers, deadlines, prices and rule IDs exactly.
- If the sources do not cover part of the question, say that part is not in the knowledge base.""",
    "flexible": """Answer mode: FLEXIBLE. Write naturally and helpfully: you may summarize, structure, explain and
phrase freely, but every fact still needs a source and a citation.""",
}
# An answer without citations is acceptable in strict mode only when it says the information is missing.
SAYS_NO_INFO = re.compile(r"không (có )?đủ thông tin|không có (trong|thông tin)|chưa có thông tin|"
                          r"not enough information|not in the knowledge base|does not (have|contain|cover)|"
                          r"no information", re.I)

REFUSAL = {
    "vi": "Xin lỗi, câu hỏi này nằm ngoài phạm vi của trợ lý. Mình chỉ trả lời về các dòng sản phẩm trái cây của "
          "Glow Recipe (sản phẩm, đánh giá khách hàng, thương hiệu, quy định quảng cáo, chính sách, quy trình nội bộ "
          "và kết quả test quảng cáo).",
    "en": "Sorry, that question is outside what this assistant covers. I can help with Glow Recipe's fruit skincare "
          "lines: products, customer reviews, brand, marketing-claims rules, policies, internal processes and "
          "creative test results.",
}
CHITCHAT = {
    "vi": "Chào bạn! Mình là trợ lý kiến thức nội bộ của Glow Recipe. Bạn có thể hỏi về sản phẩm (giá, thành phần, "
          "dung tích), khách hàng nghĩ gì, quy định claim quảng cáo, chính sách đổi trả, quy trình CSKH, kết quả test "
          "quảng cáo, hoặc nhờ mình viết creative brief / caption đúng quy định.",
    "en": "Hi! I'm Glow Recipe's internal knowledge assistant. Ask me about products (prices, ingredients, sizes), "
          "what customers think, marketing-claims rules, return policy, customer-care processes, creative test results, "
          "or ask me to draft a compliant creative brief or caption.",
}
NO_INFO = {
    "vi": "Kho kiến thức không có đủ thông tin để trả lời câu hỏi này.",
    "en": "The knowledge base does not have enough information to answer this question.",
}


class Timer:
    def __init__(self):
        self.steps = {}

    def __call__(self, name):
        timer = self

        class _T:
            def __enter__(self):
                self.t = time.perf_counter()

            def __exit__(self, *exc):
                timer.steps[name] = round((time.perf_counter() - self.t) * 1000)
        return _T()


def _lang(r):
    return "vi" if r.get("language") == "vi" else "en"


def _lines_in(text):
    words = set(re.findall(r"[a-z]+", (strip_accents(text) + " " + expand(text)).lower()))
    return [l for l in LINES if l.lower() in words]


def retrieve(question, r, s=None):
    """Run the retrieval plan for the route with settings `s`. Returns (context items, retrieval trace)."""
    s = s or Settings()
    plan = PLANS.get(r["route"], PLANS["unknown"])
    pids = r.get("product_ids") or []
    extra = [r["search_query_en"]] if r.get("search_query_en") else []
    flags = s.search_flags()
    items, trace = {"kb": [], "reviews": [], "products": None, "claims": None}, []

    kb_limit = min(plan["kb_limit"], s.top_k) if "kb_limit" in plan else s.top_k
    kb = search_knowledge(question, doc_types=plan["doc_types"],
                          product_ids=pids if plan.get("product_filter") else None,
                          limit=kb_limit, rerank=s.rerank, rerank_candidates=s.rerank_candidates,
                          extra_queries=extra, **flags)
    items["kb"] = kb["results"]
    trace.append({"tool": "search_knowledge", "doc_types": plan["doc_types"], "top_k": kb_limit,
                  "search_mode": s.search_mode, "rerank": s.rerank, "hits": kb["count"],
                  "top_relevance": kb["top_relevance"]})

    for cid in plan.get("always", []):
        if all(x["chunk_id"] != cid for x in items["kb"]):
            d = get_document(cid)
            items["kb"].append({"chunk_id": cid, "title": d.get("title"), "source_type": d.get("source_type"),
                                "doc_type": "brand", "text": d.get("text", "")})

    if plan.get("reviews"):
        rating = r.get("rating_filter", "any")
        rv = search_reviews(r.get("search_query_en") or question, product_id=pids[0] if len(pids) == 1 else None,
                            rating_max=2 if rating == "negative" else None,
                            rating_min=4 if rating == "positive" or r["route"] == "generation" else None,
                            exclude_incentivized=r["route"] == "generation",
                            limit=s.review_k if r["route"] == "review_evidence" else min(plan["reviews"], s.review_k),
                            **flags)
        items["reviews"] = rv["results"]
        trace.append({"tool": "search_reviews", "product_id": pids[0] if len(pids) == 1 else None,
                      "rating": rating, "hits": rv["count"]})

    if plan.get("lookup"):
        lines = _lines_in(question)
        args = {"product_ids": pids} if pids else ({"product_line": lines[0]} if len(lines) == 1 else {})
        items["products"] = lookup_products(**args)
        trace.append({"tool": "lookup_products", "args": args, "listings": items["products"]["count_listings"]})

    if plan.get("claims"):
        items["claims"] = check_claims(question, pids)
        trace.append({"tool": "check_claims", "violations": len(items["claims"]["violations"])})
    return items, trace


def format_sources(items):
    parts = []
    for x in items["kb"]:
        parts.append(f'<source id="{x["chunk_id"]}" type="{x.get("source_type")}" title="{x.get("title")}">\n'
                     f'{x["text"]}\n</source>')
    for x in items["reviews"]:
        parts.append(f'<source id="{x["review_id"]}" type="real" title="Customer review of {x["product_id"]}, '
                     f'{x["rating"]}★, skin {x["skin_type"]}, incentivized={x["incentivized"]}">\n{x["text"]}\n</source>')
    if items["products"]:
        p = items["products"]
        rows = [{k: v for k, v in row.items() if k != "source"} | {"id": row["source"]} for row in p["products"]]
        parts.append(f'<source id="lookup_products" type="real" title="Catalog lookup: {p["count_listings"]} listings, '
                     f'{p["count_distinct_products"]} distinct products, {p["count_minis"]} minis">\n'
                     f'{json.dumps(rows, ensure_ascii=False, default=str)}\n</source>')
    if items["claims"] and items["claims"]["violations"]:
        parts.append(f'<source id="check_claims" type="derived" title="Claims check of the phrases in the question">\n'
                     f'{json.dumps(items["claims"], ensure_ascii=False)}\n</source>')
    return "\n\n".join(parts)


def known_ids(items, tool_calls_text=""):
    ids = {x["chunk_id"] for x in items["kb"]} | {x["review_id"] for x in items["reviews"]}
    if items["products"]:
        ids |= {p["source"] for p in items["products"]["products"]} | {"lookup_products"}
    if items["claims"]:
        ids.add("check_claims")
    ids |= set(re.findall(r'"(?:chunk_id|review_id|source|id)": "([^"]+)"', tool_calls_text))
    return ids


CITATION = re.compile(r"\[([a-z_]+/[^\]\s,;]+|lookup_products|check_claims)\]")


def verify_citations(text, ids):
    cited = sorted(set(CITATION.findall(text)))
    doc_ids = {i.split("#")[0] for i in ids}
    bad = [c for c in cited if c not in ids and c not in doc_ids and not any(i.startswith(c + "#") for i in ids)]
    return {"cited": cited, "invalid": bad, "ok": not bad}


def extractive_answer(question, r, items, lang):
    """No-LLM answer: the most relevant passages, quoted with their ids."""
    head = ("(Chế độ không có LLM: trích các đoạn liên quan nhất)" if lang == "vi"
            else "(No-LLM mode: the most relevant passages)")
    out = [head, ""]
    if items["products"] and r["route"] in ("product_catalog", "generation"):
        p = items["products"]
        out.append(f"- {p['count_listings']} listings ({p['count_distinct_products']} products + {p['count_minis']} "
                   f"minis): " + "; ".join(f"{x['name']} ${x['price_usd']:.0f}" for x in p["products"][:12])
                   + " [lookup_products]")
    if items["claims"] and items["claims"]["violations"]:
        out.append("- Claims check: " + "; ".join(f"\"{v['matched']}\" → {v['rule_id']} {v['severity']}"
                                                   for v in items["claims"]["violations"]) + " [check_claims]")
    for x in items["kb"][:3]:
        snippet = re.sub(r"\s+", " ", x["text"])[:350]
        out.append(f"- {x['title']}: {snippet} [{x['chunk_id']}]")
    for x in items["reviews"][:3]:
        out.append(f"- \"{re.sub(r'\s+', ' ', x['text'])[:200]}\" ({x['rating']}★) [{x['review_id']}]")
    return "\n".join(out)


def answer(question, settings=None, provider=None, rerank=None, history=None):
    """Answer one question. `settings` (app.settings.Settings) holds every tunable; anything not set comes
    from the environment. `provider` / `rerank` are shortcuts that override the matching settings.
    `history`: earlier turns of this conversation, oldest first ([{"role", "content", "product_ids"?}], see
    app.history.recent_turns); the last `settings.history_turns` pairs are used to resolve follow-up questions."""
    s = settings or Settings()
    if provider:
        s.provider = provider
    if rerank is not None:
        s.rerank = rerank
    model = s.resolved_model()
    hist = (history or [])[-s.history_turns * 2:] if s.history_turns > 0 else []
    t = Timer()
    result = {"question": question, "settings": s.public(), "history_turns_used": len(hist) // 2}
    with t("route"):
        r = route(question, s.provider, model, s.api_key, use_llm=s.use_llm_router, history=hist)
    lang = _lang(r)
    result["route"] = {k: r.get(k) for k in ("route", "in_scope", "language", "standalone_question", "product_ids",
                                             "rating_filter", "search_query_en", "reason", "router", "router_note")
                       if r.get(k) is not None}
    # retrieval works on the self-contained version of a follow-up question
    search_question = r.get("standalone_question") or question
    answer_mode, temperature = s.answer_mode(r["route"])
    result["answer_mode"] = {"mode": answer_mode, "temperature": temperature}

    def done(text, mode, **extra):
        result.update(answer=text, mode=mode, timings_ms=t.steps, **extra)
        return result

    if r["route"] == "out_of_scope" or not r.get("in_scope", True):
        return done(REFUSAL[lang], "refused_out_of_scope", confidence="high")
    if r["route"] == "chitchat":
        return done(CHITCHAT[lang], "chitchat", confidence="high")

    with t("retrieve"):
        items, trace = retrieve(search_question, r, s)
    top = max((x.get("relevance", 0) for x in items["kb"]), default=0)
    structured = bool(items["products"] and items["products"]["count_listings"]) or bool(items["reviews"])
    result.update(retrieval=trace, top_relevance=round(top, 3) if s.rerank else None,
                  sources=[{"id": x["chunk_id"], "title": x.get("title"), "source_type": x.get("source_type"),
                            "relevance": x.get("relevance")} for x in items["kb"]]
                  + [{"id": x["review_id"], "title": f"review {x['rating']}★", "source_type": "real"} for x in items["reviews"]])

    # relevance gates (rerank score only): the last line of defence against unrelated questions
    if s.rerank:
        if r["route"] == "unknown" and top < s.out_of_scope_gate and not r.get("product_ids"):
            return done(REFUSAL[lang], "refused_low_relevance", confidence="medium")
        if top < s.no_info_gate and not structured:
            return done(NO_INFO[lang], "no_information", confidence="medium")
        confidence = "high" if top >= 0.5 else "medium" if top >= s.out_of_scope_gate else "low"
    else:
        confidence = "unknown (rerank off)"

    try:
        llm = get_llm(s.provider, model=model, api_key=s.api_key, max_tool_rounds=s.max_tool_rounds)
    except LLMUnavailable as e:
        return done(extractive_answer(question, r, items, lang), "extractive", confidence=confidence,
                    llm_note=str(e))

    conversation = ""
    if hist:
        turns = "\n".join(f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:1200]}" for m in hist)
        conversation = f"<conversation>\n{turns}\n</conversation>\n\n"
    resolved = f"\n(Resolved with the conversation: {search_question})" if search_question != question else ""
    user = (f"{conversation}<sources>\n{format_sources(items)}\n</sources>\n\n{MODE_INSTRUCTIONS[answer_mode]}\n\n"
            f"Route: {r['route']}. Question ({'Vietnamese' if lang == 'vi' else 'English'}): {question}{resolved}")
    effort = "high" if r["route"] == "generation" and s.effort != "low" else s.effort
    # models without a temperature parameter keep strictness through the prompt and the checks below
    result["answer_mode"]["temperature_applied"] = llm.supports_temperature
    try:
        with t("generate"):
            gen = llm.chat_with_tools(SYSTEM, user, TOOL_SPECS, run_tool, effort=effort, temperature=temperature)
    except LLMRefused as e:
        return done(NO_INFO[lang] + f" ({e})", "llm_refused", confidence="low")
    except LLMUnavailable as e:
        return done(extractive_answer(question, r, items, lang), "extractive", confidence=confidence,
                    llm_note=str(e))
    text = gen["text"]

    # verification: citations must point at sources we actually gave or fetched; copy must pass the claims check
    tool_text = json.dumps(gen["tool_calls"], ensure_ascii=False)
    ids = known_ids(items, tool_text) | {i for c in gen["tool_calls"] for i in [c["input"].get("doc_or_chunk_id")] if i}
    cites = verify_citations(text, ids)
    claims = check_claims(text, r.get("product_ids")) if r["route"] == "generation" else None
    if claims and not claims["ok"]:
        with t("revise"):
            fix = llm.chat_with_tools(
                SYSTEM, user + f"\n\nYour previous draft:\n{text}\n\nIt breaks these claims rules:\n"
                f"{json.dumps(claims['violations'], ensure_ascii=False)}\nRewrite it so every BLOCK violation is gone.",
                TOOL_SPECS, run_tool, effort=effort, temperature=temperature)
        text = fix["text"]
        claims = check_claims(text, r.get("product_ids"))
        cites = verify_citations(text, ids)

    # strict mode: an answer that cites a source we never gave, or cites nothing while not saying
    # "not enough information", is not trusted -> show the retrieved passages verbatim instead
    if answer_mode == "strict" and (not cites["ok"] or (not cites["cited"] and not SAYS_NO_INFO.search(text))):
        reason = (f"citations not in the sources: {cites['invalid']}" if not cites["ok"]
                  else "no citations in the answer")
        result["answer_mode"]["rejected_llm_answer"] = text
        return done(extractive_answer(question, r, items, lang), "strict_fallback", confidence=confidence,
                    llm_model=llm.model, tool_calls=gen["tool_calls"], citations=cites,
                    llm_note=f"strict mode rejected the LLM answer ({reason}); showing the sources verbatim")
    return done(text, f"llm:{llm.name}", confidence=confidence, llm_model=llm.model, tool_calls=gen["tool_calls"],
                citations=cites, claims_check=claims)
