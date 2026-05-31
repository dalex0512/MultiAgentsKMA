# KMA Multi-Agent Chatbot

Chatbot đa tác tử hỗ trợ sinh viên Học viện Kỹ thuật Mật mã (KMA): tra cứu tài liệu đào tạo qua RAG + điều phối agent theo chủ đề.

## Chạy nhanh

```bash
pip install -r requirements.txt
cp .env.example .env   # điền OPENAI_API_KEY, QDRANT_URL, QDRANT_API_KEY
python ingest_all.py
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

- Trang sinh viên: `http://localhost:8000`
- Quản trị: `http://localhost:8000/admin/login`

## Luồng xử lý

```
Câu hỏi → Guardrail → Rewriter → Supervisor → Specialist (1–3 agent) → Aggregator
```

Trong mỗi specialist: ước lượng độ phức tạp (Qc) → chọn pipeline `native_rag` / `hybrid_rag` / `agentic_rag` → retrieve Qdrant theo `agent_id`.

## 7 agent chuyên môn

| `agent_id` | Thư mục `docs/` | Nội dung |
|---|---|---|
| `tuyen_sinh` | `tuyen_sinh_va_chuong_trinh_dao_tao/` | Tuyển sinh, CTĐT |
| `khao_thi` | `khao_thi_quy_che/` | Quy chế, chuẩn đầu ra |
| `ma_tran` | `ma_tran_de_thi/` | Ma trận đề thi |
| `diem_thi` | `diem_thi/` | Bảng điểm (MSSV) |
| `bieu_mau` | `bieu_mau/` | Biểu mẫu, thủ tục |
| `danh_sach_thi` | `danh_sach_thi/` | Danh sách dự thi (MSSV/SBD, ca, phòng) |
| `lich_thi` | `lich_thi/` | Lịch thi KTHP (môn, giờ, địa điểm) |

## Tính năng cổng

- **Hỏi đáp trực tuyến** — chat widget, hỗ trợ hội thoại nhiều lượt
- **Bảng điểm / Lịch học** — tiện ích client-side
- **Tin mới** — admin upload PDF, sinh viên xem trên trang chủ

## API chính

| Endpoint | Mô tả |
|---|---|
| `POST /chat` | Hỏi đáp (JSON) |
| `POST /chat/stream` | Hỏi đáp (SSE) |
| `POST /session/new` | Tạo phiên chat mới |
| `GET /news` | Danh sách tin mới (public) |
| `GET /agents` | Danh sách agent |

Admin: upload tài liệu, tin mới, thống kê, benchmark — qua `/admin/*`.

## Cấu trúc code

```
demo/
├── agents/          # supervisor, planner, router, guardrail…
├── pipelines/       # multi_agent_system, retrieval, RAG
├── utils/rag/       # schedule_lookup, exam_list_lookup…
├── admin_auth/      # đăng nhập admin, upload, analytics
├── docs/            # corpus PDF theo domain
├── api/main.py      # FastAPI
├── static/          # giao diện sinh viên + admin
└── ingest_all.py    # nạp Qdrant
```

## Công nghệ

FastAPI · OpenAI (GPT-4o-mini + embedding) · Qdrant · PostgreSQL · Redis (session, tùy chọn)

## Test

```bash
python test_agent_schedule_exam_routing.py
```

Benchmark: [eval/benchmark.md](eval/benchmark.md)
