# Company Brain: trợ lý kiến thức nội bộ cho một thương hiệu skincare DTC

Bài AI Demo Challenge, **Option 2**. Trợ lý trả lời câu hỏi của team marketing, creative và chăm sóc khách hàng của **Glow Recipe** (các dòng skincare trái cây). Trợ lý:
- trích dẫn nguồn cho câu trả lời,
- tuân thủ luật claims quảng cáo của thương hiệu,
- từ chối câu hỏi không liên quan,
- nói rõ khi kho kiến thức không có câu trả lời,
- viết được nội dung đúng quy định: creative brief, caption, trả lời review,
- nhớ hội thoại: hiểu câu hỏi nối tiếp ("còn bản mini thì sao?") và lưu lại các cuộc trò chuyện để mở lại sau.

Có ba cách dùng: giao diện chat trên web (Streamlit), dòng lệnh (CLI) và **MCP server**. Chọn được nhà cung cấp LLM: **Claude, GPT hoặc Gemini**.

---

## 1. Kiến trúc hệ thống

```
                 ┌──────────── câu hỏi (tiếng Việt hoặc tiếng Anh, có dấu hay không dấu) ────────┐
                 ▼                                                                                 │
   ① Router: LLM trả JSON theo schema (dự phòng: luật từ khoá Anh/Việt), có xem vài lượt trước    │
      → loại câu hỏi, có trong phạm vi không, câu hỏi viết lại cho đủ ngữ cảnh, ngôn ngữ,          │
        câu viết lại bằng tiếng Anh, mã sản phẩm, bộ lọc rating                                    │
      ├─ ngoài phạm vi → từ chối lịch sự (không search, không gọi LLM)                             │
      ├─ chào hỏi      → giới thiệu những gì trợ lý làm được                                       │
      ▼                                                                                            │
   ② Lấy dữ liệu theo loại câu hỏi (qua các tool)                                                 │
      product_catalog  → lookup_products (tra bảng chính xác) + search(sản phẩm, catalog)          │
      customer_insight → search(báo cáo insight) + search_reviews (lọc theo sản phẩm, rating)      │
      compliance       → search(luật claims, FDA/FTC, SOP) + check_claims trên câu hỏi             │
      generation       → sản phẩm + insight + review + luật claims và voice guide (luôn nạp)       │
      … sop_policy / creative / brand / review_evidence                                            │
      ▼                                                                                            │
   ③ Cổng liên quan: điểm rerank quá thấp → từ chối (chủ đề lạ) hoặc "không đủ thông tin"         │
      ▼                                                                                            │
   ④ LLM trả lời chỉ dựa trên nguồn, trích dẫn [chunk_id], có thể gọi tool để tra thêm            │
      ▼                                                                                            │
   ⑤ Hậu kiểm: mọi trích dẫn phải có trong nguồn; nội dung viết ra được kiểm tra lại với          │
      luật claims và tự viết lại một lần nếu vi phạm luật mức BLOCK ──────────────────────────────┘
```

**Phần tìm kiếm (Qdrant):** mỗi câu hỏi chạy nhiều truy vấn con trong một lần gọi, rồi gộp kết quả bằng Reciprocal Rank Fusion (RRF):
- vector dense của `multilingual-e5-large`, hiểu cả tiếng Việt lẫn tiếng Anh
- BM25 trên câu hỏi gốc
- BM25 trên các thuật ngữ tiếng Anh lấy từ từ điển Việt→Anh
- tra chính xác mã luật và mã test (`CP-05`, `CT-03`)

Sau đó một cross-encoder đa ngôn ngữ (`jina-reranker-v2-base-multilingual`) chấm lại 15 ứng viên đầu.

| Lớp | File |
|---|---|
| Pipeline dữ liệu (dữ liệu thật → tài liệu → chunk → index) | `scripts/prepare_data.py`, `build_insights.py`, `build_catalog.py`, `build_manifest.py`, `build_chunks.py`, `build_index.py` |
| Tìm kiếm, tool, router, pipeline RAG | `app/retrieval.py`, `app/glossary.py`, `app/tools.py`, `app/router.py`, `app/rag.py` |
| Adapter LLM (Claude / OpenAI / Gemini) | `app/llm.py`; tham số chạy trong `app/settings.py` |
| Lịch sử hội thoại (SQLite, `data/history/chat.db`) | `app/history.py` |
| Giao diện | `ui.py` (web), `cli.py`, `mcp_server.py` (8 tool: `ask`, `route_question`, `search_knowledge`, `search_reviews`, `lookup_products`, `get_document`, `check_claims`, `list_providers`) |
| Đánh giá | `data/eval/` + `scripts/eval_*.py` |

**Kho kiến thức** (`data/kb/`, chi tiết trong `data/kb/README.md`):

| Nội dung | Số lượng | Nguồn |
|---|---|---|
| Sản phẩm: giá, dung tích, thành phần, hoạt chất, bản mini | 25 listing (19 sản phẩm + 6 bản mini) | **thật** (bộ dữ liệu Sephora trên Kaggle) |
| Review khách hàng | 25.211 review (2018 đến 03/2023) | **thật** |
| Báo cáo insight (chủ đề khen/chê, loại da, xu hướng) và tổng quan catalog | 27 tài liệu | **tính từ** dữ liệu thật |
| Luật FDA/FTC/MoCRA, chính sách đổi trả và giao hàng, định vị thương hiệu | 9 tài liệu | **thật** (nguồn công khai, có link) |
| Luật claims nội bộ, voice guide, 4 SOP, nhật ký test quảng cáo, mẫu brief | 8 tài liệu | **giả lập**, có ghi rõ |

---

## 2. Các quyết định thiết kế chính

1. **Ưu tiên dữ liệu thật; chỉ giả lập phần không có nguồn công khai.**
   - SOP, voice guide và kết quả test quảng cáo là tài liệu nội bộ, không bao giờ được công bố, nên được viết riêng cho demo.
   - Mỗi tài liệu giả lập có banner và `source_type: synthetic` trong metadata. Trợ lý trình bày chúng như chính sách nội bộ, không như sự thật công khai.
   - Một số khoảng trống dữ liệu được giữ lại có chủ đích để kiểm tra khả năng trả lời "không đủ thông tin": không có kết quả test chống nước, không có nồng độ AHA, dữ liệu dừng ở 03/2023.
2. **Cắt chunk theo cấu trúc tài liệu, không theo độ dài.**
   - Mỗi mục, mỗi luật claims, mỗi bài test là một chunk. Mỗi chunk có tên tài liệu và tên mục ở đầu để tự đứng được. Bảng được viết lại thành câu văn trước khi embed.
   - Chỉ những mục dài hơn 500 token mới bị cắt, và chỉ các phần bị cắt mới có overlap khoảng 80 token.
   - Có thêm một tài liệu **catalog overview** tạo tự động, chứa sẵn các con số tổng và danh sách, vì RAG không tự cộng được thông tin nằm rải rác ở 25 file sản phẩm.
3. **Số lượng, giá và danh sách sản phẩm lấy từ tool tra bảng (`lookup_products`), không lấy từ đoạn văn.** LLM được yêu cầu dùng tool này cho mọi con số.
4. **Cấu hình tìm kiếm được chọn bằng đo đạc, không theo mặc định.**
   - So sánh 4 model embedding trên một bộ dev song ngữ. Kết quả cuối được báo cáo trên một **bộ held-out riêng**, không dùng để tinh chỉnh.
   - Ví dụ: hit@5 với tiếng Việt tăng từ 0.27 (model embedding chỉ hiểu tiếng Anh) lên 0.90 trên bộ dev, và đạt 0.83 trên bộ held-out.
5. **Rerank được dùng chủ yếu để quyết định câu hỏi có trong phạm vi hay không.**
   - Điểm cosine thô không tách được câu không liên quan khỏi câu hợp lệ: ở ngưỡng giữ được 100% câu hợp lệ, nó chỉ loại được 38% câu không liên quan. Điểm của cross-encoder loại được 79%.
   - Việc chặn câu ngoài phạm vi có 3 lớp: router, cổng theo điểm rerank, và LLM được yêu cầu chỉ trả lời từ nguồn.
6. **Compliance được kiểm tra bằng code, không chỉ dựa vào prompt.**
   - Với yêu cầu viết nội dung, luật claims và voice guide luôn được đưa vào ngữ cảnh.
   - Nội dung viết ra đi qua bước kiểm tra bằng regex với danh sách cụm từ cấm (`check_claims`). Nếu vi phạm luật mức BLOCK thì LLM tự viết lại một lần.
   - Mọi `[trích dẫn]` được đối chiếu với các nguồn đã thực sự đưa cho LLM.
7. **Hai chế độ trả lời theo mức độ rủi ro của câu hỏi.**
   - **Nghiêm ngặt** (mặc định cho quy trình/chính sách, compliance, thông tin sản phẩm): temperature = 0; chỉ dẫn yêu cầu chỉ nêu điều có trong nguồn và câu nào cũng có trích dẫn. Câu trả lời có trích dẫn không tồn tại, hoặc không có trích dẫn mà cũng không nói "không đủ thông tin", **bị loại bằng code** và thay bằng nguyên văn nguồn.
   - **Linh hoạt** (các loại còn lại, ví dụ viết nội dung, creative): temperature 0.5 để diễn đạt tự nhiên hơn, sự thật vẫn phải có nguồn.
   - Danh sách loại câu nghiêm ngặt và temperature chỉnh được trên giao diện hoặc trong `.env`. Một số model không cho chỉnh temperature (Claude Opus 5 / Sonnet 5, GPT-5 / o-series); với các model này, chế độ nghiêm ngặt vẫn được bảo đảm bằng chỉ dẫn và bước kiểm tra, và giao diện ghi rõ điều đó.
8. **Một lớp tool dùng chung cho ba nơi:** pipeline RAG, các lần LLM gọi tool, và MCP server đều dùng cùng một bộ hàm Python.
9. **Không phụ thuộc nhà cung cấp LLM, và vẫn chạy khi thiếu LLM.**
   - Claude, GPT và Gemini dùng chung một giao diện adapter, mỗi adapter dùng SDK chính thức của nhà cung cấp.
   - Không có API key thì hệ thống vẫn định tuyến bằng luật từ khoá và trả lời bằng các đoạn liên quan nhất, nên vẫn kiểm tra và demo phần tìm kiếm được khi offline.
   - Với Claude Opus 5, cơ chế fallback phía server được bật sẵn (đặt `CLAUDE_FALLBACKS=off` để tắt).
10. **Hội thoại nhiều lượt nhưng sự thật vẫn lấy từ nguồn.**
   - Câu hỏi nối tiếp được viết lại thành câu đầy đủ trước khi search: LLM router làm việc này khi có LLM, còn luật nhận diện câu nối tiếp mang theo sản phẩm của lượt trước khi không có LLM. Chuỗi câu nối tiếp luôn bám vào câu hỏi gốc.
   - LLM được xem vài lượt gần nhất để hiểu ý, nhưng được yêu cầu không lấy sự thật từ câu trả lời cũ, chỉ từ nguồn của lượt hiện tại.
   - Lịch sử lưu trong SQLite có sẵn của Python (không cần cài thêm). Mỗi câu trả lời lưu kèm route, nguồn và thời gian để mở lại xem. API key không bao giờ được lưu.
11. **Chạy cục bộ là chính.** Qdrant, các model và giao diện đều chạy trên một máy và chỉ nghe trên `127.0.0.1`. API key nhập trên giao diện chỉ tồn tại trong phiên trình duyệt.

---

## 3. Cách chạy bản demo

Yêu cầu: **Python 3.11 hoặc 3.12**, khoảng 8GB RAM, khoảng 7GB ổ đĩa. Lần chạy đầu cần internet để tải thư viện, Qdrant và model. **Không cần GPU.**

```bash
# 1. môi trường
python -m venv .venv
.venv\Scripts\activate                     # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                     # Linux/macOS: cp ...  (API key không bắt buộc, nhập trên giao diện cũng được)

# 2. vector database: Qdrant v1.19.2 đúng hệ điều hành + dashboard
python scripts/setup_qdrant.py
qdrant_server\start_qdrant.bat             # Linux/macOS: ./qdrant_server/start_qdrant.sh
#    -> MỞ TERMINAL RIÊNG và để cửa sổ này chạy suốt. Kiểm tra: http://127.0.0.1:6333/dashboard
#    -> Các bước sau chạy ở terminal khác (nhớ activate .venv)

# 3. nạp index vào Qdrant — chọn MỘT trong hai cách
# 3a. Build từ chunk có sẵn trong repo (data/index/*.jsonl) — mặc định khi vừa clone
python scripts/build_index.py              # cả kb + reviews, ~1 giờ trên CPU (lần đầu tự tải model embedding)
python scripts/build_index.py --kb-only    # chỉ tài liệu nội bộ, nhanh hơn nhiều; demo được trừ câu hỏi về review
# 3b. Có snapshot từ máy khác (~1 phút) — data/snapshots/ KHÔNG nằm trong git
#     máy nguồn:  python scripts/qdrant_snapshot.py export   rồi copy data/snapshots/ sang máy này
python scripts/qdrant_snapshot.py import

# 4. model (~3,5GB, không bắt buộc; nếu bỏ qua sẽ tự tải ở câu hỏi đầu tiên)
python scripts/download_models.py

# 5. chạy
streamlit run ui.py                        # http://127.0.0.1:8501
python cli.py "Có được gọi kem chống nắng là chống nước không?"
python cli.py --provider gemini "Viết caption cho Dew Drops"
```

**Lỗi thường gặp khi cài:**

| Thông báo | Nguyên nhân | Cách xử lý |
|---|---|---|
| `Qdrant is not reachable at http://127.0.0.1:6333` | Qdrant chưa chạy | Chạy `start_qdrant.bat` ở terminal riêng, đợi dòng `listening on 6333` |
| `qdrant.exe was blocked by your organization's Device Guard policy` | **Smart App Control** của Windows 11 chặn exe chưa ký số (`qdrant.exe` không có chữ ký) | Tắt Smart App Control (Windows Security → App & browser control), **hoặc** chạy Qdrant bằng Docker: `docker run -d --name qdrant -p 127.0.0.1:6333:6333 -p 127.0.0.1:6334:6334 -v "${PWD}\qdrant_server\storage:/qdrant/storage" qdrant/qdrant:v1.19.2`, **hoặc** chạy bản Linux trong WSL |
| `missing ...\data\snapshots\kb.snapshot.gz` | Snapshot không nằm trong git | Dùng bước 3a (`build_index.py`), hoặc copy `data/snapshots/` từ máy đã `export` |

**Giao diện web:** chọn nhà cung cấp (Claude, GPT hoặc Gemini), dán API key, rồi bấm **"Tải danh sách model từ API"** để xem các model mà key đó dùng được.
- Đầu sidebar là khu **Hội thoại**: tạo cuộc trò chuyện mới, mở lại hoặc xoá các cuộc trò chuyện đã lưu.
- Sidebar cho chỉnh: kiểu tìm kiếm (hybrid, dense hoặc BM25), top-k, từ điển, rerank và số ứng viên, kiểu router, ngưỡng phạm vi, effort, số lượt hội thoại nhớ, chế độ trả lời (loại câu nghiêm ngặt và temperature).
- Tham số nào không chỉnh sẽ lấy theo `.env`.
- **Lưu ý:** API key, model và các tham số chỉnh trên sidebar chỉ lưu trong phiên trình duyệt. **Khi tải lại trang (F5) hoặc mở tab mới, phải nhập lại API key và chọn lại model**, các tham số khác quay về giá trị trong `.env`. Muốn không phải nhập lại mỗi lần, hãy điền key và model vào `.env`. Các cuộc trò chuyện đã lưu thì không mất, mở lại được ở khu **Hội thoại**.
- Mỗi câu trả lời hiển thị loại câu hỏi, nguồn, thời gian và các cảnh báo hậu kiểm.

**MCP:** file `.mcp.json` đã đăng ký `mcp_server.py` cho Claude Code. Với Claude Desktop, thêm cùng lệnh đó (dùng đường dẫn tuyệt đối) vào `claude_desktop_config.json`. Tool `ask` nhận `conversation_id` (truyền `"new"` để bắt đầu) để tiếp tục một cuộc trò chuyện đã lưu.

**CLI ở chế độ hỏi đáp liên tục** (`python cli.py`) nhớ các lượt trong phiên; gõ `new` để bắt đầu lại.

**Kiểm tra cài đặt và tái tạo số liệu:**
```bash
python scripts/search_demo.py                # kết quả đúng: 7/7
python scripts/eval_search_val.py [--rerank] # đánh giá tìm kiếm trên bộ held-out
python scripts/eval_routing.py [--provider claude|openai|gemini]
python scripts/test_mcp_client.py            # thử MCP server qua stdio
```

Câu hỏi nên thử: *"Có được gọi kem chống nắng là chống nước không?"* · *"Khách phàn nàn gì về kem chống nắng SPF 50?"* · *"Dòng Watermelon có bao nhiêu sản phẩm?"* · *"Khách bị rát da sau khi dùng toner thì CSKH làm gì?"* · *"Viết creative brief cho serum Guava"* · *"Thời tiết Hà Nội ngày mai?"* (bị từ chối)

---

## 4. Hướng cải thiện tiếp theo

- **Cải thiện chunking và lựa chọn model embedding để tìm đúng kết quả hơn.**
  - **Semantic chunking cho dữ liệu tiếng Việt:** tách câu bằng công cụ hiểu tiếng Việt (ví dụ `underthesea`, `pyvi`), embed từng câu rồi chỉ cắt chunk ở chỗ ý nghĩa giữa hai câu liền kề thay đổi rõ. Như vậy chunk không bị cắt giữa câu hay giữa một ý, nhất là với các mục dài hiện đang bị cắt theo số token.
  - Thử thêm các cách cắt chunk khác: parent–child (tìm trên chunk nhỏ, đưa chunk cha cho LLM), thêm đoạn tóm tắt ngữ cảnh vào đầu mỗi chunk; so sánh kích thước chunk và overlap bằng số đo thay vì chọn cố định.
  - So sánh thêm các model embedding đa ngôn ngữ mới (ví dụ `bge-m3`, các bản e5 có instruction) và cân nhắc fine-tune trên cặp câu hỏi–tài liệu của chính lĩnh vực skincare.
  - Xử lý riêng tiếng Việt không dấu và kiểu chat: khôi phục dấu hoặc chuẩn hoá câu hỏi trước khi search, mở rộng từ điển Việt→Anh.
  - Thử các reranker khác và tinh chỉnh số ứng viên, trọng số RRF giữa dense và BM25.
- **Đưa LangGraph vào để quản lý luồng xử lý, lịch sử hội thoại và memory.**
  - Mô hình hoá pipeline hiện tại (router → lấy dữ liệu → cổng liên quan → trả lời → hậu kiểm) thành một graph có trạng thái rõ ràng, dễ thêm nhánh, vòng lặp tự sửa và điểm dừng chờ người duyệt.
  - Dùng checkpointer để lưu và khôi phục hội thoại, tách lịch sử theo từng người dùng và từng cuộc trò chuyện.
  - Thêm memory dài hạn (sở thích, sản phẩm hay hỏi, vai trò của người dùng) và tóm tắt các hội thoại dài thay vì chỉ giữ vài lượt gần nhất.
  - Gọi tool chính xác hơn: kiểm tra tham số, thử lại khi tool lỗi, giới hạn số bước và ghi lại vết từng lần gọi tool.
- **Xây dựng bộ câu hỏi test để đo phân luồng và chất lượng tìm kiếm.**
  - Bộ test routing lớn hơn và **tách hẳn khỏi dữ liệu dùng để chỉnh luật**, có đủ tiếng Việt có dấu, không dấu, tiếng Anh, kiểu chat, câu nối tiếp nhiều lượt và câu gần chủ đề nhưng ngoài phạm vi.
  - Bộ test tìm kiếm có nhãn tài liệu đúng cho từng câu, đo hit@k, MRR, nDCG theo từng loại câu hỏi và từng ngôn ngữ.
  - Bộ test câu trả lời: trích dẫn có đúng nguồn không, có bịa thông tin không, có từ chối/nói "không đủ thông tin" đúng lúc không, nội dung viết ra có vi phạm luật claims không (có thể dùng LLM làm giám khảo kết hợp kiểm tra bằng code).
  - Chạy tự động các bộ test này mỗi khi đổi model, prompt hoặc cấu hình để phát hiện suy giảm.
- **Chạy thử và đánh giá với LLM thật** của cả ba nhà cung cấp, so sánh chất lượng, độ trễ và chi phí để chọn model mặc định cho từng loại câu hỏi.
- **Tăng tốc độ phản hồi.**
  - Chạy rerank và embedding bằng ONNX/quantize hoặc GPU, cache kết quả cho các câu hỏi lặp lại.
  - Stream câu trả lời lên giao diện để người dùng không phải chờ.
- **Nâng cấp kiểm tra compliance.** Bổ sung bộ phân loại bằng LLM bên cạnh regex để bắt các claim vi phạm được diễn đạt khác đi, và cho người duyệt xác nhận trước khi xuất nội dung quảng cáo.
- **Cập nhật và mở rộng dữ liệu.**
  - Đồng bộ tự động kho kiến thức với nguồn dữ liệu, chỉ index lại phần thay đổi.
  - Bổ sung review mới hơn 03/2023 và các sản phẩm còn thiếu; nhận diện chủ đề review bằng model thay vì từ khoá.
- **Hướng tới production.**
  - Đăng nhập và phân quyền theo vai trò (marketing, creative, CSKH), lưu lịch sử theo người dùng.
  - Giám sát và tracing (ví dụ LangSmith hoặc Langfuse), thu thập phản hồi 👍/👎 từ người dùng để bổ sung vào bộ test.
  - Đóng gói bằng Docker để triển khai dễ dàng trên server.
