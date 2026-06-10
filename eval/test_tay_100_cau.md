# Test tay — 100 câu hỏi KMA Chatbot

**Phiên bản:** 3.1 · **100 câu**

100 câu test trực tiếp trên http://127.0.0.1:8000 — copy câu hỏi, so sánh câu trả lời chatbot với mục «Câu trả lời đúng cần có». Gold facts trích từ docs/. Cần ingest_all.py + Qdrant trước khi test.

## Cách dùng

1. Bật server: `uvicorn api.main:app --host 127.0.0.1 --port 8000`
2. Mở http://127.0.0.1:8000
3. **Copy** khối câu hỏi (```text```) → dán vào chat
4. So sánh câu trả lời với **Câu trả lời đúng cần có**
5. **L5 (multi-turn):** gửi lượt 1 → đợi trả lời → lượt 2 **cùng tab**, không refresh

## Mục lục

| ID | Tier | Tiêu đề |
|----|------|---------|
| [L0-01](#l0-01) | L0 | Chào hỏi |
| [L0-02](#l0-02) | L0 | Cảm ơn |
| [L0-03](#l0-03) | L0 | Off-topic thời tiết |
| [L0-04](#l0-04) | L0 | Off-topic lập trình |
| [L0-05](#l0-05) | L0 | Trường khác |
| [L0-06](#l0-06) | L0 | Giới thiệu khả năng |
| [L1-01](#l1-01) | L1 | Mã trường KMA |
| [L1-02](#l1-02) | L1 | Website tuyển sinh |
| [L1-03](#l1-03) | L1 | Khối tín chỉ cử nhân |
| [L1-04](#l1-04) | L1 | TOEIC Tiếng Anh 1 |
| [L1-05](#l1-05) | L1 | Ma trận THĐC — số câu |
| [L1-06](#l1-06) | L1 | Ma trận Toán A3 — khoa |
| [L1-07](#l1-07) | L1 | Đơn phúc khảo |
| [L1-08](#l1-08) | L1 | Đơn nghỉ dưới 7 ngày |
| [L1-09](#l1-09) | L1 | SV đạt TA đầu vào |
| [L1-10](#l1-10) | L1 | SV không đạt TA |
| [L1-11](#l1-11) | L1 | Điểm chuẩn CNTT (không diem_thi) |
| [L1-12](#l1-12) | L1 | Chuẩn VSTEP |
| [L1-13](#l1-13) | L1 | Ma trận — không nhầm tuyển sinh |
| [L1-14](#l1-14) | L1 | Tổng phí nhập học |
| [L2-01](#l2-01) | L2 | So sánh điểm TS ATTT |
| [L2-02](#l2-02) | L2 | Liệt kê tổ hợp TS 2025 |
| [L2-03](#l2-03) | L2 | CDIO CNTT |
| [L2-04](#l2-04) | L2 | Đối tượng chuẩn NN |
| [L2-05](#l2-05) | L2 | TOEIC TA2 |
| [L2-06](#l2-06) | L2 | Ma trận THĐC — mức độ |
| [L2-07](#l2-07) | L2 | Ma trận CSDL |
| [L2-08](#l2-08) | L2 | Giấy tờ nhập học |
| [L2-09](#l2-09) | L2 | So sánh đơn nghỉ |
| [L2-10](#l2-10) | L2 | File HK1 đợt 2 |
| [L2-11](#l2-11) | L2 | CT060310 HK2 đợt 1 |
| [L2-12](#l2-12) | L2 | AT200106 TA đầu vào |
| [L2-13](#l2-13) | L2 | AT200201 điểm HK1 đợt 2 |
| [L2-14](#l2-14) | L2 | TOEIC trước đồ án |
| [L2-15](#l2-15) | L2 | Hướng dẫn thi TN online |
| [L2-16](#l2-16) | L2 | Thực tập — catalog |
| [L3-01](#l3-01) | L3 | TS + phí nhập học |
| [L3-02](#l3-02) | L3 | Quy chế + đơn phúc khảo |
| [L3-03](#l3-03) | L3 | Chuẩn NN + điểm TA |
| [L3-04](#l3-04) | L3 | Ma trận + quy chế thi |
| [L3-05](#l3-05) | L3 | CTĐT + ma trận toán |
| [L3-06](#l3-06) | L3 | Điểm chuẩn + mẫu nhập học |
| [L3-07](#l3-07) | L3 | TOEIC TA3 + ma trận THĐC |
| [L3-08](#l3-08) | L3 | Kết quả TA + đơn hoãn thi |
| [L3-09](#l3-09) | L3 | Quy chế + CTĐT CNTT |
| [L3-10](#l3-10) | L3 | Thạc sĩ + mã trường |
| [L3-11](#l3-11) | L3 | Đơn nghỉ + BHYT |
| [L3-12](#l3-12) | L3 | DT070103 + chứng chỉ TA |
| [L4-01](#l4-01) | L4 | Tổng hợp tân SV |
| [L4-02](#l4-02) | L4 | Roadmap ngoại ngữ |
| [L4-03](#l4-03) | L4 | So sánh ngành TS |
| [L4-04](#l4-04) | L4 | Thi + đơn + quy chế |
| [L4-05](#l4-05) | L4 | Ma trận 3 môn |
| [L4-06](#l4-06) | L4 | Điểm TA + quy chế |
| [L4-07](#l4-07) | L4 | Bảo lưu / tiếp tục / thôi học |
| [L4-08](#l4-08) | L4 | CNTT + thực tập + đồ án |
| [L4-09](#l4-09) | L4 | Ưu tiên nhập học + MBank |
| [L4-10](#l4-10) | L4 | HK điểm + tra cứu |
| [L5-01](#l5-01) | L5 | Follow-up biểu mẫu |
| [L5-02](#l5-02) | L5 | Follow-up tuyển sinh |
| [L5-03](#l5-03) | L5 | Follow-up ma trận |
| [L5-04](#l5-04) | L5 | Đổi mảng giữa phiên |
| [L5-05](#l5-05) | L5 | Đại từ — điền đơn |
| [L5-06](#l5-06) | L5 | Follow-up điểm MSSV |
| [L5-07](#l5-07) | L5 | Off-topic chen giữa |
| [L5-08](#l5-08) | L5 | Hai mảng trong phiên |
| [L6-01](#l6-01) | L6 | Catalog BHYT ATTT |
| [L6-02](#l6-02) | L6 | Điền đơn xác nhận SV |
| [L6-03](#l6-03) | L6 | Tải đơn bảo lưu |
| [L6-04](#l6-04) | L6 | Điểm chuẩn — routing negative |
| [L1-15](#l1-15) | L1 | SĐT tuyển sinh |
| [L1-16](#l1-16) | L1 | Phương thức TS 2025 |
| [L2-17](#l2-17) | L2 | Điểm trúng tuyển CNTT 2024 |
| [L2-18](#l2-18) | L2 | KTX nhập học |
| [L3-13](#l3-13) | L3 | Điểm DTVT + phiếu ra trường |
| [L3-14](#l3-14) | L3 | Ma trận kiểm thử + quy chế |
| [L4-11](#l4-11) | L4 | Ba mảng tân SV |
| [L4-12](#l4-12) | L4 | Chuẩn NN đầy đủ |
| [L5-09](#l5-09) | L5 | Điểm chuẩn follow-up |
| [L5-10](#l5-10) | L5 | MSSV + học kỳ follow-up |
| [L0-07](#l0-07) | L0 | Tạm biệt |
| [L0-08](#l0-08) | L0 | Off-topic y tế |
| [L1-17](#l1-17) | L1 | Địa chỉ PHCM |
| [L1-18](#l1-18) | L1 | Phân hiệu quy chế |
| [L1-19](#l1-19) | L1 | Đơn cấp lại thẻ SV |
| [L1-20](#l1-20) | L1 | Ma trận ATHT |
| [L2-19](#l2-19) | L2 | Cú pháp chuyển khoản |
| [L2-20](#l2-20) | L2 | Kết quả CT4 |
| [L2-21](#l2-21) | L2 | Chỉ tiêu CNTT 2025 |
| [L2-22](#l2-22) | L2 | Miễn thi NN |
| [L3-15](#l3-15) | L3 | Thi TN + đơn phúc khảo |
| [L3-16](#l3-16) | L3 | Điểm chuẩn + quy chế tín chỉ |
| [L3-17](#l3-17) | L3 | Catalog thực tập + CDIO |
| [L4-13](#l4-13) | L4 | Nhập học đầy đủ |
| [L4-14](#l4-14) | L4 | So sánh 3 ngành TS |
| [L4-15](#l4-15) | L4 | Điểm + đơn + ma trận |
| [L5-11](#l5-11) | L5 | Follow-up khao_thi |
| [L5-12](#l5-12) | L5 | Form → hủy |
| [L6-05](#l6-05) | L6 | Đơn đăng ký học |
| [L6-06](#l6-06) | L6 | Điền đơn phúc khảo |

---

## L0 — Guardrail — chào / off-topic (8 câu)

### L0-01 — Chào hỏi

**Câu hỏi (copy):**
```text
Xin chào!
```

**Câu trả lời đúng cần có:**

- Chào hỏi / giới thiệu trợ lý KMA và các mảng hỗ trợ. Không tra cứu tài liệu.

---

### L0-02 — Cảm ơn

**Câu hỏi (copy):**
```text
Cảm ơn bạn nhé!
```

**Câu trả lời đúng cần có:**

- Chào hỏi / giới thiệu trợ lý KMA và các mảng hỗ trợ. Không tra cứu tài liệu.

---

### L0-03 — Off-topic thời tiết

**Câu hỏi (copy):**
```text
Thời tiết Hà Nội ngày mai thế nào?
```

**Câu trả lời đúng cần có:**

- Từ chối nhẹ — câu ngoài phạm vi KMA. Gợi ý hỏi đúng mảng (tuyển sinh, quy chế, …).

---

### L0-04 — Off-topic lập trình

**Câu hỏi (copy):**
```text
Viết code Python sắp xếp danh sách như thế nào?
```

**Câu trả lời đúng cần có:**

- Từ chối nhẹ — câu ngoài phạm vi KMA. Gợi ý hỏi đúng mảng (tuyển sinh, quy chế, …).

---

### L0-05 — Trường khác

**Câu hỏi (copy):**
```text
Điểm chuẩn Đại học Bách Khoa Hà Nội năm 2025?
```

**Câu trả lời đúng cần có:**

- Từ chối nhẹ — câu ngoài phạm vi KMA. Gợi ý hỏi đúng mảng (tuyển sinh, quy chế, …).

---

### L0-06 — Giới thiệu khả năng

**Câu hỏi (copy):**
```text
Bạn có thể giúp gì cho sinh viên KMA?
```

**Câu trả lời đúng cần có:**

- Chào hỏi / giới thiệu trợ lý KMA và các mảng hỗ trợ. Không tra cứu tài liệu.

---

## L1 — Đơn giản — một mảng (20 câu)

### L1-01 — Mã trường KMA

**Câu hỏi (copy):**
```text
Mã trường của Học viện Kỹ thuật Mật mã trong đề án tuyển sinh 2025 là gì?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có:** KMA
- **Tài liệu tham chiếu:** 01_de_an_tuyen_sinh_2025.pdf

---

### L1-02 — Website tuyển sinh

**Câu hỏi (copy):**
```text
Trang web tuyển sinh chính thức của KMA là gì?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** tuyensinh.actvn.edu.vn, actvn
- **Tài liệu tham chiếu:** 01_de_an_tuyen_sinh_2025.pdf

---

### L1-03 — Khối tín chỉ cử nhân

**Câu hỏi (copy):**
```text
Khối lượng học tập tối thiểu chương trình cử nhân theo quy chế đào tạo KMA 2025 là bao nhiêu tín chỉ?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có:** 120
- **Tài liệu tham chiếu:** 25_quy_che_dao_tao_dai_hoc_2025.pdf

---

### L1-04 — TOEIC Tiếng Anh 1

**Câu hỏi (copy):**
```text
Sinh viên cần đạt tối thiểu bao nhiêu điểm TOEIC khi kết thúc học phần Tiếng Anh 1 theo quy định chuẩn ngoại ngữ KMA?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có:** 300
- **Tài liệu tham chiếu:** 03_quy_dinh_chuan_ngoai_ngu_2025.pdf

---

### L1-05 — Ma trận THĐC — số câu

**Câu hỏi (copy):**
```text
Môn Tin học đại cương: tổng số câu trắc nghiệm và thời gian làm bài theo ma trận đề thi KMA?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **ma_tran** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 50, 60, phút
- **Tài liệu tham chiếu:** 13_ma_tran_de_thi_tin_hoc_dai_cuong.pdf

---

### L1-06 — Ma trận Toán A3 — khoa

**Câu hỏi (copy):**
```text
Môn Toán cao cấp A3 thuộc khoa nào theo ma trận đề thi?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **ma_tran** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** Cơ bản
- **Tài liệu tham chiếu:** 21_ma_tran_toan_cao_cap_a3.pdf

---

### L1-07 — Đơn phúc khảo

**Câu hỏi (copy):**
```text
KMA có mẫu đơn xin phúc khảo bài thi không? Tên file trong catalog?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** phúc khảo, 15-Don_phuc_khao

---

### L1-08 — Đơn nghỉ dưới 7 ngày

**Câu hỏi (copy):**
```text
Sinh viên xin nghỉ học tạm thời dưới 7 ngày dùng đơn nào?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 08-Don, dưới 7

---

### L1-09 — SV đạt TA đầu vào

**Câu hỏi (copy):**
```text
Mã sinh viên AT200201 có đạt kiểm tra phân loại tiếng Anh đầu vào khóa A20C8D7 năm 2024 (lần 2) không?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** ĐẠT, đạt, AT200201
- **Tài liệu tham chiếu:** 08_ket_qua_thi_anh_van_2024.pdf

---

### L1-10 — SV không đạt TA

**Câu hỏi (copy):**
```text
Sinh viên AT200401 có trong danh sách ĐẠT tiếng Anh đầu vào A20C8D7 2024 (lần 2) không?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** KHÔNG, không đạt, AT200401
- **Tài liệu tham chiếu:** 08_ket_qua_thi_anh_van_2024.pdf

---

### L1-11 — Điểm chuẩn CNTT (không diem_thi)

**Câu hỏi (copy):**
```text
Điểm chuẩn ngành Công nghệ thông tin năm 2024 theo đề án tuyển sinh KMA là bao nhiêu?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 26.20, 26,20, 26.60, 26,60
- **Tài liệu tham chiếu:** 02_de_an_tuyen_sinh_2024.pdf

*Ghi chú:* Supervisor không được gán diem_thi cho «điểm chuẩn».

---

### L1-12 — Chuẩn VSTEP

**Câu hỏi (copy):**
```text
Học viện có công nhận chứng chỉ VSTEP không?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** VSTEP
- **Tài liệu tham chiếu:** 03_quy_dinh_chuan_ngoai_ngu_2025.pdf

---

### L1-13 — Ma trận — không nhầm tuyển sinh

**Câu hỏi (copy):**
```text
Ma trận đề thi môn Tin học đại cương gồm những phần nào?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **ma_tran** (gợi ý, không cần đúng pipeline).
- **Tài liệu tham chiếu:** 13_ma_tran_de_thi_tin_hoc_dai_cuong.pdf

---

### L1-14 — Tổng phí nhập học

**Câu hỏi (copy):**
```text
Tổng số tiền phải nộp khi làm thủ tục nhập học theo hướng dẫn KMA 2024 là bao nhiêu?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có:** 10.896.940 · 10896940
- **Tài liệu tham chiếu:** Thu_tuc_nhap_hoc_2024.pdf

---

## L2 — Trung bình — liệt kê, so sánh, tra điểm MSSV (22 câu)

### L2-01 — So sánh điểm TS ATTT

**Câu hỏi (copy):**
```text
So sánh điểm trúng tuyển năm 2023 và 2024 của ngành An toàn thông tin (cơ sở Hà Nội) theo đề án tuyển sinh KMA.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 25.60, 25.90, 25,90, 25.95

---

### L2-02 — Liệt kê tổ hợp TS 2025

**Câu hỏi (copy):**
```text
Liệt kê các tổ hợp môn xét tuyển đại học chính quy KMA năm 2025.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** A00, A01, Toán

---

### L2-03 — CDIO CNTT

**Câu hỏi (copy):**
```text
Chương trình CNTT chính quy KMA theo hướng tiếp cận nào và mã chương trình là gì?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** CDIO, KMC, 7.48
- **Tài liệu tham chiếu:** 23_chuong_trinh_dao_tao_cntt.pdf

---

### L2-04 — Đối tượng chuẩn NN

**Câu hỏi (copy):**
```text
Quy định chuẩn ngoại ngữ KMA không áp dụng cho những đối tượng sinh viên nào?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** kỹ sư tài năng, chất lượng cao

---

### L2-05 — TOEIC TA2

**Câu hỏi (copy):**
```text
Theo bảng chuẩn tiếng Anh, sinh viên cần bao nhiêu tín chỉ tích lũy và TOEIC tối thiểu khi kết thúc Tiếng Anh 2?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 350, 3

---

### L2-06 — Ma trận THĐC — mức độ

**Câu hỏi (copy):**
```text
Trong ma trận Tin học đại cương, tổng điểm phân bổ NB, TH, VD, VDC lần lượt là bao nhiêu?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **ma_tran** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 10, 22
- **Tài liệu tham chiếu:** 13_ma_tran_de_thi_tin_hoc_dai_cuong.pdf

---

### L2-07 — Ma trận CSDL

**Câu hỏi (copy):**
```text
Ma trận đề thi môn Lý thuyết cơ sở dữ liệu có những phần nội dung chính nào?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **ma_tran** (gợi ý, không cần đúng pipeline).
- **Tài liệu tham chiếu:** 14_ma_tran_de_thi_ly_thuyet_csdl.pdf

---

### L2-08 — Giấy tờ nhập học

**Câu hỏi (copy):**
```text
Liệt kê ít nhất 6 loại giấy tờ sinh viên phải mang khi làm thủ tục nhập học KMA 2024.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** trúng tuyển, học bạ, CCCD
- **Tài liệu tham chiếu:** Thu_tuc_nhap_hoc_2024.pdf

---

### L2-09 — So sánh đơn nghỉ

**Câu hỏi (copy):**
```text
Khác nhau giữa đơn nghỉ học dưới 7 ngày và trên 7 ngày của KMA?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 08-Don, 09-Don, 7 ngày, dưới 7, trên 7, 08-Don_nghi, 09-Don_nghi, nghỉ học tạm thời, nghỉ học

---

### L2-10 — File HK1 đợt 2

**Câu hỏi (copy):**
```text
File bảng điểm học kỳ 1 năm 2024-2025 đợt 2 của KMA tổng hợp những học phần nào (nêu ít nhất 3 tên)?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** hk1_20242025, 2024, 2025
- **Tài liệu tham chiếu:** hk1_20242025_dot2.pdf

---

### L2-11 — CT060310 HK2 đợt 1

**Câu hỏi (copy):**
```text
CT060310 điểm học kỳ 2 năm 2024-2025 đợt 1
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** CT060310, HK2, học kỳ 2, 2024-2025, đợt 1, học kỳ
- **Không được:** không tìm thấy thông tin trong tài liệu
- **Tài liệu tham chiếu:** hk2_20242025_dot1

*Ghi chú:* Content: có MSSV hoặc nhắc đúng HK2/đợt (kể cả hỏi lại kỳ khi đã route grade_lookup).

---

### L2-12 — AT200106 TA đầu vào

**Câu hỏi (copy):**
```text
Sinh viên AT200106 có đạt phân loại tiếng Anh đầu vào A20C8D7 2024 (lần 2) không? Cho biết lớp nếu có.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** AT200106, ĐẠT, đạt
- **Tài liệu tham chiếu:** 08_ket_qua_thi_anh_van_2024.pdf

---

### L2-13 — AT200201 điểm HK1 đợt 2

**Câu hỏi (copy):**
```text
Cho xem điểm học kỳ 1 năm 2024-2025 đợt 2 của sinh viên AT200201.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** AT200201, HK1, học kỳ 1, 2024-2025, đợt 2, học kỳ, đợt

---

### L2-14 — TOEIC trước đồ án

**Câu hỏi (copy):**
```text
Điểm TOEIC tối thiểu trước khi nhận đề tài đồ án tốt nghiệp theo quy định chuẩn ngoại ngữ KMA?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có:** 450

---

### L2-15 — Hướng dẫn thi TN online

**Câu hỏi (copy):**
```text
KMA có tài liệu hướng dẫn thi tốt nghiệp online không? Nêu tên file.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).
- **Tài liệu tham chiếu:** 22_huong_dan_thi_tot_nghiep_online.pdf

---

### L2-16 — Thực tập — catalog

**Câu hỏi (copy):**
```text
Sinh viên cần giấy giới thiệu thực tập — tên biểu mẫu trong catalog KMA?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 18-Giay_gioi_thieu_thuc_tap, thực tập

---

## L3 — Hai mảng trở lên (17 câu)

### L3-01 — TS + phí nhập học

**Câu hỏi (copy):**
```text
Theo đề án tuyển sinh KMA 2025, phương thức tuyển sinh đại học chính quy là gì? Đồng thời theo hướng dẫn nhập học 2024, tổng số tiền phải nộp khi làm thủ tục là bao nhiêu?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh, bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** xét tuyển, 10.896, tuyển sinh

---

### L3-02 — Quy chế + đơn phúc khảo

**Câu hỏi (copy):**
```text
Theo quy chế đào tạo KMA 2025, chương trình học được xây dựng theo đơn vị gì? Và sinh viên muốn phúc khảo bài thi cần dùng đơn/mẫu nào trong catalog?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi, bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** tín chỉ, phúc khảo, 15-Don

---

### L3-03 — Chuẩn NN + điểm TA

**Câu hỏi (copy):**
```text
Chuẩn TOEIC tối thiểu trước khi nhận đề tài đồ án của KMA là bao nhiêu? Và sinh viên AT200106 có đạt tiếng Anh đầu vào khóa A20C8D7 2024 (lần 2) không?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi, diem_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 450, AT200106, ĐẠT, đạt

---

### L3-04 — Ma trận + quy chế thi

**Câu hỏi (copy):**
```text
Ma trận Tin học đại cương quy định thời gian thi bao lâu? Quy chế đào tạo KMA 2025 quy định khối lượng tối thiểu cử nhân bao nhiêu tín chỉ?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **ma_tran, khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 60, 120, phút, tín chỉ

---

### L3-05 — CTĐT + ma trận toán

**Câu hỏi (copy):**
```text
Chương trình CNTT KMA theo CDIO có mã ngành gì? Ma trận môn Toán cao cấp A3 thuộc khoa nào?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh, ma_tran** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** CDIO, 7.48, Cơ bản

---

### L3-06 — Điểm chuẩn + mẫu nhập học

**Câu hỏi (copy):**
```text
Điểm trúng tuyển ngành CNTT Hà Nội năm 2024 của KMA là bao nhiêu? Và có mẫu đơn/biểu mẫu nào liên quan thủ tục nhập học trong catalog?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh, bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 26.20, 26.60, 26.1, nhập học, Thu_tuc

---

### L3-07 — TOEIC TA3 + ma trận THĐC

**Câu hỏi (copy):**
```text
Yêu cầu TOEIC khi kết thúc Tiếng Anh 3 theo quy định chuẩn ngoại ngữ KMA? Và môn Tin học đại cương có bao nhiêu câu trắc nghiệm theo ma trận?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi, ma_tran** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 450, 50

---

### L3-08 — Kết quả TA + đơn hoãn thi

**Câu hỏi (copy):**
```text
Tài liệu kết quả thi Anh văn công bố 2024 của KMA dùng để tra cứu gì? Và đơn xin hoãn thi trong bộ biểu mẫu tên file gì?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi, bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 14-Don_hoan_thi, Anh văn, 08_ket_qua, hoãn

---

### L3-09 — Quy chế + CTĐT CNTT

**Câu hỏi (copy):**
```text
Quy chế đào tạo 2025: khối lượng tối thiểu cử nhân? Chương trình CNTT: mã ngành đào tạo?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi, tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 120, 7.48, tín chỉ

---

### L3-10 — Thạc sĩ + mã trường

**Câu hỏi (copy):**
```text
KMA có danh sách trúng tuyển thạc sĩ ATTT 2025 không? Đề án tuyển sinh đại học 2025 ghi mã trường là gì?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** KMA, thạc sĩ
- **Tài liệu tham chiếu:** 09_trung_tuyen_thac_si_attt_2025.pdf

*Ghi chú:* Một agent đủ nếu cả hai ý cùng corpus tuyển sinh — không bắt 2 agent.

---

### L3-11 — Đơn nghỉ + BHYT

**Câu hỏi (copy):**
```text
Sinh viên nghỉ học trên 7 ngày và cần cấp lại thẻ BHYT: dùng những đơn/mẫu nào trong catalog KMA?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 09-Don, 16-Don, BHYT

---

### L3-12 — DT070103 + chứng chỉ TA

**Câu hỏi (copy):**
```text
Sinh viên DT070103 có đạt phân loại tiếng Anh đầu vào 2024 không? File danh sách nhận chứng chỉ tiếng Anh TA 2024 dùng để tra cứu gì?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** DT070103
- **Tài liệu tham chiếu:** 12_ds_nhan_chung_chi_ta_2024.pdf

---

## L4 — Câu dài / nhiều ý (15 câu)

### L4-01 — Tổng hợp tân SV

**Câu hỏi (copy):**
```text
Em là tân sinh viên KMA nhập học 2024: cho em biết tổng tiền phải nộp khi làm thủ tục, học viện có ký túc xá không, cần mang những giấy tờ gì (ít nhất 5 mục), và trang tuyển sinh chính thức là gì?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau, tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 10.896, Ký túc xá, tuyensinh, giấy tờ

---

### L4-02 — Roadmap ngoại ngữ

**Câu hỏi (copy):**
```text
Giải thích lộ trình chuẩn tiếng Anh KMA: TOEIC tối thiểu sau Tiếng Anh 1, Tiếng Anh 2, Tiếng Anh 3, trước khi nhận đề tài đồ án; nêu rõ số tín chỉ tích lũy tương ứng từng mốc.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 300, 350, 450

---

### L4-03 — So sánh ngành TS

**Câu hỏi (copy):**
```text
So sánh chỉ tiêu, số nhập học và điểm trúng tuyển năm 2024 của ngành CNTT và An toàn thông tin (cơ sở Hà Nội) theo đề án tuyển sinh KMA.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 26.20, 26.60, 25.90, 25.95

---

### L4-04 — Thi + đơn + quy chế

**Câu hỏi (copy):**
```text
Sinh viên KMA muốn phúc khảo kết quả thi, xin hoãn thi và cần biết quy chế đào tạo quy định chương trình học theo đơn vị tín chỉ — hướng dẫn từng thủ tục và tên đơn tương ứng.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi, bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** phúc khảo, hoãn thi, tín chỉ, 15-Don, 14-Don

---

### L4-05 — Ma trận 3 môn

**Câu hỏi (copy):**
```text
Trong tài liệu ma trận đề thi KMA, nêu tổng số câu và thời gian thi của Tin học đại cương, khoa phụ trách Toán cao cấp A3, và ít nhất hai phần nội dung của Lý thuyết CSDL.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **ma_tran** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 50, 60, Cơ bản, CSDL, phút

---

### L4-06 — Điểm TA + quy chế

**Câu hỏi (copy):**
```text
Cho biết sinh viên AT200401 và AT200201 trong kết quả phân loại tiếng Anh đầu vào A20C8D7 2024 (lần 2), đồng thời nêu điểm TOEIC tối thiểu trước đồ án theo quy định chuẩn ngoại ngữ KMA.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi, khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** AT200401, AT200201, 450, TOEIC

---

### L4-07 — Bảo lưu / tiếp tục / thôi học

**Câu hỏi (copy):**
```text
Sinh viên KMA đang cân nhắc bảo lưu kết quả, sau đó tiếp tục học hoặc thôi học: mỗi trường hợp dùng đơn nào trong catalog, khác nhau thế nào?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 10-Don, 11-Don, 12-Don, bảo lưu

---

### L4-08 — CNTT + thực tập + đồ án

**Câu hỏi (copy):**
```text
Sinh viên ngành CNTT KMA: mã ngành, hướng CDIO, đơn đăng ký đồ án lần 2 và giấy giới thiệu thực tập — tên file và mục đích từng biểu mẫu.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh, bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 7.48.01.01, 7.48, 17-Don, 18-Giay, CDIO

---

### L4-09 — Ưu tiên nhập học + MBank

**Câu hỏi (copy):**
```text
Thủ tục nhập học KMA 2024: các khoản phí bắt buộc (học phí HK1 tạm thu, BHYT, thư viện, thẻ SV, khám SK), tài khoản ngân hàng nhận tiền, hướng dẫn mở tài khoản MBank và mẫu đăng ký TK MBank.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 9.000.000, 9.000, MBank, 26-Dang_ky, 10.896, nhập học

---

### L4-10 — HK điểm + tra cứu

**Câu hỏi (copy):**
```text
Bảng điểm học kỳ 1 năm 2024-2025 đợt 2 của KMA gồm những học phần/khóa nào, file PDF tên gì, và sinh viên tra cứu điểm cá nhân theo MSSV cần lưu ý gì?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** hk1_20242025_dot2, hk1, 2024-2025, đợt 2, MSSV, bảng điểm

---

## L5 — Nhiều lượt hội thoại (12 câu)

### L5-01 — Follow-up biểu mẫu

*Gửi lần lượt các lượt trong CÙNG một cửa sổ chat (không F5).*

#### Lượt 1

**Câu hỏi (copy):**
```text
Cho tôi biết đơn xin nghỉ học dưới 7 ngày của KMA.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).

#### Lượt 2

**Câu hỏi (copy):**
```text
Còn nếu nghỉ trên 7 ngày thì sao?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 09-Don, trên 7, 7 ngày

---

### L5-02 — Follow-up tuyển sinh

*Gửi lần lượt các lượt trong CÙNG một cửa sổ chat (không F5).*

#### Lượt 1

**Câu hỏi (copy):**
```text
Điểm trúng tuyển CNTT Hà Nội năm 2024 của KMA?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).

#### Lượt 2

**Câu hỏi (copy):**
```text
Còn an toàn thông tin thì điểm bao nhiêu?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 25.90, 25.95, 25,95, ATTT, an toàn

---

### L5-03 — Follow-up ma trận

*Gửi lần lượt các lượt trong CÙNG một cửa sổ chat (không F5).*

#### Lượt 1

**Câu hỏi (copy):**
```text
Ma trận đề thi Tin học đại cương có bao nhiêu câu?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **ma_tran** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 50, câu

#### Lượt 2

**Câu hỏi (copy):**
```text
Thời gian làm bài là bao lâu?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **ma_tran** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 60, 90, phút, giờ

---

### L5-04 — Đổi mảng giữa phiên

*Gửi lần lượt các lượt trong CÙNG một cửa sổ chat (không F5).*

#### Lượt 1

**Câu hỏi (copy):**
```text
Chuẩn TOEIC trước khi làm đồ án tốt nghiệp KMA?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 450, TOEIC, toeic, đồ án

#### Lượt 2

**Câu hỏi (copy):**
```text
Giờ cho tôi mẫu đơn phúc khảo bài thi.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** phúc khảo, 15-Don, phuc khao

---

### L5-05 — Đại từ — điền đơn

*Gửi lần lượt các lượt trong CÙNG một cửa sổ chat (không F5).*

#### Lượt 1

**Câu hỏi (copy):**
```text
Tôi cần giấy xác nhận sinh viên để vay vốn ngân hàng.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).

#### Lượt 2

**Câu hỏi (copy):**
```text
Điền giúp tôi đơn đó được không?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** điền, mục, họ tên, xác nhận

---

### L5-06 — Follow-up điểm MSSV

*Gửi lần lượt các lượt trong CÙNG một cửa sổ chat (không F5).*

#### Lượt 1

**Câu hỏi (copy):**
```text
CT060310 điểm học kỳ 2 năm 2024-2025 đợt 1
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi** (gợi ý, không cần đúng pipeline).

#### Lượt 2

**Câu hỏi (copy):**
```text
Liệt kê các môn và điểm của bạn ấy.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** CT060310

---

### L5-07 — Off-topic chen giữa

*Gửi lần lượt các lượt trong CÙNG một cửa sổ chat (không F5).*

#### Lượt 1

**Câu hỏi (copy):**
```text
Quy định miễn thi chuẩn tiếng Anh đầu ra KMA?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).

#### Lượt 2

**Câu hỏi (copy):**
```text
Cho em hỏi giá Bitcoin hôm nay?
```

**Câu trả lời đúng cần có:**

- Từ chối nhẹ — câu ngoài phạm vi KMA. Gợi ý hỏi đúng mảng (tuyển sinh, quy chế, …).

#### Lượt 3

**Câu hỏi (copy):**
```text
Vậy TOEIC tối thiểu trước đồ án là bao nhiêu?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 450

---

### L5-08 — Hai mảng trong phiên

*Gửi lần lượt các lượt trong CÙNG một cửa sổ chat (không F5).*

#### Lượt 1

**Câu hỏi (copy):**
```text
Em cần biết điểm trúng tuyển CNTT 2024 và học phí tạm thu HK1 khi nhập học.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh, bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 26.20, 26.60, 10.896, tuyển sinh

#### Lượt 2

**Câu hỏi (copy):**
```text
Tóm lại em phải chuẩn bị bao nhiêu tiền mặt theo hướng dẫn nhập học?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 10.896, 10896940

---

## L6 — Biểu mẫu / điền đơn (6 câu)

### L6-01 — Catalog BHYT ATTT

**Câu hỏi (copy):**
```text
Trong catalog biểu mẫu KMA, mẫu khai BHYT sinh viên ATTT và file hướng dẫn khai BHYT tên gì?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 24-Mau_khai_BHYT, 25-Huong_dan_khai_BHYT

---

### L6-02 — Điền đơn xác nhận SV

**Câu hỏi (copy):**
```text
Điền giúp tôi giấy xác nhận sinh viên.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** điền, mục, họ tên, xác nhận

---

### L6-03 — Tải đơn bảo lưu

**Câu hỏi (copy):**
```text
Tôi muốn tải đơn bảo lưu kết quả học tập — cho tên file trong catalog KMA.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 10-Don_bao_luu, bảo lưu

---

### L6-04 — Điểm chuẩn — routing negative

**Câu hỏi (copy):**
```text
Điểm chuẩn ngành DTVT năm 2024 của KMA?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 24.5, 24,5, 25.0, 25.35, DTVT

---

## L1 — Đơn giản — một mảng (20 câu)

### L1-15 — SĐT tuyển sinh

**Câu hỏi (copy):**
```text
Số điện thoại liên hệ tuyển sinh KMA trong đề án 2025?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có:** 0986622772
- **Tài liệu tham chiếu:** 01_de_an_tuyen_sinh_2025.pdf

---

### L1-16 — Phương thức TS 2025

**Câu hỏi (copy):**
```text
Phương thức tuyển sinh đại học chính quy KMA năm 2025 là gì?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** xét tuyển, THPT
- **Tài liệu tham chiếu:** 01_de_an_tuyen_sinh_2025.pdf

---

## L2 — Trung bình — liệt kê, so sánh, tra điểm MSSV (22 câu)

### L2-17 — Điểm trúng tuyển CNTT 2024

**Câu hỏi (copy):**
```text
Điểm trúng tuyển ngành Công nghệ thông tin (Hà Nội) năm 2024 theo đề án KMA?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có:** 26.20 · 26.60

---

### L2-18 — KTX nhập học

**Câu hỏi (copy):**
```text
Học viện có ký túc xá cho sinh viên hệ đóng học phí khi nhập học không?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** không có, Ký túc xá
- **Tài liệu tham chiếu:** Thu_tuc_nhap_hoc_2024.pdf

---

## L3 — Hai mảng trở lên (17 câu)

### L3-13 — Điểm DTVT + phiếu ra trường

**Câu hỏi (copy):**
```text
Điểm trúng tuyển ngành Điện tử viễn thông 2025 và mẫu phiếu thanh toán ra trường cá nhân 2026 trong tài liệu KMA?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh, bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** DTVT, thanh toán, ra trường, trúng tuyển

---

### L3-14 — Ma trận kiểm thử + quy chế

**Câu hỏi (copy):**
```text
Môn Kiểm thử an toàn hệ thống thông tin thuộc ma trận nào? Quy chế đào tạo 2025 áp dụng cho cơ sở Hà Nội và TP.HCM không?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **ma_tran, khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** Kiểm thử, Phân hiệu, Hà Nội, TP.HCM

---

## L4 — Câu dài / nhiều ý (15 câu)

### L4-11 — Ba mảng tân SV

**Câu hỏi (copy):**
```text
Tân sinh viên KMA: điểm chuẩn CNTT 2024, tổng tiền nhập học 2024, và mẫu đơn đăng ký học — trả lời từng phần theo tài liệu.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh, bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 26.20, 26.60, 10.896, 04-Don, nhập học

---

### L4-12 — Chuẩn NN đầy đủ

**Câu hỏi (copy):**
```text
Tổng hợp: TOEIC sau TA1, TA2, TA3, trước đồ án và điều kiện công nhận VSTEP theo quy định chuẩn ngoại ngữ KMA.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 300, 350, 450, VSTEP

---

## L5 — Nhiều lượt hội thoại (12 câu)

### L5-09 — Điểm chuẩn follow-up

*Gửi lần lượt các lượt trong CÙNG một cửa sổ chat (không F5).*

#### Lượt 1

**Câu hỏi (copy):**
```text
Điểm chuẩn ngành CNTT năm 2024 của KMA?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).

#### Lượt 2

**Câu hỏi (copy):**
```text
Năm 2023 thì sao?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 25.5, 25,5, 2023

---

### L5-10 — MSSV + học kỳ follow-up

*Gửi lần lượt các lượt trong CÙNG một cửa sổ chat (không F5).*

#### Lượt 1

**Câu hỏi (copy):**
```text
CT060310 điểm học kỳ 2 năm 2024-2025 đợt 1
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi** (gợi ý, không cần đúng pipeline).

#### Lượt 2

**Câu hỏi (copy):**
```text
Có môn nào không đạt không?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** CT060310, Không đạt, không đạt, Đạt, đạt

---

## L0 — Guardrail — chào / off-topic (8 câu)

### L0-07 — Tạm biệt

**Câu hỏi (copy):**
```text
Tạm biệt nhé, hẹn gặp lại!
```

**Câu trả lời đúng cần có:**

- Chào hỏi / giới thiệu trợ lý KMA và các mảng hỗ trợ. Không tra cứu tài liệu.

---

### L0-08 — Off-topic y tế

**Câu hỏi (copy):**
```text
Thuốc hạ sốt cho trẻ 5 tuổi uống liều bao nhiêu?
```

**Câu trả lời đúng cần có:**

- Từ chối nhẹ — câu ngoài phạm vi KMA. Gợi ý hỏi đúng mảng (tuyển sinh, quy chế, …).

---

## L1 — Đơn giản — một mảng (20 câu)

### L1-17 — Địa chỉ PHCM

**Câu hỏi (copy):**
```text
Địa chỉ Phân hiệu KMA tại TP.HCM theo đề án tuyển sinh 2025?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** Cộng Hòa, Tân Bình, TP.HCM
- **Tài liệu tham chiếu:** 01_de_an_tuyen_sinh_2025.pdf

---

### L1-18 — Phân hiệu quy chế

**Câu hỏi (copy):**
```text
Quy chế đào tạo KMA 2025 có áp dụng cho Phân hiệu TP.HCM không?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** Phân hiệu, Hồ Chí Minh, Hà Nội
- **Tài liệu tham chiếu:** 25_quy_che_dao_tao_dai_hoc_2025.pdf

---

### L1-19 — Đơn cấp lại thẻ SV

**Câu hỏi (copy):**
```text
Sinh viên mất thẻ sinh viên cần đơn nào trong catalog KMA?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 06-Don_cap_lai_the, thẻ sinh viên

---

### L1-20 — Ma trận ATHT

**Câu hỏi (copy):**
```text
Môn Kiểm thử an toàn hệ thống thông tin có trong ma trận đề thi KMA không?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **ma_tran** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** Kiểm thử, an toàn, ma trận
- **Tài liệu tham chiếu:** 20_ma_tran_kiem_thu_athttt.pdf

---

## L2 — Trung bình — liệt kê, so sánh, tra điểm MSSV (22 câu)

### L2-19 — Cú pháp chuyển khoản

**Câu hỏi (copy):**
```text
Cú pháp nộp kinh phí nhập học vào tài khoản MB theo hướng dẫn KMA 2024?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 0021145666888, Mã trúng tuyển
- **Tài liệu tham chiếu:** Thu_tuc_nhap_hoc_2024.pdf

---

### L2-20 — Kết quả CT4

**Câu hỏi (copy):**
```text
Tài liệu kết quả tốt nghiệp CT4 năm 2024 của KMA dùng để tra cứu thông tin gì?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** CT4, tốt nghiệp, kết quả
- **Tài liệu tham chiếu:** 04_ket_qua_tot_nghiep_ct4_2024.pdf

---

### L2-21 — Chỉ tiêu CNTT 2025

**Câu hỏi (copy):**
```text
Chỉ tiêu tuyển sinh ngành Công nghệ thông tin năm 2025 của KMA là bao nhiêu?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** chỉ tiêu, CNTT, Công nghệ thông tin
- **Tài liệu tham chiếu:** 01_de_an_tuyen_sinh_2025.pdf

---

### L2-22 — Miễn thi NN

**Câu hỏi (copy):**
```text
Sinh viên có thể được miễn thi chuẩn tiếng Anh đầu ra theo quy định KMA trong trường hợp nào?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).
- **Tài liệu tham chiếu:** 03_quy_dinh_chuan_ngoai_ngu_2025.pdf

---

## L3 — Hai mảng trở lên (17 câu)

### L3-15 — Thi TN + đơn phúc khảo

**Câu hỏi (copy):**
```text
KMA có hướng dẫn thi tốt nghiệp online không? Và sinh viên phúc khảo bài thi dùng đơn nào trong catalog?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi, bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** thi tốt nghiệp, phúc khảo, 15-Don, online

---

### L3-16 — Điểm chuẩn + quy chế tín chỉ

**Câu hỏi (copy):**
```text
Điểm trúng tuyển ngành An toàn thông tin Hà Nội năm 2024? Quy chế đào tạo 2025 quy định chương trình học theo đơn vị gì?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh, khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 25.90, 25.95, tín chỉ, an toàn

---

### L3-17 — Catalog thực tập + CDIO

**Câu hỏi (copy):**
```text
Tên file giấy giới thiệu thực tập trong catalog KMA? Chương trình CNTT được xây dựng theo hướng tiếp cận nào?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau, tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 18-Giay, CDIO, thực tập

---

## L4 — Câu dài / nhiều ý (15 câu)

### L4-13 — Nhập học đầy đủ

**Câu hỏi (copy):**
```text
Tân sinh viên KMA 2024: tổng tiền nhập học, có ký túc xá không, cú pháp chuyển khoản MB và mẫu đăng ký tài khoản MBank — trả lời theo hướng dẫn nhập học.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 10.896, MBank, 26-Dang_ky, 0021145666888

---

### L4-14 — So sánh 3 ngành TS

**Câu hỏi (copy):**
```text
So sánh điểm trúng tuyển năm 2024 của ngành CNTT, An toàn thông tin và Điện tử viễn thông (cơ sở Hà Nội) theo đề án tuyển sinh KMA.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **tuyen_sinh** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 26.20, 26.60, 25.90, 25.95, 25.0, 25.35

---

### L4-15 — Điểm + đơn + ma trận

**Câu hỏi (copy):**
```text
Sinh viên AT200106 đạt tiếng Anh đầu vào 2024 chưa? Đơn xin hoãn thi tên file gì? Ma trận Tin học đại cương có bao nhiêu câu và thời gian thi?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **diem_thi, bieu_mau, ma_tran** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** AT200106, 14-Don, 50, 60, hoãn

---

## L5 — Nhiều lượt hội thoại (12 câu)

### L5-11 — Follow-up khao_thi

*Gửi lần lượt các lượt trong CÙNG một cửa sổ chat (không F5).*

#### Lượt 1

**Câu hỏi (copy):**
```text
TOEIC tối thiểu sau Tiếng Anh 1 của KMA là bao nhiêu?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).

#### Lượt 2

**Câu hỏi (copy):**
```text
Còn sau Tiếng Anh 2 thì sao?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **khao_thi** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 350, 3

---

### L5-12 — Form → hủy

*Gửi lần lượt các lượt trong CÙNG một cửa sổ chat (không F5).*

#### Lượt 1

**Câu hỏi (copy):**
```text
Điền giúp tôi đơn xin nghỉ học dưới 7 ngày.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).

#### Lượt 2

**Câu hỏi (copy):**
```text
Thôi, hủy đi.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** hủy, dừng, thôi, bỏ

---

## L6 — Biểu mẫu / điền đơn (6 câu)

### L6-05 — Đơn đăng ký học

**Câu hỏi (copy):**
```text
Trong catalog KMA, đơn đăng ký học tên file gì?
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** 04-Don_dang_ky_hoc

---

### L6-06 — Điền đơn phúc khảo

**Câu hỏi (copy):**
```text
Điền giúp tôi đơn xin phúc khảo bài thi.
```

**Câu trả lời đúng cần có:**

- Mảng phù hợp: **bieu_mau** (gợi ý, không cần đúng pipeline).
- **Phải có (một trong):** điền, phúc khảo, mục

---

*Nguồn máy đọc: `eval/benchmark.json` · Chấm tự động nội dung: `python eval/run_benchmark.py`*