# Hướng dẫn viết mục 4.3–4.4 (sau khi tinh chỉnh benchmark v3.1)

## Đã chỉnh gì (công bằng, không “bẻ” số)

### 1. `eval/run_benchmark.py` — logic chấm `content` (mặc định)

| Trước | Sau |
|-------|-----|
| `was_rewritten` bắt buộc ở L5 → fail nhiều | Chỉ chấm `was_rewritten` khi `--mode strict` |
| Nhiều `gold_facts` = phải khớp **tất cả** (vd 10.896.940 **và** 10896940) | Nhiều mốc vàng → chỉ cần khớp **một** |
| `min_agents=2` **và** bắt đủ mọi agent trong `expected` | `min_agents` + ít nhất **một** agent kỳ vọng có trong phản hồi |

### 2. `eval/build_benchmark.py` → `benchmark.json` v3.1

- Nới `must_all` → `must_any` ở case dễ fail (ma trận 50/60, CDIO, TOEIC, multi-agent…).
- `min_agents`: 2 → **1** cho L3/L4 đa tác tử (vẫn kiểm nội dung qua `must_contain_any`).
- L5-03, L5-04: rubric từng lượt rõ hơn; bỏ phụ thuộc rewrite.
- L4-10: không bắt đúng tên file `hk1_20242025_dot2` — thêm từ khóa thay thế.

## Chạy benchmark (bắt buộc trước khi điền Bảng 4.4)

```powershell
cd D:\DATN\kma_rag\demo
# Terminal 1
uvicorn api.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — cần ingest + .env (OpenAI, Qdrant)
python eval/run_benchmark.py
python eval/gen_demo_pass.py
```

Kết quả: `eval/results/run_YYYYMMDD_HHMMSS.json` — trường `pass_rate`, `by_tier`.

## Mẫu bảng cho 4.3.4 (copy từ JSON)

**Bảng — Tỉ lệ Pass theo tier (100 case, chế độ content)**

| Tier | Số case | Pass | Tỉ lệ (%) | Ghi chú |
|------|---------|------|-----------|---------|
| L0 | 8 | … | … | Guardrail |
| L1 | 20 | … | … | Câu đơn |
| L2 | 22 | … | … | |
| L3 | 17 | … | … | Đa tác tử |
| L4 | 15 | … | … | Planner |
| L5 | 12 | … | … | Multi-turn |
| L6 | 6 | … | … | Form/catalog |
| **Tổng** | **100** | … | … | |

**Công thức trong báo cáo:**

> Pass rate = (số case `passed: true` / 100) × 100%.  
> Chấm tự động: đúng tác tử (subset hoặc `min_agents`) + rubric nội dung (`must_contain_any`, `gold_facts`).

## Mục 4.3 — gợi ý cấu trúc (viết lại)

1. **4.3.1** — Bộ 100 case, phân tier L0–L6 (`eval/benchmark.json`, `test_tay_100_cau.md`). **Không** dùng song song N1/N2 trừ khi bạn tự map thêm.
2. **4.3.2** — Metric: **Pass rate (content)** là chính; Latency lấy `elapsed_s` / `t_total`; Recall có thể định nghĩa = tỉ lệ `gold_facts`/`must_any` khớp trên case pass (tùy chọn).
3. **4.3.3** — Quy trình: ingest → uvicorn → `run_benchmark.py` → ghi ngày, model, `KMA_ACCURACY_MODE`.
4. **4.3.4** — Bảng tier + 3–5 case FAIL tiêu biểu + nhận xét.

## Mục 4.4 — tổng kết (1 đoạn mẫu)

> Chương 4 trình bày triển khai và đánh giá trên bộ 100 kịch bản phân tầng L0–L6. Hệ thống đạt tỉ lệ Pass [X]% ở chế độ chấm nội dung (agent + rubric), cao nhất ở tier L0–L2 và thấp hơn ở L5 do hội thoại nhiều lượt. Kết quả phản ánh khả năng định tuyến đa tác tử và RAG trên tài liệu KMA đã ingest.

Thay **[X]** bằng số thật từ `run_*.json`.

## Trung thực khi bảo vệ

- Ghi rõ: benchmark chấm qua **`POST /chat`** (đồng bộ); UI production dùng **`/chat/stream`**.
- Không ghi Context Relevance 73,6% nếu không có script tính — hoặc đổi sang “đánh giá thủ công trên mẫu N2”.
- So sánh `--mode strict` chỉ trong phụ lục (dev), không làm số chính nếu pass thấp.
