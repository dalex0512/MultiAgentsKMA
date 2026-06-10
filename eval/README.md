# 100 câu test tay — KMA Chatbot

## File dùng khi demo / bảo vệ

| File | Dùng để |
|------|---------|
| **`test_tay_100_cau.md`** | **Mở file này** — copy câu hỏi, so sánh câu trả lời đúng |
| `benchmark.json` | Nguồn máy đọc (100 case, **v3.1** — rubric đã tinh chỉnh cho 4.3–4.4) |
| `HUONG_DAN_4_3_4_4.md` | Cách viết mục 4.3–4.4 + bảng mẫu từ `run_*.json` |
| `build_benchmark.py` | Sửa case → `python eval/build_benchmark.py` |
| `run_benchmark.py` | Chấm tự động qua API (tùy chọn) |
| `benchmark.md` | Chi tiết kỹ thuật routing (tham khảo) |

## Test trực tiếp trên web (cách chính)

1. `uvicorn api.main:app --host 127.0.0.1 --port 8000`
2. Mở http://127.0.0.1:8000
3. Mở **`eval/test_tay_100_cau.md`**
4. Copy từng câu (khối ` ```text ` ) → dán chat
5. Đối chiếu với mục **Câu trả lời đúng cần có**

**L5 (multi-turn):** gửi lượt 1 → đợi trả lời → lượt 2 **cùng tab**, không F5.

## Chấm tự động (tùy chọn)

Mặc định chỉ kiểm **agent + nội dung** (khớp mục tiêu test tay):

```bash
python eval/run_benchmark.py
python eval/run_benchmark.py --tier L2
python eval/run_benchmark.py --id L2-11
python eval/run_benchmark.py --ids-file eval/failed_retest_ids.txt
python eval/gen_demo_pass.py
python eval/merge_benchmark_runs.py eval/results/run_BASE.json eval/results/run_PATCH.json
python eval/rescore_results.py eval/results/merged_run_20260523_143737.json
```

`gen_demo_pass.md` → tạo **`demo_pass.md`** (chỉ câu pass + câu trả lời mẫu từ lần chạy gần nhất).

Chấm strict (thêm pipeline, Qc — cho dev):

```bash
python eval/run_benchmark.py --mode strict
```

## Phân bổ 100 câu

| Tier | Ý nghĩa | Số |
|------|---------|-----|
| L0 | Chào / off-topic | 8 |
| L1 | Một mảng, câu đơn | 20 |
| L2 | Liệt kê, so sánh, MSSV | 22 |
| L3 | Hai mảng trở lên | 17 |
| L4 | Câu dài / planner | 15 |
| L5 | Nhiều lượt chat | 12 |
| L6 | Biểu mẫu / form | 6 |

Cần `python ingest_all.py` + Qdrant trước khi test câu RAG.
