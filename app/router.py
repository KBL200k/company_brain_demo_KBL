"""Question routing: decide what kind of question this is, whether it is in scope, and how to search.

Two routers with the same output:
  route_llm   - the selected LLM with a JSON-schema response (handles paraphrase, slang, no accents)
  route_rules - keyword rules in English + Vietnamese (accent-insensitive); used without an LLM or if it fails
The pipeline adds a final check after retrieval: if nothing relevant is found, the question is treated
as out of scope even when the router let it through.
"""
import re

from app.glossary import is_vietnamese, strip_accents
from app.llm import LLMRefused, LLMUnavailable, get_llm
from app.tools import resolve_products

ROUTES = {
    "product_catalog": "facts about our products: prices, sizes, minis, ingredients/actives, product types, "
                       "how many products, which product does X, listing a line",
    "customer_insight": "what customers think: praise, complaints, ratings, trends over time, skin-type segments, "
                        "incentivized-review share, product rankings",
    "review_evidence": "the user wants actual customer review quotes or examples",
    "compliance": "can we say / claim / write X, marketing claims rules, FDA/FTC/MoCRA regulations, disclosures, "
                  "warning labels, what is banned",
    "sop_policy": "internal processes and customer-facing policies: returns, refunds, shipping, customer care, "
                  "adverse reaction handling, ad approval steps, influencer brief process",
    "creative": "paid-social creative tests and learnings, which ads won or lost, what to test next",
    "brand": "brand positioning, tagline, tone of voice, vocabulary, emoji, channel formats, commitments",
    "generation": "the user asks us to WRITE something: a creative brief, ad copy, caption, email, reply to a review, "
                  "a summary or recommendation document",
    "chitchat": "greetings, thanks, or asking what the assistant can do",
    "out_of_scope": "anything not about this brand's products, customers, marketing, compliance or operations "
                    "(other brands/products, general knowledge, weather, coding, personal or medical advice, "
                    "products outside the knowledge base such as the lip balm or kits)",
}

ROUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "route": {"type": "string", "enum": list(ROUTES)},
        "in_scope": {"type": "boolean"},
        "standalone_question": {"type": "string",
                                "description": "The question rewritten to be understandable without the "
                                               "conversation, in the user's language"},
        "language": {"type": "string", "enum": ["vi", "en", "other"]},
        "search_query_en": {"type": "string", "description": "The question rewritten as a short English search query"},
        "product_mentions": {"type": "array", "items": {"type": "string"},
                             "description": "Product or product-line names mentioned, in English"},
        "rating_filter": {"type": "string", "enum": ["any", "negative", "positive"]},
        "reason": {"type": "string"},
    },
    "required": ["route", "in_scope", "standalone_question", "language", "search_query_en", "product_mentions",
                 "rating_filter", "reason"],
    "additionalProperties": False,
}

ROUTER_SYSTEM = """You route questions for the internal knowledge assistant of Glow Recipe, a DTC skincare brand.

The knowledge base covers ONLY:
- the 7 fruit skincare lines (Watermelon, Plum, Avocado, Strawberry, Guava, Blueberry, Papaya): 19 products + 6 minis
- real Sephora customer reviews 2018-2023 and insight reports computed from them
- brand positioning and voice guide, internal marketing claims policy, FDA/FTC/MoCRA rules
- glowrecipe.com return and shipping policies, internal SOPs, paid-social creative test learnings
NOT covered: Glow Recipe's lip balm (Glow Lip Pop) and kits, other brands, company finances/HR/stores, general
skincare or medical advice, and anything unrelated to the brand.

Routes:
""" + "\n".join(f"- {k}: {v}" for k, v in ROUTES.items()) + """

Rules:
- in_scope is false for out_of_scope questions, true otherwise (chitchat counts as in scope).
- Questions may be English or Vietnamese, with or without accents, with chat abbreviations
  (e.g. "kcn" = kem chống nắng = sunscreen, "srm" = sữa rửa mặt = cleanser, "dc" = được, "ko" = không).
- search_query_en: a short English search query with product names and key terms spelled out.
- "can we say/write/call X" is compliance even when it names a product.
- rating_filter: negative for complaints/problems, positive for praise, otherwise any.
- The conversation so far may be given. Follow-up questions ("còn bản mini thì sao?", "what about oily skin?",
  "viết lại ngắn hơn") refer to it: resolve them into standalone_question (name the product/topic explicitly)
  and route the resolved question. Without a follow-up, standalone_question is the question itself."""


RULES = [  # (route, pattern on accent-stripped lowercase text), checked in order
    ("chitchat", r"^\s*((hi|hello|hey|xin chao|chao( ban)?)[\s,!.]*)?(cam on|thanks?|thank you|ban la ai|"
                 r"who are you|ban (co the )?(lam|giup)( duoc)? gi|what can you do|how can you help)?[\s!?.]*$"),
    ("brand_first", r"(emojis?|giong van|tone of voice|\bvoice\b|tagline|slogan)"),
    ("generation", r"\b(viet|soan|draft|write|compose|tom tat|summari[sz]e|lap brief|tao (mot |1 )?(brief|caption|"
                   r"noi dung|bai|email|kich ban)|caption|kich ban|script)\b"),
    ("compliance", r"(co (duoc|dc) (noi|ghi|goi|viet|dung|quang cao|claim)|(duoc|dc) phep|(can|may) we (say|call|use|claim|"
                   r"write|describe)|is it (ok|fine|allowed)|allowed to|\bclaims?\b|tuyen bo|\bluat\b|quy dinh|"
                   r"\bfda\b|\bftc\b|mocra|compliance|vi pham|disclos|#ad|#gifted|\bcp-\d\d|sunblock|waterproof|"
                   r"chong nuoc|lam sang|clinically|canh bao)"),
    ("review_evidence", r"(\btrich\b|\bquotes?\b|vi du (ve )?review|cau review|examples? of reviews?|show (me )?"
                        r"reviews|reviews? (that|saying|which say))"),
    ("sop_policy", r"(tra hang|doi tra|hoan tien|\breturns?\b|refund|\bship|giao hang|van chuyen|quy trinh|\bsop\b|"
                   r"cskh|customer care|xu ly|escalat|phan ung|adverse|di ung|duyet|approv|creator|influencer|kol|koc)"),
    ("creative", r"(quang cao nao|\bads?\b|creative|\bct-\d\d|test quang cao|a/b|\bcpa\b|\bctr\b|mau quang cao|"
                 r"chien dich|campaign|nen test)"),
    ("customer_insight", r"(khach (hang )?(noi|nghi|thich|che|phan nan|danh gia|khen)|phan nan|complain|customers? "
                         r"(say|think|like|love|hate|rate)|danh gia|rating|reviews?|insight|nhan xet|cam nhan|"
                         r"loai da|skin type|\bda (dau|kho|hon hop|nhay cam|thuong)\b|(oily|dry|combination|"
                         r"sensitive|normal) skin|xu huong|trend|gay (noi )?mun|break ?out|kich ung|irritat)"),
    ("brand", r"(giong van|\btone\b|\bvoice\b|tagline|slogan|thuong hieu|\bbrand\b|emoji|tu (nao )?nen tranh|"
              r"vegan|cruelty|gioi thieu (ve )?(cong ty|glow recipe))"),
    ("product_catalog", r"(\bgia\b|price|cost|(bao nhieu|may|bn) (san pham|loai|tien|size|ml)|how many|thanh phan|ingredient|"
                        r"dung tich|\bsize|\bmini\b|co nhung (san pham|dong)|liet ke|\blist\b|san pham nao|which product|"
                        r"\bserum|cleanser|toner|\bkem\b|sua rua mat|chong nang|sunscreen|\bchua\b|contain|retinol|"
                        r"\baha\b|\bbha\b|dong san pham|product line)"),
]

DOMAIN_HINTS = r"(glow recipe|watermelon|dua hau|plum|\bman\b|avocado|\bbo\b|strawberry|\bdau\b|guava|\boi\b|" \
               r"blueberry|viet quat|papaya|du du|skincare|my pham|cosmetic|sephora)"


# Glow Recipe products deliberately left out of the knowledge base (scripts/prepare_data.py EXCLUDED_LINES)
EXCLUDED_PRODUCTS = r"(lip pop|lip balm|son duong|son moi|\bkits?\b|fruit babies|plumping power duo|glowy skin prep|" \
                    r"bo qua|gift set)"


# Other brands: out of scope even when the question also uses one of our product words ("serum").
COMPETITORS = r"(the ordinary|rare beauty|la roche|cerave|paula'?s choice|drunk elephant|tatcha|laneige|clinique|" \
              r"innisfree|cosrx|some by mi|olay|neutrogena|fenty|glossier|summer fridays|youth to the people)"
# Clearly unrelated topics; checked only when the question names none of our products.
OFF_TOPIC = r"(\bpython\b|javascript|\bcode\b|lap trinh|bitcoin|crypto|chung khoan|stock price|doanh thu|revenue|" \
            r"loi nhuan|profit|\bceo\b|nhan vien|employees|thoi tiet|weather|nha hang|restaurant|mat khau|password|" \
            r"uong thuoc|thuoc gi|bac si nao|which (medicine|drug)|doctor)"
# words that make a writing request a marketing task rather than a general one
MARKETING = r"(caption|brief|quang cao|\bads?\b|email|post|review|khach|customer|san pham|product|serum|kem|" \
            r"cleanser|toner|sunscreen|chong nang|insight|chien dich|campaign|tagline|copy)"


def _rules_result(question, route, reason, products=(), domain=False, rating="any"):
    return {"route": route, "in_scope": route != "out_of_scope", "domain_terms": domain,
            "language": "vi" if is_vietnamese(question) else "en", "search_query_en": "",
            "product_mentions": [], "product_ids": list(products), "rating_filter": rating,
            "reason": reason, "router": "rules"}


def route_rules(question):
    norm = strip_accents(question).lower()
    products = resolve_products(question)
    if re.search(COMPETITORS, norm) and not re.search(r"glow recipe", norm):
        return _rules_result(question, "out_of_scope", "asks about another brand's products")
    if not products and re.search(OFF_TOPIC, norm):
        return _rules_result(question, "out_of_scope",
                             "unrelated topic (other brand, finance, coding, weather, medical, ...)")
    if re.search(EXCLUDED_PRODUCTS, norm):
        return {"route": "out_of_scope", "in_scope": False, "domain_terms": True,
                "language": "vi" if is_vietnamese(question) else "en", "search_query_en": "",
                "product_mentions": [], "product_ids": [], "rating_filter": "any",
                "reason": "asks about a product that is not in the knowledge base (lip balm / kits)", "router": "rules"}
    route = next((r for r, pat in RULES if re.search(pat, norm)), None)
    if route == "brand_first":
        route = "brand"
    domain = bool(products or re.search(DOMAIN_HINTS, norm))
    if route == "generation" and not (domain or re.search(MARKETING, norm)):
        route = "unknown"  # "write a sorting function" is not a marketing task; let the relevance gate decide
    if route is None:
        # nothing matched: let retrieval decide (the relevance gate rejects unrelated questions)
        route = "product_catalog" if products else "unknown"
    rating = "any"
    # "kem" (cream) and "kém" (poor) collide once accents are stripped, so "kem" is not a negative cue
    if re.search(r"\b(che|phan nan|complain\w*|negative|bad|worst|thap nhat|lowest|1 sao|1-2 sao|"
                 r"van de|problems?|issues?|noi mun|break ?outs?|kich ung|irritat\w*|von|pill\w*)\b", norm):
        rating = "negative"
    elif re.search(r"\b(khen|thich|praise\w*|love\w*|positive|tot nhat|best|cao nhat|highest)\b", norm):
        rating = "positive"
    return {"route": route, "in_scope": route != "out_of_scope", "domain_terms": domain,
            "language": "vi" if is_vietnamese(question) else "en", "search_query_en": "",
            "product_mentions": [], "product_ids": products, "rating_filter": rating,
            "reason": "keyword rules", "router": "rules"}


def _history_text(history, answer_chars=300):
    lines = []
    for m in history or []:
        text = m["content"] if m["role"] == "user" else m["content"][:answer_chars]
        lines.append(f"{'User' if m['role'] == 'user' else 'Assistant'}: {text}")
    return "\n".join(lines)


def route_llm(question, provider=None, model=None, api_key=None, history=None):
    llm = get_llm(provider, model=model, api_key=api_key)
    user = f"Question: {question}"
    if history:
        user = f"Conversation so far:\n{_history_text(history)}\n\n{user}"
    out = llm.structured(ROUTER_SYSTEM, user, ROUTE_SCHEMA, temperature=0.0)  # classification: deterministic
    standalone = out.get("standalone_question") or question
    hints = " ".join([standalone, *out.get("product_mentions", [])])
    out["product_ids"] = resolve_products(hints)
    out["domain_terms"] = out["in_scope"]
    out["router"] = f"llm:{llm.name}"
    return out


# Follow-up cues (accent-stripped): "còn ... thì sao", "thế còn", "nó", "sản phẩm đó", "what about", "it" ...
FOLLOW_UP = (r"^\s*(con|the con|vay con|con ve|va|what about|how about|and|also|same for)\b|"
             r"\b(thi sao|the nao|nua khong|san pham (do|nay|tren)|cai (do|nay)|dong (do|nay)|no\b|"
             r"it\b|its\b|that one|this one|the same|ngan hon|dai hon|viet lai|rewrite|shorter|longer)")


def contextualize_rules(question, r, history):
    """Rule-based follow-up handling: when the question looks like a follow-up, reuse the previous
    question as context for retrieval and carry over its products (and route, if none matched)."""
    if not history or r["route"] in ("out_of_scope", "chitchat"):
        return r
    # anchor follow-up chains on the original question, not on the previous follow-up
    last_user = next((m["standalone"].split(" → ")[0] for m in reversed(history)
                      if m["role"] == "assistant" and m.get("standalone")), None) \
        or next((m["content"] for m in reversed(history) if m["role"] == "user"), None)
    last_products = next((m.get("product_ids") for m in reversed(history)
                          if m["role"] == "assistant" and m.get("product_ids")), [])
    norm = strip_accents(question).lower()
    short = len(norm.split()) <= 5
    if not last_user or not (re.search(FOLLOW_UP, norm) or (short and not r["product_ids"])):
        return r
    r = dict(r)
    r["standalone_question"] = f"{last_user} → {question}"
    if not r["product_ids"] and last_products:
        r["product_ids"] = list(last_products)
    if r["route"] == "unknown":
        prev = resolve_products(last_user)
        r["route"] = route_rules(last_user)["route"] if prev or last_products else r["route"]
    r["reason"] += "; follow-up of the previous question"
    return r


def route(question, provider=None, model=None, api_key=None, use_llm=True, history=None):
    """LLM router when available (and use_llm), rule router otherwise. Never raises.
    `history`: recent turns [{"role", "content", "product_ids"?}] for resolving follow-up questions."""
    def rules(note):
        r = contextualize_rules(question, route_rules(question), history)
        r.setdefault("standalone_question", question)
        r["router_note"] = note
        return r

    if not use_llm:
        return rules("LLM router turned off in settings; used keyword rules")
    try:
        return route_llm(question, provider, model, api_key, history)
    except (LLMUnavailable, LLMRefused, ValueError) as e:
        return rules(f"LLM router unavailable ({e}); used keyword rules")
    except Exception as e:  # noqa: BLE001 - routing must not take the assistant down
        return rules(f"LLM router error ({type(e).__name__}: {e}); used keyword rules")
