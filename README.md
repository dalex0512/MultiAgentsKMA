# Trợ lý ảo Học viện KMA

Chatbot đa tác tử hỗ trợ sinh viên **Học viện Kỹ thuật Mật mã (KMA)** tra cứu tài liệu đào tạo: tuyển sinh, quy chế thi, ma trận đề, bảng điểm, biểu mẫu, danh sách thi và lịch thi. Hệ thống dùng RAG (Qdrant + embedding) và điều phối **7 agent chuyên môn** theo nội dung câu hỏi.

## Yêu cầu

- Python 3.10+
- Tài khoản OpenAI (API key cho LLM và embedding)
- Qdrant (cloud hoặc local)
- PostgreSQL (quản trị, tin mới — nếu dùng trang admin)

## Cài đặt và chạy

```bash
# 1. Cài thư viện
pip install -r requirements.txt

# 2. Cấu hình môi trường
cp .env.example .env
# Sửa .env: OPENAI_API_KEY, QDRANT_URL, QDRANT_API_KEY (và DB nếu dùng admin)

# 3. Nạp tài liệu PDF trong docs/ vào Qdrant (7 agent)
python ingest_all.py

# 4. Chạy server
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Trên Windows, bước 2 có thể copy thủ công: `copy .env.example .env`.

## Truy cập

| Trang | URL |
|-------|-----|
| Giao diện sinh viên (hỏi đáp) | http://localhost:8000 |
| Quản trị | http://localhost:8000/admin/login |

## Ingest lại một agent (tùy chọn)

```bash
python ingest_all.py --domain diem_thi
```

Các domain: `tuyen_sinh`, `khao_thi`, `ma_tran`, `diem_thi`, `bieu_mau`, `danh_sach_thi`, `lich_thi`.

Tài liệu nguồn nằm trong thư mục `docs/`, mỗi agent tương ứng một subfolder (ví dụ `docs/diem_thi/`).
