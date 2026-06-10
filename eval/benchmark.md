# Benchmark v2 — KMA Multi-Agent (Supervisor + Router)

**Phiên bản:** 3.1  
**Tổng case:** 100  
**API:** `POST /chat`  

100 câu test trực tiếp trên http://127.0.0.1:8000 — copy câu hỏi, so sánh câu trả lời chatbot với mục «Câu trả lời đúng cần có». Gold facts trích từ docs/. Cần ingest_all.py + Qdrant trước khi test.

## Ngưỡng Router (Qc cục bộ, `KMA_ACCURACY_MODE=1`)

| Qc | Pipeline |
|----|----------|
| Qc < 0.50 | `native_rag` |
| 0.50 ≤ Qc < 0.70 | `hybrid_rag` |
| Qc ≥ 0.70 | `agentic_rag` |

## Phân bổ tier

| Tier | Mô tả | Số case |
|------|--------|---------|
| L0 | Guardrail — không vào RAG | 8 |
| L1 | Đơn giản — 1 agent, native/hybrid, supervisor | 20 |
| L2 | Trung bình — hybrid/agentic/grade_lookup | 22 |
| L3 | Multi-agent — supervisor multi_domain | 17 |
| L4 | Phức tạp — planner + agentic/multi | 15 |
| L5 | Multi-turn — memory & rewrite | 12 |
| L6 | Biểu mẫu — catalog & form_fill | 6 |

## Cách chạy

```bash
python eval/build_benchmark.py
uvicorn api.main:app --host 127.0.0.1 --port 8000
python ingest_all.py   # nếu đổi docs
python eval/run_benchmark.py
python eval/run_benchmark.py --tier L1
python eval/run_benchmark.py --id L2-11
```

Môi trường: `KMA_FAST_MODE=0`, `KMA_ACCURACY_MODE=1`, Qdrant đã ingest.

---

## L0 — Guardrail

### L0-01 — Chào hỏi
**Câu hỏi:** Xin chào!
**Agents:** `(không)` | primary=``
**Pipeline ∈** `['guardrail']`
**Phải có (một):** KMA, trợ lý

### L0-02 — Cảm ơn
**Câu hỏi:** Cảm ơn bạn nhé!
**Agents:** `(không)` | primary=``
**Pipeline ∈** `['guardrail']`

### L0-03 — Off-topic thời tiết
**Câu hỏi:** Thời tiết Hà Nội ngày mai thế nào?
**Agents:** `(không)` | primary=``
**Pipeline ∈** `['guardrail']`
**Phải có (một):** ngoài phạm vi, KMA

### L0-04 — Off-topic lập trình
**Câu hỏi:** Viết code Python sắp xếp danh sách như thế nào?
**Agents:** `(không)` | primary=``
**Pipeline ∈** `['guardrail']`

### L0-05 — Trường khác
**Câu hỏi:** Điểm chuẩn Đại học Bách Khoa Hà Nội năm 2025?
**Agents:** `(không)` | primary=``
**Pipeline ∈** `['guardrail']`
**Phải có (một):** ngoài phạm vi

### L0-06 — Giới thiệu khả năng
**Câu hỏi:** Bạn có thể giúp gì cho sinh viên KMA?
**Agents:** `(không)` | primary=``
**Pipeline ∈** `['guardrail']`
**Phải có (một):** tuyển sinh, biểu mẫu, quy chế, ma trận, điểm

## L1 — Đơn giản — Supervisor 1 agent + native/hybrid

### L1-01 — Mã trường KMA
**Câu hỏi:** Mã trường của Học viện Kỹ thuật Mật mã trong đề án tuyển sinh 2025 là gì?
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Supervisor intent:** `single_domain`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Gold:** KMA

### L1-02 — Website tuyển sinh
**Câu hỏi:** Trang web tuyển sinh chính thức của KMA là gì?
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Supervisor intent:** `single_domain`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** tuyensinh.actvn.edu.vn, actvn

### L1-03 — Khối tín chỉ cử nhân
**Câu hỏi:** Khối lượng học tập tối thiểu chương trình cử nhân theo quy chế đào tạo KMA 2025 là bao nhiêu tín chỉ?
**Agents:** `khao_thi` | primary=`khao_thi`
**Supervisor intent:** `single_domain`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Gold:** 120

### L1-04 — TOEIC Tiếng Anh 1
**Câu hỏi:** Sinh viên cần đạt tối thiểu bao nhiêu điểm TOEIC khi kết thúc học phần Tiếng Anh 1 theo quy định chuẩn ngoại ngữ KMA?
**Agents:** `khao_thi` | primary=`khao_thi`
**Supervisor intent:** `single_domain`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Gold:** 300

### L1-05 — Ma trận THĐC — số câu
**Câu hỏi:** Môn Tin học đại cương: tổng số câu trắc nghiệm và thời gian làm bài theo ma trận đề thi KMA?
**Agents:** `ma_tran` | primary=`ma_tran`
**Supervisor intent:** `single_domain`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** 50, 60, phút

### L1-06 — Ma trận Toán A3 — khoa
**Câu hỏi:** Môn Toán cao cấp A3 thuộc khoa nào theo ma trận đề thi?
**Agents:** `ma_tran` | primary=`ma_tran`
**Supervisor intent:** `single_domain`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** Cơ bản

### L1-07 — Đơn phúc khảo
**Câu hỏi:** KMA có mẫu đơn xin phúc khảo bài thi không? Tên file trong catalog?
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Supervisor intent:** `form_procedure`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** phúc khảo, 15-Don_phuc_khao

### L1-08 — Đơn nghỉ dưới 7 ngày
**Câu hỏi:** Sinh viên xin nghỉ học tạm thời dưới 7 ngày dùng đơn nào?
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Supervisor intent:** `form_procedure`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** 08-Don, dưới 7

### L1-09 — SV đạt TA đầu vào
**Câu hỏi:** Mã sinh viên AT200201 có đạt kiểm tra phân loại tiếng Anh đầu vào khóa A20C8D7 năm 2024 (lần 2) không?
**Agents:** `diem_thi` | primary=`diem_thi`
**Supervisor intent:** `grade_result`
**Pipeline ∈** `['grade_lookup', 'hybrid_rag', 'agentic_rag', 'hybrid_rag', 'agentic_rag']`
**Phải có (một):** ĐẠT, đạt, AT200201

### L1-10 — SV không đạt TA
**Câu hỏi:** Sinh viên AT200401 có trong danh sách ĐẠT tiếng Anh đầu vào A20C8D7 2024 (lần 2) không?
**Agents:** `diem_thi` | primary=`diem_thi`
**Supervisor intent:** `grade_result`
**Pipeline ∈** `['grade_lookup', 'hybrid_rag', 'agentic_rag', 'hybrid_rag', 'agentic_rag']`
**Phải có (một):** KHÔNG, không đạt, AT200401

### L1-11 — Điểm chuẩn CNTT (không diem_thi)
**Câu hỏi:** Điểm chuẩn ngành Công nghệ thông tin năm 2024 theo đề án tuyển sinh KMA là bao nhiêu?
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Supervisor intent:** `single_domain`
**Không được dùng:** `['diem_thi']`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** 26.20, 26,20, 26.60, 26,60
*Supervisor không được gán diem_thi cho «điểm chuẩn».*

### L1-12 — Chuẩn VSTEP
**Câu hỏi:** Học viện có công nhận chứng chỉ VSTEP không?
**Agents:** `khao_thi` | primary=`khao_thi`
**Supervisor intent:** `single_domain`
**Không được dùng:** `['diem_thi', 'tuyen_sinh']`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** VSTEP

### L1-13 — Ma trận — không nhầm tuyển sinh
**Câu hỏi:** Ma trận đề thi môn Tin học đại cương gồm những phần nào?
**Agents:** `ma_tran` | primary=`ma_tran`
**Supervisor intent:** `single_domain`
**Không được dùng:** `['tuyen_sinh']`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`

### L1-14 — Tổng phí nhập học
**Câu hỏi:** Tổng số tiền phải nộp khi làm thủ tục nhập học theo hướng dẫn KMA 2024 là bao nhiêu?
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Supervisor intent:** `form_procedure`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Gold:** 10.896.940; 10896940

## L2 — Trung bình — hybrid/agentic/grade_lookup

### L2-01 — So sánh điểm TS ATTT
**Câu hỏi:** So sánh điểm trúng tuyển năm 2023 và 2024 của ngành An toàn thông tin (cơ sở Hà Nội) theo đề án tuyển sinh KMA.
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Supervisor intent:** `single_domain`
**Không được dùng:** `['diem_thi']`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Phải có (một):** 25.60, 25.90, 25,90, 25.95

### L2-02 — Liệt kê tổ hợp TS 2025
**Câu hỏi:** Liệt kê các tổ hợp môn xét tuyển đại học chính quy KMA năm 2025.
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Phải có (một):** A00, A01, Toán

### L2-03 — CDIO CNTT
**Câu hỏi:** Chương trình CNTT chính quy KMA theo hướng tiếp cận nào và mã chương trình là gì?
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Phải có (một):** CDIO, KMC, 7.48

### L2-04 — Đối tượng chuẩn NN
**Câu hỏi:** Quy định chuẩn ngoại ngữ KMA không áp dụng cho những đối tượng sinh viên nào?
**Agents:** `khao_thi` | primary=`khao_thi`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Phải có (một):** kỹ sư tài năng, chất lượng cao

### L2-05 — TOEIC TA2
**Câu hỏi:** Theo bảng chuẩn tiếng Anh, sinh viên cần bao nhiêu tín chỉ tích lũy và TOEIC tối thiểu khi kết thúc Tiếng Anh 2?
**Agents:** `khao_thi` | primary=`khao_thi`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Phải có (một):** 350, 3

### L2-06 — Ma trận THĐC — mức độ
**Câu hỏi:** Trong ma trận Tin học đại cương, tổng điểm phân bổ NB, TH, VD, VDC lần lượt là bao nhiêu?
**Agents:** `ma_tran` | primary=`ma_tran`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Phải có (một):** 10, 22

### L2-07 — Ma trận CSDL
**Câu hỏi:** Ma trận đề thi môn Lý thuyết cơ sở dữ liệu có những phần nội dung chính nào?
**Agents:** `ma_tran` | primary=`ma_tran`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`

### L2-08 — Giấy tờ nhập học
**Câu hỏi:** Liệt kê ít nhất 6 loại giấy tờ sinh viên phải mang khi làm thủ tục nhập học KMA 2024.
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Supervisor intent:** `form_procedure`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Phải có (một):** trúng tuyển, học bạ, CCCD

### L2-09 — So sánh đơn nghỉ
**Câu hỏi:** Khác nhau giữa đơn nghỉ học dưới 7 ngày và trên 7 ngày của KMA?
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Supervisor intent:** `form_procedure`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Phải có (một):** 08-Don, 09-Don, 7 ngày, dưới 7, trên 7, 08-Don_nghi, 09-Don_nghi, nghỉ học tạm thời, nghỉ học

### L2-10 — File HK1 đợt 2
**Câu hỏi:** File bảng điểm học kỳ 1 năm 2024-2025 đợt 2 của KMA tổng hợp những học phần nào (nêu ít nhất 3 tên)?
**Agents:** `diem_thi` | primary=`diem_thi`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Phải có (một):** hk1_20242025, 2024, 2025

### L2-11 — CT060310 HK2 đợt 1
**Câu hỏi:** CT060310 điểm học kỳ 2 năm 2024-2025 đợt 1
**Agents:** `diem_thi` | primary=`diem_thi`
**Supervisor intent:** `grade_result`
**Pipeline ∈** `['grade_lookup', 'hybrid_rag', 'agentic_rag']`
**Phải có (một):** CT060310, HK2, học kỳ 2, 2024-2025, đợt 1, học kỳ
*Content: có MSSV hoặc nhắc đúng HK2/đợt (kể cả hỏi lại kỳ khi đã route grade_lookup).*

### L2-12 — AT200106 TA đầu vào
**Câu hỏi:** Sinh viên AT200106 có đạt phân loại tiếng Anh đầu vào A20C8D7 2024 (lần 2) không? Cho biết lớp nếu có.
**Agents:** `diem_thi` | primary=`diem_thi`
**Supervisor intent:** `grade_result`
**Pipeline ∈** `['grade_lookup', 'hybrid_rag', 'agentic_rag', 'hybrid_rag', 'agentic_rag']`
**Phải có (một):** AT200106, ĐẠT, đạt

### L2-13 — AT200201 điểm HK1 đợt 2
**Câu hỏi:** Cho xem điểm học kỳ 1 năm 2024-2025 đợt 2 của sinh viên AT200201.
**Agents:** `diem_thi` | primary=`diem_thi`
**Supervisor intent:** `grade_result`
**Pipeline ∈** `['grade_lookup', 'hybrid_rag', 'agentic_rag']`
**Phải có (một):** AT200201, HK1, học kỳ 1, 2024-2025, đợt 2, học kỳ, đợt

### L2-14 — TOEIC trước đồ án
**Câu hỏi:** Điểm TOEIC tối thiểu trước khi nhận đề tài đồ án tốt nghiệp theo quy định chuẩn ngoại ngữ KMA?
**Agents:** `khao_thi` | primary=`khao_thi`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Gold:** 450

### L2-15 — Hướng dẫn thi TN online
**Câu hỏi:** KMA có tài liệu hướng dẫn thi tốt nghiệp online không? Nêu tên file.
**Agents:** `khao_thi` | primary=`khao_thi`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`

### L2-16 — Thực tập — catalog
**Câu hỏi:** Sinh viên cần giấy giới thiệu thực tập — tên biểu mẫu trong catalog KMA?
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Supervisor intent:** `form_procedure`
**Pipeline ∈** `['native_rag', 'hybrid_rag', 'hybrid_rag', 'agentic_rag']`
**Phải có (một):** 18-Giay_gioi_thieu_thuc_tap, thực tập

## L3 — Multi-agent — Supervisor multi_domain

### L3-01 — TS + phí nhập học
**Câu hỏi:** Theo đề án tuyển sinh KMA 2025, phương thức tuyển sinh đại học chính quy là gì? Đồng thời theo hướng dẫn nhập học 2024, tổng số tiền phải nộp khi làm thủ tục là bao nhiêu?
**Agents:** `tuyen_sinh, bieu_mau` | primary=`tuyen_sinh`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent', 'hybrid_rag', 'agentic_rag', 'multi_agent']`
**Phải có (một):** xét tuyển, 10.896, tuyển sinh

### L3-02 — Quy chế + đơn phúc khảo
**Câu hỏi:** Theo quy chế đào tạo KMA 2025, chương trình học được xây dựng theo đơn vị gì? Và sinh viên muốn phúc khảo bài thi cần dùng đơn/mẫu nào trong catalog?
**Agents:** `khao_thi, bieu_mau` | primary=`bieu_mau`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent']`
**Phải có (một):** tín chỉ, phúc khảo, 15-Don

### L3-03 — Chuẩn NN + điểm TA
**Câu hỏi:** Chuẩn TOEIC tối thiểu trước khi nhận đề tài đồ án của KMA là bao nhiêu? Và sinh viên AT200106 có đạt tiếng Anh đầu vào khóa A20C8D7 2024 (lần 2) không?
**Agents:** `khao_thi, diem_thi` | primary=`khao_thi`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent', 'hybrid_rag', 'agentic_rag', 'multi_agent']`
**Phải có (một):** 450, AT200106, ĐẠT, đạt

### L3-04 — Ma trận + quy chế thi
**Câu hỏi:** Ma trận Tin học đại cương quy định thời gian thi bao lâu? Quy chế đào tạo KMA 2025 quy định khối lượng tối thiểu cử nhân bao nhiêu tín chỉ?
**Agents:** `ma_tran, khao_thi` | primary=`ma_tran`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent']`
**Phải có (một):** 60, 120, phút, tín chỉ

### L3-05 — CTĐT + ma trận toán
**Câu hỏi:** Chương trình CNTT KMA theo CDIO có mã ngành gì? Ma trận môn Toán cao cấp A3 thuộc khoa nào?
**Agents:** `tuyen_sinh, ma_tran` | primary=`tuyen_sinh`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent']`
**Phải có (một):** CDIO, 7.48, Cơ bản

### L3-06 — Điểm chuẩn + mẫu nhập học
**Câu hỏi:** Điểm trúng tuyển ngành CNTT Hà Nội năm 2024 của KMA là bao nhiêu? Và có mẫu đơn/biểu mẫu nào liên quan thủ tục nhập học trong catalog?
**Agents:** `tuyen_sinh, bieu_mau` | primary=`tuyen_sinh`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent', 'hybrid_rag', 'agentic_rag', 'multi_agent']`
**Phải có (một):** 26.20, 26.60, 26.1, nhập học, Thu_tuc

### L3-07 — TOEIC TA3 + ma trận THĐC
**Câu hỏi:** Yêu cầu TOEIC khi kết thúc Tiếng Anh 3 theo quy định chuẩn ngoại ngữ KMA? Và môn Tin học đại cương có bao nhiêu câu trắc nghiệm theo ma trận?
**Agents:** `khao_thi, ma_tran` | primary=`khao_thi`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent']`
**Phải có (một):** 450, 50

### L3-08 — Kết quả TA + đơn hoãn thi
**Câu hỏi:** Tài liệu kết quả thi Anh văn công bố 2024 của KMA dùng để tra cứu gì? Và đơn xin hoãn thi trong bộ biểu mẫu tên file gì?
**Agents:** `diem_thi, bieu_mau` | primary=`diem_thi`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent']`
**Phải có (một):** 14-Don_hoan_thi, Anh văn, 08_ket_qua, hoãn

### L3-09 — Quy chế + CTĐT CNTT
**Câu hỏi:** Quy chế đào tạo 2025: khối lượng tối thiểu cử nhân? Chương trình CNTT: mã ngành đào tạo?
**Agents:** `khao_thi, tuyen_sinh` | primary=`khao_thi`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent']`
**Phải có (một):** 120, 7.48, tín chỉ

### L3-10 — Thạc sĩ + mã trường
**Câu hỏi:** KMA có danh sách trúng tuyển thạc sĩ ATTT 2025 không? Đề án tuyển sinh đại học 2025 ghi mã trường là gì?
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Supervisor intent:** `single_domain`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Phải có (một):** KMA, thạc sĩ
*Một agent đủ nếu cả hai ý cùng corpus tuyển sinh — không bắt 2 agent.*

### L3-11 — Đơn nghỉ + BHYT
**Câu hỏi:** Sinh viên nghỉ học trên 7 ngày và cần cấp lại thẻ BHYT: dùng những đơn/mẫu nào trong catalog KMA?
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Supervisor intent:** `form_procedure`
**Tối thiểu agents:** 1
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Phải có (một):** 09-Don, 16-Don, BHYT

### L3-12 — DT070103 + chứng chỉ TA
**Câu hỏi:** Sinh viên DT070103 có đạt phân loại tiếng Anh đầu vào 2024 không? File danh sách nhận chứng chỉ tiếng Anh TA 2024 dùng để tra cứu gì?
**Agents:** `diem_thi` | primary=`diem_thi`
**Supervisor intent:** `grade_result`
**Pipeline ∈** `['grade_lookup', 'hybrid_rag', 'agentic_rag', 'hybrid_rag', 'agentic_rag']`
**Phải có (một):** DT070103

## L4 — Phức tạp — Planner

### L4-01 — Tổng hợp tân SV
**Câu hỏi:** Em là tân sinh viên KMA nhập học 2024: cho em biết tổng tiền phải nộp khi làm thủ tục, học viện có ký túc xá không, cần mang những giấy tờ gì (ít nhất 5 mục), và trang tuyển sinh chính thức là gì?
**Agents:** `bieu_mau, tuyen_sinh` | primary=`bieu_mau`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent', 'hybrid_rag', 'agentic_rag', 'multi_agent']`
**Planner:** bật
**Phải có (một):** 10.896, Ký túc xá, tuyensinh, giấy tờ

### L4-02 — Roadmap ngoại ngữ
**Câu hỏi:** Giải thích lộ trình chuẩn tiếng Anh KMA: TOEIC tối thiểu sau Tiếng Anh 1, Tiếng Anh 2, Tiếng Anh 3, trước khi nhận đề tài đồ án; nêu rõ số tín chỉ tích lũy tương ứng từng mốc.
**Agents:** `khao_thi` | primary=`khao_thi`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag', 'multi_agent']`
**Planner:** bật
**Phải có (một):** 300, 350, 450

### L4-03 — So sánh ngành TS
**Câu hỏi:** So sánh chỉ tiêu, số nhập học và điểm trúng tuyển năm 2024 của ngành CNTT và An toàn thông tin (cơ sở Hà Nội) theo đề án tuyển sinh KMA.
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag', 'multi_agent']`
**Planner:** bật
**Phải có (một):** 26.20, 26.60, 25.90, 25.95

### L4-04 — Thi + đơn + quy chế
**Câu hỏi:** Sinh viên KMA muốn phúc khảo kết quả thi, xin hoãn thi và cần biết quy chế đào tạo quy định chương trình học theo đơn vị tín chỉ — hướng dẫn từng thủ tục và tên đơn tương ứng.
**Agents:** `khao_thi, bieu_mau` | primary=`bieu_mau`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent', 'hybrid_rag', 'agentic_rag', 'multi_agent']`
**Planner:** bật
**Phải có (một):** phúc khảo, hoãn thi, tín chỉ, 15-Don, 14-Don

### L4-05 — Ma trận 3 môn
**Câu hỏi:** Trong tài liệu ma trận đề thi KMA, nêu tổng số câu và thời gian thi của Tin học đại cương, khoa phụ trách Toán cao cấp A3, và ít nhất hai phần nội dung của Lý thuyết CSDL.
**Agents:** `ma_tran` | primary=`ma_tran`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag', 'multi_agent']`
**Planner:** bật
**Phải có (một):** 50, 60, Cơ bản, CSDL, phút

### L4-06 — Điểm TA + quy chế
**Câu hỏi:** Cho biết sinh viên AT200401 và AT200201 trong kết quả phân loại tiếng Anh đầu vào A20C8D7 2024 (lần 2), đồng thời nêu điểm TOEIC tối thiểu trước đồ án theo quy định chuẩn ngoại ngữ KMA.
**Agents:** `diem_thi, khao_thi` | primary=`diem_thi`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent', 'hybrid_rag', 'agentic_rag', 'multi_agent']`
**Planner:** bật
**Phải có (một):** AT200401, AT200201, 450, TOEIC

### L4-07 — Bảo lưu / tiếp tục / thôi học
**Câu hỏi:** Sinh viên KMA đang cân nhắc bảo lưu kết quả, sau đó tiếp tục học hoặc thôi học: mỗi trường hợp dùng đơn nào trong catalog, khác nhau thế nào?
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag', 'multi_agent']`
**Planner:** bật
**Phải có (một):** 10-Don, 11-Don, 12-Don, bảo lưu

### L4-08 — CNTT + thực tập + đồ án
**Câu hỏi:** Sinh viên ngành CNTT KMA: mã ngành, hướng CDIO, đơn đăng ký đồ án lần 2 và giấy giới thiệu thực tập — tên file và mục đích từng biểu mẫu.
**Agents:** `tuyen_sinh, bieu_mau` | primary=`tuyen_sinh`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent', 'hybrid_rag', 'agentic_rag', 'multi_agent']`
**Planner:** bật
**Phải có (một):** 7.48.01.01, 7.48, 17-Don, 18-Giay, CDIO

### L4-09 — Ưu tiên nhập học + MBank
**Câu hỏi:** Thủ tục nhập học KMA 2024: các khoản phí bắt buộc (học phí HK1 tạm thu, BHYT, thư viện, thẻ SV, khám SK), tài khoản ngân hàng nhận tiền, hướng dẫn mở tài khoản MBank và mẫu đăng ký TK MBank.
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag', 'multi_agent']`
**Planner:** bật
**Phải có (một):** 9.000.000, 9.000, MBank, 26-Dang_ky, 10.896, nhập học

### L4-10 — HK điểm + tra cứu
**Câu hỏi:** Bảng điểm học kỳ 1 năm 2024-2025 đợt 2 của KMA gồm những học phần/khóa nào, file PDF tên gì, và sinh viên tra cứu điểm cá nhân theo MSSV cần lưu ý gì?
**Agents:** `diem_thi` | primary=`diem_thi`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag', 'multi_agent']`
**Planner:** bật
**Phải có (một):** hk1_20242025_dot2, hk1, 2024-2025, đợt 2, MSSV, bảng điểm

## L5 — Multi-turn

### L5-01 — Follow-up biểu mẫu
**Lượt 1:** Cho tôi biết đơn xin nghỉ học dưới 7 ngày của KMA.
**Lượt 2:** Còn nếu nghỉ trên 7 ngày thì sao?
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Pipeline ∈** `['native_rag', 'hybrid_rag', 'multi_agent', 'form_fill', 'native_rag', 'hybrid_rag']`

### L5-02 — Follow-up tuyển sinh
**Lượt 1:** Điểm trúng tuyển CNTT Hà Nội năm 2024 của KMA?
**Lượt 2:** Còn an toàn thông tin thì điểm bao nhiêu?
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Pipeline ∈** `['native_rag', 'hybrid_rag', 'multi_agent', 'form_fill', 'native_rag', 'hybrid_rag']`

### L5-03 — Follow-up ma trận
**Lượt 1:** Ma trận đề thi Tin học đại cương có bao nhiêu câu?
**Lượt 2:** Thời gian làm bài là bao lâu?
**Agents:** `ma_tran` | primary=`ma_tran`
**Pipeline ∈** `['native_rag', 'hybrid_rag', 'multi_agent', 'form_fill', 'native_rag', 'hybrid_rag']`

### L5-04 — Đổi mảng giữa phiên
**Lượt 1:** Chuẩn TOEIC trước khi làm đồ án tốt nghiệp KMA?
**Lượt 2:** Giờ cho tôi mẫu đơn phúc khảo bài thi.
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Pipeline ∈** `['native_rag', 'hybrid_rag', 'multi_agent', 'form_fill', 'native_rag', 'hybrid_rag']`

### L5-05 — Đại từ — điền đơn
**Lượt 1:** Tôi cần giấy xác nhận sinh viên để vay vốn ngân hàng.
**Lượt 2:** Điền giúp tôi đơn đó được không?
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Pipeline ∈** `['form_fill', 'native_rag', 'hybrid_rag']`

### L5-06 — Follow-up điểm MSSV
**Lượt 1:** CT060310 điểm học kỳ 2 năm 2024-2025 đợt 1
**Lượt 2:** Liệt kê các môn và điểm của bạn ấy.
**Agents:** `diem_thi` | primary=`diem_thi`
**Pipeline ∈** `['native_rag', 'hybrid_rag', 'multi_agent', 'form_fill', 'native_rag', 'hybrid_rag']`

### L5-07 — Off-topic chen giữa
**Lượt 1:** Quy định miễn thi chuẩn tiếng Anh đầu ra KMA?
**Lượt 2:** Cho em hỏi giá Bitcoin hôm nay?
**Lượt 3:** Vậy TOEIC tối thiểu trước đồ án là bao nhiêu?
**Agents:** `khao_thi` | primary=`khao_thi`
**Pipeline ∈** `['native_rag', 'hybrid_rag', 'multi_agent', 'form_fill', 'native_rag', 'hybrid_rag']`

### L5-08 — Hai mảng trong phiên
**Lượt 1:** Em cần biết điểm trúng tuyển CNTT 2024 và học phí tạm thu HK1 khi nhập học.
**Lượt 2:** Tóm lại em phải chuẩn bị bao nhiêu tiền mặt theo hướng dẫn nhập học?
**Agents:** `bieu_mau, tuyen_sinh` | primary=`bieu_mau`
**Pipeline ∈** `['native_rag', 'hybrid_rag', 'multi_agent', 'form_fill', 'native_rag', 'hybrid_rag']`

## L6 — Biểu mẫu & form fill

### L6-01 — Catalog BHYT ATTT
**Câu hỏi:** Trong catalog biểu mẫu KMA, mẫu khai BHYT sinh viên ATTT và file hướng dẫn khai BHYT tên gì?
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Supervisor intent:** `form_procedure`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** 24-Mau_khai_BHYT, 25-Huong_dan_khai_BHYT

### L6-02 — Điền đơn xác nhận SV
**Câu hỏi:** Điền giúp tôi giấy xác nhận sinh viên.
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Pipeline ∈** `['form_fill', 'native_rag', 'hybrid_rag']`
**Phải có (một):** điền, mục, họ tên, xác nhận

### L6-03 — Tải đơn bảo lưu
**Câu hỏi:** Tôi muốn tải đơn bảo lưu kết quả học tập — cho tên file trong catalog KMA.
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** 10-Don_bao_luu, bảo lưu

### L6-04 — Điểm chuẩn — routing negative
**Câu hỏi:** Điểm chuẩn ngành DTVT năm 2024 của KMA?
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Supervisor intent:** `single_domain`
**Không được dùng:** `['diem_thi']`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** 24.5, 24,5, 25.0, 25.35, DTVT

## L1 — Đơn giản — Supervisor 1 agent + native/hybrid

### L1-15 — SĐT tuyển sinh
**Câu hỏi:** Số điện thoại liên hệ tuyển sinh KMA trong đề án 2025?
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Gold:** 0986622772

### L1-16 — Phương thức TS 2025
**Câu hỏi:** Phương thức tuyển sinh đại học chính quy KMA năm 2025 là gì?
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** xét tuyển, THPT

## L2 — Trung bình — hybrid/agentic/grade_lookup

### L2-17 — Điểm trúng tuyển CNTT 2024
**Câu hỏi:** Điểm trúng tuyển ngành Công nghệ thông tin (Hà Nội) năm 2024 theo đề án KMA?
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Không được dùng:** `['diem_thi']`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Gold:** 26.20; 26.60

### L2-18 — KTX nhập học
**Câu hỏi:** Học viện có ký túc xá cho sinh viên hệ đóng học phí khi nhập học không?
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Pipeline ∈** `['native_rag', 'hybrid_rag', 'hybrid_rag', 'agentic_rag']`
**Phải có (một):** không có, Ký túc xá

## L3 — Multi-agent — Supervisor multi_domain

### L3-13 — Điểm DTVT + phiếu ra trường
**Câu hỏi:** Điểm trúng tuyển ngành Điện tử viễn thông 2025 và mẫu phiếu thanh toán ra trường cá nhân 2026 trong tài liệu KMA?
**Agents:** `tuyen_sinh, bieu_mau` | primary=`tuyen_sinh`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent']`
**Phải có (một):** DTVT, thanh toán, ra trường, trúng tuyển

### L3-14 — Ma trận kiểm thử + quy chế
**Câu hỏi:** Môn Kiểm thử an toàn hệ thống thông tin thuộc ma trận nào? Quy chế đào tạo 2025 áp dụng cho cơ sở Hà Nội và TP.HCM không?
**Agents:** `ma_tran, khao_thi` | primary=`ma_tran`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent']`
**Phải có (một):** Kiểm thử, Phân hiệu, Hà Nội, TP.HCM

## L4 — Phức tạp — Planner

### L4-11 — Ba mảng tân SV
**Câu hỏi:** Tân sinh viên KMA: điểm chuẩn CNTT 2024, tổng tiền nhập học 2024, và mẫu đơn đăng ký học — trả lời từng phần theo tài liệu.
**Agents:** `tuyen_sinh, bieu_mau` | primary=`tuyen_sinh`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent', 'hybrid_rag', 'agentic_rag', 'multi_agent']`
**Planner:** bật
**Phải có (một):** 26.20, 26.60, 10.896, 04-Don, nhập học

### L4-12 — Chuẩn NN đầy đủ
**Câu hỏi:** Tổng hợp: TOEIC sau TA1, TA2, TA3, trước đồ án và điều kiện công nhận VSTEP theo quy định chuẩn ngoại ngữ KMA.
**Agents:** `khao_thi` | primary=`khao_thi`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag', 'multi_agent']`
**Planner:** bật
**Phải có (một):** 300, 350, 450, VSTEP

## L5 — Multi-turn

### L5-09 — Điểm chuẩn follow-up
**Lượt 1:** Điểm chuẩn ngành CNTT năm 2024 của KMA?
**Lượt 2:** Năm 2023 thì sao?
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Pipeline ∈** `['native_rag', 'hybrid_rag', 'multi_agent', 'form_fill', 'native_rag', 'hybrid_rag']`

### L5-10 — MSSV + học kỳ follow-up
**Lượt 1:** CT060310 điểm học kỳ 2 năm 2024-2025 đợt 1
**Lượt 2:** Có môn nào không đạt không?
**Agents:** `diem_thi` | primary=`diem_thi`
**Pipeline ∈** `['native_rag', 'hybrid_rag', 'multi_agent', 'form_fill', 'native_rag', 'hybrid_rag']`

## L0 — Guardrail

### L0-07 — Tạm biệt
**Câu hỏi:** Tạm biệt nhé, hẹn gặp lại!
**Agents:** `(không)` | primary=``
**Pipeline ∈** `['guardrail']`

### L0-08 — Off-topic y tế
**Câu hỏi:** Thuốc hạ sốt cho trẻ 5 tuổi uống liều bao nhiêu?
**Agents:** `(không)` | primary=``
**Pipeline ∈** `['guardrail']`
**Phải có (một):** ngoài phạm vi, KMA

## L1 — Đơn giản — Supervisor 1 agent + native/hybrid

### L1-17 — Địa chỉ PHCM
**Câu hỏi:** Địa chỉ Phân hiệu KMA tại TP.HCM theo đề án tuyển sinh 2025?
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Supervisor intent:** `single_domain`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** Cộng Hòa, Tân Bình, TP.HCM

### L1-18 — Phân hiệu quy chế
**Câu hỏi:** Quy chế đào tạo KMA 2025 có áp dụng cho Phân hiệu TP.HCM không?
**Agents:** `khao_thi` | primary=`khao_thi`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** Phân hiệu, Hồ Chí Minh, Hà Nội

### L1-19 — Đơn cấp lại thẻ SV
**Câu hỏi:** Sinh viên mất thẻ sinh viên cần đơn nào trong catalog KMA?
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Supervisor intent:** `form_procedure`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** 06-Don_cap_lai_the, thẻ sinh viên

### L1-20 — Ma trận ATHT
**Câu hỏi:** Môn Kiểm thử an toàn hệ thống thông tin có trong ma trận đề thi KMA không?
**Agents:** `ma_tran` | primary=`ma_tran`
**Không được dùng:** `['khao_thi']`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** Kiểm thử, an toàn, ma trận

## L2 — Trung bình — hybrid/agentic/grade_lookup

### L2-19 — Cú pháp chuyển khoản
**Câu hỏi:** Cú pháp nộp kinh phí nhập học vào tài khoản MB theo hướng dẫn KMA 2024?
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Phải có (một):** 0021145666888, Mã trúng tuyển

### L2-20 — Kết quả CT4
**Câu hỏi:** Tài liệu kết quả tốt nghiệp CT4 năm 2024 của KMA dùng để tra cứu thông tin gì?
**Agents:** `diem_thi` | primary=`diem_thi`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Phải có (một):** CT4, tốt nghiệp, kết quả

### L2-21 — Chỉ tiêu CNTT 2025
**Câu hỏi:** Chỉ tiêu tuyển sinh ngành Công nghệ thông tin năm 2025 của KMA là bao nhiêu?
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Không được dùng:** `['diem_thi']`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`
**Phải có (một):** chỉ tiêu, CNTT, Công nghệ thông tin

### L2-22 — Miễn thi NN
**Câu hỏi:** Sinh viên có thể được miễn thi chuẩn tiếng Anh đầu ra theo quy định KMA trong trường hợp nào?
**Agents:** `khao_thi` | primary=`khao_thi`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag']`

## L3 — Multi-agent — Supervisor multi_domain

### L3-15 — Thi TN + đơn phúc khảo
**Câu hỏi:** KMA có hướng dẫn thi tốt nghiệp online không? Và sinh viên phúc khảo bài thi dùng đơn nào trong catalog?
**Agents:** `khao_thi, bieu_mau` | primary=`khao_thi`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent']`
**Phải có (một):** thi tốt nghiệp, phúc khảo, 15-Don, online

### L3-16 — Điểm chuẩn + quy chế tín chỉ
**Câu hỏi:** Điểm trúng tuyển ngành An toàn thông tin Hà Nội năm 2024? Quy chế đào tạo 2025 quy định chương trình học theo đơn vị gì?
**Agents:** `tuyen_sinh, khao_thi` | primary=`tuyen_sinh`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent']`
**Phải có (một):** 25.90, 25.95, tín chỉ, an toàn

### L3-17 — Catalog thực tập + CDIO
**Câu hỏi:** Tên file giấy giới thiệu thực tập trong catalog KMA? Chương trình CNTT được xây dựng theo hướng tiếp cận nào?
**Agents:** `bieu_mau, tuyen_sinh` | primary=`bieu_mau`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent']`
**Phải có (một):** 18-Giay, CDIO, thực tập

## L4 — Phức tạp — Planner

### L4-13 — Nhập học đầy đủ
**Câu hỏi:** Tân sinh viên KMA 2024: tổng tiền nhập học, có ký túc xá không, cú pháp chuyển khoản MB và mẫu đăng ký tài khoản MBank — trả lời theo hướng dẫn nhập học.
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag', 'multi_agent']`
**Planner:** bật
**Phải có (một):** 10.896, MBank, 26-Dang_ky, 0021145666888

### L4-14 — So sánh 3 ngành TS
**Câu hỏi:** So sánh điểm trúng tuyển năm 2024 của ngành CNTT, An toàn thông tin và Điện tử viễn thông (cơ sở Hà Nội) theo đề án tuyển sinh KMA.
**Agents:** `tuyen_sinh` | primary=`tuyen_sinh`
**Pipeline ∈** `['hybrid_rag', 'agentic_rag', 'multi_agent']`
**Planner:** bật
**Phải có (một):** 26.20, 26.60, 25.90, 25.95, 25.0, 25.35

### L4-15 — Điểm + đơn + ma trận
**Câu hỏi:** Sinh viên AT200106 đạt tiếng Anh đầu vào 2024 chưa? Đơn xin hoãn thi tên file gì? Ma trận Tin học đại cương có bao nhiêu câu và thời gian thi?
**Agents:** `diem_thi, bieu_mau, ma_tran` | primary=`diem_thi`
**Supervisor intent:** `multi_domain`
**Tối thiểu agents:** 1
**Pipeline ∈** `['multi_agent', 'hybrid_rag', 'agentic_rag', 'multi_agent']`
**Planner:** bật
**Phải có (một):** AT200106, 14-Don, 50, 60, hoãn

## L5 — Multi-turn

### L5-11 — Follow-up khao_thi
**Lượt 1:** TOEIC tối thiểu sau Tiếng Anh 1 của KMA là bao nhiêu?
**Lượt 2:** Còn sau Tiếng Anh 2 thì sao?
**Agents:** `khao_thi` | primary=`khao_thi`
**Pipeline ∈** `['native_rag', 'hybrid_rag', 'multi_agent', 'form_fill', 'native_rag', 'hybrid_rag']`

### L5-12 — Form → hủy
**Lượt 1:** Điền giúp tôi đơn xin nghỉ học dưới 7 ngày.
**Lượt 2:** Thôi, hủy đi.
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Pipeline ∈** `['form_fill', 'native_rag', 'hybrid_rag', 'native_rag', 'hybrid_rag']`

## L6 — Biểu mẫu & form fill

### L6-05 — Đơn đăng ký học
**Câu hỏi:** Trong catalog KMA, đơn đăng ký học tên file gì?
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Supervisor intent:** `form_procedure`
**Pipeline ∈** `['native_rag', 'hybrid_rag']`
**Phải có (một):** 04-Don_dang_ky_hoc

### L6-06 — Điền đơn phúc khảo
**Câu hỏi:** Điền giúp tôi đơn xin phúc khảo bài thi.
**Agents:** `bieu_mau` | primary=`bieu_mau`
**Pipeline ∈** `['form_fill', 'native_rag', 'hybrid_rag']`
**Phải có (một):** điền, phúc khảo, mục

---
*Machine-readable: `eval/benchmark.json`*