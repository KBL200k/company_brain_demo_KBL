# Kết quả đánh giá

Các lần chạy được giữ lại là những lần có số liệu được dẫn trong README chính. Mỗi lần chạy có file `.md` (bảng tóm tắt + câu trượt) và `.json` (chi tiết từng câu).

| File | Bộ câu hỏi | Nội dung | Số liệu dẫn trong README |
|---|---|---|---|
| `retrieval_20261006-1435` | Dev (`retrieval_eval.jsonl`, 30 câu × 3 biến thể) | So sánh 4 model embedding × 3 cấu hình (dense, hybrid, hybrid + từ điển) | Tiếng Việt hit@5 từ 0.27 (bge-small) lên 0.90 (e5-large + hybrid + từ điển) |
| `retrieval_20261006-1655` | Dev | Có và không có rerank (30 ứng viên) | Rerank: EN 1.00, VI 1.00, không dấu 0.97, ~9 giây/câu |
| `retrieval_20261006-1705` | Dev | Rerank 15 ứng viên | EN 1.00, VI 0.97, không dấu 0.93, ~4,3 giây/câu |
| `val_20261007-0958` (+ `.xlsx`) | Held-out (`val_kb`, `val_reviews`, `val_negative`) | Search không rerank: tài liệu, review có bộ lọc, câu ngoài phạm vi | hit@5 EN 0.96 / VI 0.83 / không dấu 0.64; cosine chỉ loại 38% câu ngoài phạm vi |
| `val_20261006-1725-rerank` | Held-out | Search có rerank 15 ứng viên | Điểm rerank loại 79% câu ngoài phạm vi, vẫn giữ 100% câu hợp lệ |
| `routing_rules_20261007-1458` | `routing_eval.jsonl` (44 câu) | Router theo luật + quyết định trả lời/từ chối đầu-cuối | 44/44 (luật được chỉnh trên chính bộ này, nên lạc quan) |

Chạy lại:
```bash
python scripts/eval_retrieval.py --configs hybrid+glossary,hybrid+glossary+rerank15
python scripts/eval_search_val.py            # thêm --rerank để có phần điểm rerank
python scripts/eval_routing.py               # thêm --provider claude|openai|gemini để đo router LLM
python scripts/export_val_xlsx.py            # xuất lần validation mới nhất ra Excel
```
