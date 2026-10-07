"""Web chat UI for the Company Brain assistant.

  streamlit run ui.py        -> http://127.0.0.1:8501

Sidebar: conversations (saved in data/history/chat.db; reopen or delete them), the LLM provider and model
(suggested list, or the live list from the provider's API), an API key (kept in this browser session only,
never written to disk), and retrieval / scope / memory settings. Anything left untouched uses .env defaults.
"""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import history as store  # noqa: E402
from app.llm import KEY_ENV, SUGGESTED_MODELS, LLMUnavailable, _env_key, list_models, temperature_supported  # noqa: E402
from app.rag import answer  # noqa: E402
from app.settings import SEARCH_MODES, Settings  # noqa: E402

st.set_page_config(page_title="Company Brain", page_icon="🍉", layout="wide")

DEFAULTS = Settings()  # values from .env
PROVIDER_LABELS = {"claude": "Claude (Anthropic)", "openai": "GPT (OpenAI)", "gemini": "Gemini (Google)"}
SEARCH_LABELS = {"hybrid": "Hybrid: ngữ nghĩa + từ khoá (khuyên dùng)", "dense": "Chỉ ngữ nghĩa (dense vector)",
                 "bm25": "Chỉ từ khoá (BM25)"}
MODE_LABELS = {"refused_out_of_scope": "từ chối: ngoài phạm vi", "refused_low_relevance": "từ chối: không liên quan",
               "no_information": "không đủ thông tin", "chitchat": "trò chuyện", "extractive": "trích đoạn (không LLM)",
               "llm_refused": "LLM từ chối",
               "strict_fallback": "nghiêm ngặt: câu trả lời LLM không qua kiểm tra, hiển thị nguyên văn nguồn"}
ROUTE_LABELS = {"sop_policy": "Quy trình & chính sách (SOP, đổi trả, giao hàng)",
                "compliance": "Quy định & luật quảng cáo (claims, FDA/FTC)",
                "product_catalog": "Thông tin sản phẩm (giá, size, thành phần)",
                "customer_insight": "Insight khách hàng", "review_evidence": "Trích review",
                "creative": "Kết quả test quảng cáo", "brand": "Thương hiệu & giọng văn",
                "generation": "Viết nội dung (brief, caption…)", "unknown": "Câu chưa rõ loại"}
SETTING_KEYS = ["provider", "api_key", "model_choice", "model_custom", "search_mode", "top_k", "review_k",
                "use_glossary", "rerank", "rerank_candidates", "prefetch_limit", "use_llm_router",
                "out_of_scope_gate", "no_info_gate", "effort", "max_tool_rounds", "history_turns",
                "strict_routes", "temperature"]


def init_state():
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("conversation_id", None)  # created on the first question
    st.session_state.setdefault("live_models", {})  # provider -> list from the API
    st.session_state.setdefault("history_turns", DEFAULTS.history_turns)
    st.session_state.setdefault("strict_routes", [r for r in DEFAULTS.strict_routes if r in ROUTE_LABELS])
    st.session_state.setdefault("temperature", DEFAULTS.temperature)
    for key, value in {
        "provider": DEFAULTS.provider, "api_key": "", "model_custom": "",
        "search_mode": DEFAULTS.search_mode, "top_k": DEFAULTS.top_k, "review_k": DEFAULTS.review_k,
        "use_glossary": DEFAULTS.use_glossary, "rerank": DEFAULTS.rerank,
        "rerank_candidates": DEFAULTS.rerank_candidates, "prefetch_limit": DEFAULTS.prefetch_limit,
        "use_llm_router": DEFAULTS.use_llm_router, "out_of_scope_gate": DEFAULTS.out_of_scope_gate,
        "no_info_gate": DEFAULTS.no_info_gate, "effort": DEFAULTS.effort, "max_tool_rounds": DEFAULTS.max_tool_rounds,
    }.items():
        st.session_state.setdefault(key, value)


def model_options(provider):
    env_model = Settings(provider=provider).resolved_model()
    live = st.session_state.live_models.get(provider)
    options = live or SUGGESTED_MODELS[provider]
    return ([env_model] if env_model not in options else []) + options, env_model


def _local_time(iso):
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d/%m %H:%M")
    except ValueError:
        return iso


def open_conversation(cid):
    st.session_state.conversation_id = cid
    st.session_state.messages = store.get_messages(cid) if cid else []


def conversations_panel(sb):
    sb.header("💬 Hội thoại")
    if sb.button("➕ Cuộc trò chuyện mới", width="stretch", type="primary"):
        open_conversation(None)
        st.rerun()
    convs = store.list_conversations(limit=30)
    if not convs:
        sb.caption("Chưa có cuộc trò chuyện nào được lưu.")
    current = st.session_state.conversation_id
    for c in convs:
        label = f"{'▶ ' if c['id'] == current else ''}{c['title'][:42]}"
        if sb.button(label, key=f"conv_{c['id']}", width="stretch",
                     help=f"{c['n']} tin nhắn · cập nhật {_local_time(c['updated_at'])}"):
            open_conversation(c["id"])
            st.rerun()
    if current and sb.button("🗑 Xoá cuộc trò chuyện đang mở", width="stretch"):
        store.delete_conversation(current)
        open_conversation(None)
        st.rerun()
    sb.caption("Lịch sử lưu trên máy này (data/history/chat.db), không lưu API key.")
    sb.divider()


def sidebar():
    sb = st.sidebar
    conversations_panel(sb)
    sb.header("⚙️ Cài đặt")

    # ---- LLM
    sb.subheader("Mô hình LLM")
    provider = sb.selectbox("Nhà cung cấp", list(PROVIDER_LABELS), format_func=PROVIDER_LABELS.get, key="provider")
    env_has_key = bool(_env_key(provider))
    sb.text_input("API key", type="password", key="api_key",
                  placeholder="Để trống = dùng key trong .env" if env_has_key else "Dán API key vào đây",
                  help=f"Chỉ lưu trong phiên trình duyệt này, không ghi ra đĩa. Để trống thì dùng {KEY_ENV[provider]} "
                       "trong .env.")
    key = st.session_state.api_key.strip() or None
    if not key and not env_has_key:
        sb.caption("⚠️ Chưa có key: trợ lý chạy ở chế độ không LLM (router theo luật, trả lời bằng trích đoạn).")

    options, env_model = model_options(provider)
    if st.session_state.get("model_choice") not in options:
        st.session_state.model_choice = env_model
    sb.selectbox("Model", options, key="model_choice",
                 help="Danh sách gợi ý; bấm nút bên dưới để lấy danh sách model mà key của bạn dùng được.")
    if sb.button("🔄 Tải danh sách model từ API", width="stretch"):
        try:
            with st.spinner("Đang lấy danh sách model..."):
                models = list_models(provider, key)
            st.session_state.live_models[provider] = models
            sb.success(f"Tìm thấy {len(models)} model.")
            st.rerun()
        except LLMUnavailable as e:
            sb.error(f"Không lấy được danh sách: {e}")
    sb.text_input("Hoặc nhập tên model khác", key="model_custom", placeholder="vd: gpt-5-mini")
    sb.select_slider("Mức suy luận (effort)", ["low", "medium", "high"], key="effort",
                     help="Cao hơn = kỹ hơn nhưng chậm và tốn hơn. Câu yêu cầu viết nội dung tự dùng high.")
    sb.slider("Số vòng gọi tool tối đa", 0, 8, key="max_tool_rounds",
              help="LLM có thể tự tra thêm (search, lookup_products, check_claims...). 0 = chỉ dùng nguồn đã tìm.")
    sb.slider("Số lượt hội thoại nhớ", 0, 10, key="history_turns",
              help="Số cặp hỏi–đáp trước đó dùng để hiểu câu hỏi nối tiếp (vd: 'còn bản mini thì sao?'). "
                   "0 = mỗi câu hỏi độc lập.")

    # ---- answer modes
    sb.subheader("Chế độ trả lời")
    sb.multiselect("Loại câu hỏi phải trả lời nghiêm ngặt", list(ROUTE_LABELS), format_func=ROUTE_LABELS.get,
                   key="strict_routes",
                   help="Không được trả lời sai: chỉ nêu điều có trong nguồn, câu nào cũng phải có trích dẫn, "
                        "temperature = 0. Câu trả lời có trích dẫn bịa hoặc không có trích dẫn sẽ bị loại và thay "
                        "bằng nguyên văn nguồn.")
    sb.slider("Temperature cho các câu còn lại", 0.0, 1.0, step=0.05, key="temperature",
              help="Cao hơn = diễn đạt tự nhiên, đa dạng hơn (hợp với viết nội dung). Câu nghiêm ngặt luôn dùng 0.")
    chosen_model = st.session_state.model_custom.strip() or st.session_state.model_choice
    if not temperature_supported(provider, chosen_model):
        sb.caption(f"ℹ️ `{chosen_model}` không cho chỉnh temperature: chế độ nghiêm ngặt vẫn được đảm bảo bằng "
                   "chỉ dẫn và bước kiểm tra trích dẫn; temperature của câu linh hoạt không có tác dụng.")

    # ---- retrieval
    sb.subheader("Tìm kiếm")
    sb.radio("Kiểu tìm kiếm", SEARCH_MODES, format_func=SEARCH_LABELS.get, key="search_mode")
    sb.slider("Top K đoạn tài liệu", 1, 15, key="top_k")
    sb.slider("Số review lấy làm bằng chứng", 1, 15, key="review_k")
    sb.toggle("Từ điển Việt → Anh", key="use_glossary",
              help="Thêm thuật ngữ tiếng Anh cho câu hỏi tiếng Việt (giúp câu không dấu, viết tắt).")
    sb.toggle("Rerank (cross-encoder)", key="rerank",
              help="Chính xác hơn và có điểm liên quan để chặn câu ngoài phạm vi, nhưng chậm hơn (~4-8 giây/câu trên CPU).")
    sb.slider("Số ứng viên đem rerank", 5, 50, key="rerank_candidates", disabled=not st.session_state.rerank)
    sb.slider("Prefetch mỗi truy vấn", 10, 100, step=10, key="prefetch_limit",
              help="Số kết quả mỗi truy vấn con (dense / BM25) lấy về trước khi gộp RRF.")

    # ---- scope
    sb.subheader("Phạm vi & độ tin cậy")
    sb.toggle("Dùng LLM để định tuyến", key="use_llm_router",
              help="Tắt = dùng luật từ khoá (nhanh, miễn phí, kém linh hoạt hơn).")
    sb.slider("Ngưỡng từ chối câu không liên quan", 0.0, 1.0, step=0.05, key="out_of_scope_gate",
              disabled=not st.session_state.rerank, help="Điểm rerank tối thiểu với câu không rõ chủ đề.")
    sb.slider("Ngưỡng 'không đủ thông tin'", 0.0, 1.0, step=0.05, key="no_info_gate",
              disabled=not st.session_state.rerank)

    if sb.button("↺ Khôi phục cài đặt mặc định (.env)", width="stretch"):
        for k in SETTING_KEYS:
            st.session_state.pop(k, None)
        st.rerun()


def current_settings():
    ss = st.session_state
    model = ss.model_custom.strip() or ss.model_choice
    return Settings(provider=ss.provider, model=model, api_key=ss.api_key.strip() or None, effort=ss.effort,
                    max_tool_rounds=ss.max_tool_rounds, top_k=ss.top_k, review_k=ss.review_k,
                    search_mode=ss.search_mode, use_glossary=ss.use_glossary, rerank=ss.rerank,
                    rerank_candidates=ss.rerank_candidates, prefetch_limit=ss.prefetch_limit,
                    out_of_scope_gate=ss.out_of_scope_gate, no_info_gate=ss.no_info_gate,
                    use_llm_router=ss.use_llm_router, history_turns=ss.history_turns,
                    strict_routes=list(ss.strict_routes), temperature=ss.temperature)


def changed_from_env(s):
    d, base = s.public(), Settings(provider=s.provider).public()
    return {k: v for k, v in d.items() if k != "api_key" and base.get(k) != v}


def render_details(res):
    r = res.get("route", {})
    secs = sum(res.get("timings_ms", {}).values()) / 1000
    mode = MODE_LABELS.get(res["mode"], res["mode"])
    model = res.get("llm_model") or res.get("settings", {}).get("model")
    st.caption(f"Loại câu hỏi: **{r.get('route')}** · router: {r.get('router')} · chế độ: {mode} · "
               f"độ tin cậy: {res.get('confidence')} · {secs:.1f}s" + (f" · {model}" if res["mode"].startswith("llm") else ""))
    if r.get("standalone_question") and r["standalone_question"] != res.get("question"):
        st.caption(f"↪ Hiểu theo ngữ cảnh hội thoại: _{r['standalone_question']}_")
    am = res.get("answer_mode")
    if am and res["mode"].startswith(("llm", "strict")):
        label = "🔒 nghiêm ngặt, chỉ theo nguồn" if am["mode"] == "strict" else "✍️ linh hoạt"
        temp = (f"temperature {am['temperature']:g}" if am.get("temperature_applied")
                else "model không hỗ trợ temperature")
        st.caption(f"Chế độ trả lời: {label} · {temp}")
    warnings = []
    if res.get("llm_note"):
        warnings.append(f"LLM không dùng được: {res['llm_note']}")
    if r.get("router_note") and "turned off" not in r["router_note"]:
        warnings.append(r["router_note"])
    if res.get("citations") and not res["citations"]["ok"]:
        warnings.append(f"Trích dẫn không có trong nguồn: {res['citations']['invalid']}")
    if res.get("claims_check") and res["claims_check"]["violations"]:
        warnings.append("Nội dung còn cụm cần duyệt/vi phạm: "
                        + ", ".join(f"\"{v['matched']}\" ({v['rule_id']} {v['severity']})"
                                    for v in res["claims_check"]["violations"]))
    for w in warnings:
        st.warning(w, icon="⚠️")

    if res.get("sources"):
        df = pd.DataFrame(res["sources"])
        if "relevance" in df and df["relevance"].isna().all():
            df = df.drop(columns="relevance")  # rerank off: no score to show
        with st.expander(f"Nguồn ({len(df)})"):
            st.dataframe(df, hide_index=True, width="stretch")


def main():
    init_state()
    sidebar()
    s = current_settings()
    key_source = "nhập trên giao diện" if s.api_key else ("trong .env" if _env_key(s.provider) else "chưa có")

    st.title("🍉 Company Brain")
    st.caption("Trợ lý kiến thức nội bộ Glow Recipe: sản phẩm dòng trái cây, review khách hàng, thương hiệu, "
               "quy định claim, chính sách, quy trình và kết quả test quảng cáo. Hỏi bằng tiếng Việt hoặc tiếng Anh.")
    diff = changed_from_env(s)
    st.info(f"**{PROVIDER_LABELS[s.provider]}** · model `{s.resolved_model()}` · API key: {key_source} · "
            f"tìm kiếm: {s.search_mode}, top {s.top_k}, rerank {'bật' if s.rerank else 'tắt'}"
            + (f" · đã chỉnh so với .env: {', '.join(diff)}" if diff else " · đang dùng mặc định từ .env"), icon="ℹ️")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("result"):
                render_details(msg["result"])

    if not st.session_state.messages:
        st.markdown("**Gợi ý câu hỏi:** Có được gọi kem chống nắng là chống nước không? · Khách phàn nàn gì về "
                    "SPF 50? · Dòng Watermelon có bao nhiêu sản phẩm? · Viết caption cho Dew Drops · "
                    "Khách bị rát da sau khi dùng toner thì CSKH làm gì?")

    question = st.chat_input("Nhập câu hỏi...")
    if question:
        cid = st.session_state.conversation_id
        if not cid or not store.conversation_exists(cid):
            cid = st.session_state.conversation_id = store.create_conversation(question)
        context = store.recent_turns(st.session_state.messages, s.history_turns)  # turns before this question
        st.session_state.messages.append({"role": "user", "content": question})
        store.add_message(cid, "user", question)
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Đang định tuyến, tìm kiếm và soạn câu trả lời..."):
                try:
                    res = answer(question, settings=s, history=context)
                except Exception as e:  # noqa: BLE001 - show the error in the chat instead of crashing the page
                    res = None
                    # kept in the session (not the saved history) so it is still shown after st.rerun() below
                    st.session_state.messages.append({"role": "assistant", "content":
                                                      f"⚠️ Lỗi: {type(e).__name__}: {e}. Bạn thử hỏi lại.", "error": True})
            if res:
                st.markdown(res["answer"])
                render_details(res)
                st.session_state.messages.append({"role": "assistant", "content": res["answer"], "result": res})
                store.add_message(cid, "assistant", res["answer"], res)
        st.rerun()  # refresh the conversation list in the sidebar


main()
