# Case PASS — copy vào web test (demo thực tế)

> Nguồn: [`run_20260521_230117.json`](results/run_20260521_230117.json) — chạy `20260521_230117`.  
> **10/17** case pass trong lần chạy này (chỉ tier **L4, L5, L6** từ `L4-08` trở đi, không phải full 80 case).  
> **Cách test:** http://127.0.0.1:8000 → dán câu vào chat. Case **L5:** gửi đủ lượt **trong cùng một** cửa sổ (không bấm **+** giữa chừng).

## Mục lục nhanh

| ID | Tier | Lượt |
|----|------|------|
| [L4-08](#l4-08-l4) | L4 | 1 |
| [L4-10](#l4-10-l4) | L4 | 1 |
| [L5-01](#l5-01-l5) | L5 | 2 |
| [L5-02](#l5-02-l5) | L5 | 2 |
| [L5-06](#l5-06-l5) | L5 | 2 |
| [L5-08](#l5-08-l5) | L5 | 3 |
| [L6-01](#l6-01-l6) | L6 | 1 |
| [L6-02](#l6-02-l6) | L6 | 1 (form fill) |
| [L6-03](#l6-03-l6) | L6 | 1 |
| [L6-04](#l6-04-l6) | L6 | 1 |

---

## L4-08 (L4)

**Tiêu đề benchmark:** CNTT + thực tập + đồ án  
**Khi test nên thấy (ít nhất một):** `7.48.01.01`, `17-Don`, `18-Giay`, CDIO; agent `tuyen_sinh` + `bieu_mau`.

**Copy — một lượt:**

```text
Sinh viên ngành CNTT KMA: mã ngành, hướng CDIO, đơn đăng ký đồ án lần 2 và giấy giới thiệu thực tập — tên file và mục đích từng biểu mẫu.
```

*Lần chạy script:* có mã ngành **7.48.01.01**, CDIO; phần tên file đơn thực tập có thể “chưa có trong tài liệu” — vẫn pass vì có `7.48.01.01`.

---

## L4-10 (L4)

**Tiêu đề benchmark:** Ưu tiên nhập học + MBank  
**Khi test nên thấy:** `9.000.000`, `1.031.940`, `500.000`, `MBank`, `26-Dang_ky`; tổng **10.896.940** VNĐ.

**Copy — một lượt:**

```text
Thủ tục nhập học KMA 2024: các khoản phí bắt buộc (học phí HK1 tạm thu, BHYT, thư viện, thẻ SV, khám SK), tài khoản ngân hàng nhận tiền, hướng dẫn mở tài khoản MBank và mẫu đăng ký TK MBank.
```

---

## L5-01 (L5)

**Tiêu đề benchmark:** Follow-up biểu mẫu  
**Khi test nên thấy:** Lượt 1 — đơn **dưới 7 ngày**; lượt 2 — đơn **trên 7 ngày** (bot hiểu “còn nếu…”).

### Lượt 1

```text
Cho tôi biết đơn xin nghỉ học dưới 7 ngày của KMA.
```

### Lượt 2 *(cùng cửa sổ chat)*

```text
Còn nếu nghỉ trên 7 ngày thì sao?
```

---

## L5-02 (L5)

**Tiêu đề benchmark:** Follow-up tuyển sinh  
**Khi test nên thấy:** Lượt 1 — CNTT HN 2024 ~**26.10**; lượt 2 — ATTT ~**25.95**.

### Lượt 1

```text
Điểm trúng tuyển CNTT Hà Nội năm 2024 của KMA?
```

### Lượt 2

```text
Còn an toàn thông tin thì điểm bao nhiêu?
```

---

## L5-06 (L5)

**Tiêu đề benchmark:** Chi tiết thêm quy chế  
**Khi test nên thấy:** Quy chế 2025 áp dụng cho ai; lượt 2 giải thích **học phần**, **tín chỉ**.

### Lượt 1

```text
Quy chế đào tạo đại học KMA 2025 áp dụng cho ai?
```

### Lượt 2

```text
Giải thích thêm về học phần và tín chỉ.
```

---

## L5-08 (L5)

**Tiêu đề benchmark:** Ba câu nhỏ một phiên  
**Khi test nên thấy:** `KMA`; SĐT tuyển sinh **0986622772**; PHCM **Cộng Hòa** / **Tân Bình**.

### Lượt 1

```text
Mã trường KMA?
```

### Lượt 2

```text
Số điện thoại tuyển sinh?
```

### Lượt 3

```text
Phân hiệu TP.HCM ở đâu?
```

---

## L6-01 (L6)

**Tiêu đề benchmark:** Catalog BHYT ATTT  
**Khi test nên thấy:** `24-Mau_khai_BHYT`, `25-Huong_dan_khai_BHYT`.

**Copy — một lượt:**

```text
Trong catalog biểu mẫu KMA, mẫu khai BHYT sinh viên ATTT và file hướng dẫn khai BHYT tên gì?
```

---

## L6-02 (L6)

**Tiêu đề benchmark:** Điền đơn xác nhận SV  
**Pipeline:** `form_fill` — bot hỏi **từng mục** (họ tên, SĐT, …), không phải RAG một câu.

**Copy — một lượt:**

```text
Điền giúp tôi giấy xác nhận sinh viên.
```

*Gợi ý:* Trả lời lần lượt từng field bot hỏi (hoặc demo vài mục) để thấy luồng điền đơn.

---

## L6-03 (L6)

**Tiêu đề benchmark:** Tải đơn bảo lưu  
**Khi test nên thấy:** `10-Don_bao_luu`, từ **bảo lưu**, link/tên file.

**Copy — một lượt:**

```text
Tôi muốn tải đơn bảo lưu kết quả học tập — cho link hoặc tên file trong hệ thống KMA.
```

---

## L6-04 (L6)

**Tiêu đề benchmark:** So sánh đơn nghỉ  
**Khi test nên thấy:** `08-Don`, `09-Don`, **7 ngày** (dưới / trên).

**Copy — một lượt:**

```text
Khác nhau giữa đơn nghỉ học dưới 7 ngày và trên 7 ngày của KMA?
```

---

## Case FAIL trong cùng lần chạy (không dùng làm demo “chắc đúng”)

| ID | Ghi chú ngắn |
|----|----------------|
| L4-09 | Trả “không tìm thấy” — retrieve sai file điểm (hk2 thay vì hk1 đợt 2) |
| L5-03 | Lượt 2 thiếu fact benchmark (60 phút vs kỳ vọng khác) |
| L5-04 | Lượt 1 thiếu gold TOEIC 450 |
| L5-05 | Lượt 1 catalog; lượt 2 form pass riêng |
| L5-07 | MSSV / điểm TA |
| L5-09 | Lượt 2 off-topic; lượt 3 có thể pass riêng |
| L5-10 | Tổng hợp tuyển sinh + học phí |

---

## Tạo lại file này sau lần chạy mới

```bash
cd demo
python eval/gen_passed_md.py eval/results/run_<timestamp>.json eval/passed_cases_demo_<timestamp>.md
```

Sau khi chạy full benchmark, đổi tên file hoặc mở file `.md` mới tương ứng `run_*.json`.
