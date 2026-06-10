# Mẫu mục 4.3 — dán vào Word (kết quả thực nghiệm mới: 90/100)

*Nguồn số: lần đánh giá 100 câu, 04/06/2026. Không đưa tên file kỹ thuật vào báo cáo.*

---

## 4.3 Thử nghiệm và đánh giá hệ thống

### 4.3.1 Mô tả bộ dữ liệu thực nghiệm

#### 4.3.1.1. Cấu trúc bộ dữ liệu

Nhằm đánh giá hệ thống đa tác tử đã xây dựng, quá trình thực nghiệm được tiến hành trên một tập dữ liệu được chuẩn bị trước. Bộ dữ liệu sử dụng trong quá trình thực nghiệm bao gồm các truy vấn mẫu được xây dựng dựa trên các tình huống thực tế mà người dùng có thể gặp khi tìm kiếm thông tin học vụ tại Học viện Kỹ thuật Mật mã. Do đặc trưng của hệ thống đa tác tử, bộ dữ liệu được chia thành hai nhóm chính:

- **Nhóm câu hỏi có đầu ra xác định (N1):** câu hỏi tra cứu thông tin cụ thể, có kết quả kiểm chứng được bằng đối chiếu trực tiếp. Ví dụ: điểm theo mã sinh viên, điểm chuẩn tuyển sinh, tên biểu mẫu, số tiền nhập học, ngưỡng TOEIC theo quy chế.

- **Nhóm câu hỏi có đầu ra mở (N2):** câu hỏi yêu cầu tổng hợp, giải thích hoặc so sánh; câu trả lời có thể diễn đạt theo nhiều cách nhưng vẫn phải bám tài liệu KMA. Ví dụ: quy trình thủ tục, so sánh hai loại đơn, câu đa nghiệp vụ (tuyển sinh kèm biểu mẫu), hội thoại nhiều lượt.

Đối với nhóm N1, phép đo độ chính xác có thể thực hiện tự động bằng đối chiếu các thông tin bắt buộc (số liệu, mã sinh viên, tên mẫu đơn) trong câu trả lời. Đối với nhóm N2, tiêu chí chính vẫn là **Pass/Fail** theo các điểm nội dung bắt buộc đã đặt trước cho từng kịch bản (không dùng chỉ số Context Relevance riêng trong lần đo này).

Mỗi dòng trong bộ dữ liệu thực nghiệm được biểu diễn như Bảng 4.1.

**Bảng 4.1** *Bảng mô tả ý nghĩa các trường của bộ dữ liệu thực nghiệm*

| Tên trường | Ý nghĩa |
|------------|---------|
| Mã kịch bản | Định danh duy nhất của câu hỏi thử nghiệm. |
| Câu hỏi | Nội dung truy vấn gửi tới hệ thống (một hoặc nhiều lượt hội thoại). |
| Thông tin bắt buộc | Các số liệu, từ khóa hoặc cụm nội dung phải có trong câu trả lời đúng. |
| Kỳ vọng định tuyến | Tác tử chuyên môn và phạm vi xử lý (một tác tử, đa tác tử, tra cứu điểm, biểu mẫu). |
| Mức độ phức tạp | Phân loại theo mức L0–L6 (bảng phân bổ ở mục 4.3.1.2). |

#### 4.3.1.2. Chuẩn bị dữ liệu

Để thực hiện đánh giá hệ thống, bộ dữ liệu thực nghiệm gồm **100 câu hỏi**, trong đó **55 câu** thuộc nhóm N1 và **45 câu** thuộc nhóm N2 (giữ cấu trúc phân nhóm như thiết kế ban đầu). Các câu hỏi được thiết kế với độ phức tạp tăng dần, từ những câu chỉ cần một bước truy xuất (điểm theo mã sinh viên, tên file biểu mẫu) đến những câu cần Planner phân rã thành nhiều truy vấn con và kích hoạt đồng thời nhiều tác tử chuyên biệt.

Đồng thời, toàn bộ 100 kịch bản được gán **mức độ phức tạp kỹ thuật** để phân tích kết quả theo từng lớp xử lý của hệ thống:

| Mức | Số câu | Đặc điểm |
|-----|--------|----------|
| L0 | 8 | Guardrail: chào hỏi, ngoài phạm vi, không RAG. |
| L1 | 20 | Một tác tử, tra cứu đơn giản. |
| L2 | 22 | Trung bình: liệt kê, so sánh, tra cứu điểm theo MSSV. |
| L3 | 17 | Một câu, nhiều tác tử. |
| L4 | 15 | Câu dài, Planner, đa tác tử phức tạp. |
| L5 | 12 | Hội thoại nhiều lượt. |
| L6 | 6 | Catalog và điền biểu mẫu. |

Bảng 4.2 và Bảng 4.3 thể hiện ví dụ một số câu hỏi trong bộ dữ liệu thực nghiệm.

**Bảng 4.2** *Một số câu hỏi nhóm N1 trong bộ dữ liệu thực nghiệm*

| STT | Câu hỏi | Thông tin bắt buộc trong câu trả lời đúng |
|-----|---------|---------------------------------------------|
| 1 | Mã trường KMA trong đề án tuyển sinh 2025 là gì? | KMA |
| 2 | Sinh viên cần đạt tối thiểu bao nhiêu điểm TOEIC khi kết thúc Tiếng Anh 1? | 300 |
| 3 | Môn Tin học đại cương có bao nhiêu câu trắc nghiệm theo ma trận đề thi? | 50 |
| 4 | Tổng số tiền phải nộp khi làm thủ tục nhập học KMA 2024? | 10.896.940 |
| 5 | CT060310 điểm học kỳ 2 năm 2024–2025 đợt 1 | CT060310; có điểm từng môn |
| 6 | Sinh viên AT200106 có đạt phân loại tiếng Anh đầu vào A20C8D7 2024 lần 2 không? | ĐẠT; AT200106 |

**Bảng 4.3** *Một số câu hỏi nhóm N2 trong bộ dữ liệu thực nghiệm*

| Câu hỏi | Thông tin bắt buộc / nội dung cần có |
|---------|--------------------------------------|
| Quy định về điều kiện được dự thi kết thúc học phần tại KMA. | Tham dự ≥ 80% giờ lý thuyết; không bị đình chỉ học tập/thi; hoàn thành yêu cầu thực hành. |
| So sánh điểm trúng tuyển ngành An toàn thông tin (Hà Nội) năm 2023 và 2024. | 25,60 (2023); 25,90 (2024); nhận xét tăng/giảm. |

Dữ liệu nghiệp vụ là tài liệu KMA đã nạp vào kho tri thức vector trước khi chạy thực nghiệm.

---

### 4.3.2 Kịch bản thực nghiệm

Việc đo lường các chỉ số là quan trọng để đánh giá mức độ hiệu quả của hệ thống đa tác tử. Việc đánh giá tập trung vào chất lượng và độ chính xác của hệ thống AI cốt lõi, không tính đến các yếu tố giao diện người dùng. Phần thực nghiệm tập trung đo lường nhằm xác định các tiêu chí sau:

- Độ chính xác (Accuracy / Pass rate).
- Độ bao phủ nội dung (Recall) — áp dụng mô tả định tính trên các câu đa ý.
- Thời gian phản hồi (Latency).

#### 4.3.2.1. Accuracy

Accuracy hay độ chính xác là tiêu chí cốt lõi phản ánh tính đúng đắn của câu trả lời. Với mỗi câu truy vấn, kết quả đánh giá nhị phân gồm hai trạng thái: **Pass** khi câu trả lời thỏa đồng thời (i) định tuyến đúng tác tử theo kỳ vọng và (ii) chứa đủ thông tin bắt buộc; **Fail** khi thiếu hoặc sai. Độ chính xác tổng thể được tính:

$$\text{Accuracy} = \frac{\text{Số câu trả lời Pass}}{\text{Tổng số câu truy vấn}} \times 100\%$$

Quá trình kiểm tra được thực hiện **tự động** bằng chương trình đánh giá nội bộ, đối chiếu câu trả lời với bộ thông tin bắt buộc đã khai báo cho từng kịch bản.

#### 4.3.2.2. Recall

Recall hay độ bao phủ phản ánh khả năng câu trả lời không bỏ sót các ý quan trọng. Với câu hỏi nhiều ý (liệt kê, đa tác tử), Recall được hiểu là tỷ lệ các điểm nội dung bắt buộc xuất hiện trong câu trả lời so với tổng số điểm cần có. Trong báo cáo này, Recall được **diễn giải cùng tiêu chí Pass** trên từng kịch bản (mỗi kịch bản đã liệt kê tập từ khóa/số liệu cần có); không tách bảng Recall riêng ngoài Accuracy.

#### 4.3.2.3. Latency

Latency là chỉ số thể hiện tốc độ phản hồi của hệ thống, tính bằng tổng thời gian từ khi nhận câu hỏi đến khi nhận được câu trả lời hoàn chỉnh (đơn vị: giây). Thời gian phụ thuộc pipeline (Guardrail, RAG đơn, đa tác tử, tra cứu điểm, hội thoại nhiều lượt).

---

### 4.3.3 Tiến hành thực nghiệm

Thực nghiệm được tiến hành thông qua chương trình đánh giá tự động. Mỗi câu hỏi được gửi tuần tự tới API hội thoại của hệ thống, thu thập câu trả lời, tác tử được kích hoạt, pipeline thực tế và thời gian xử lý. Các bước:

- **Bước 1:** Nạp bộ 100 kịch bản thử nghiệm.
- **Bước 2:** Với mỗi câu hỏi, gửi truy vấn tới hệ thống và ghi nhận Pass/Fail, danh sách tác tử, pipeline và Latency.
- **Bước 3:** Lặp cho đến hết 100 câu.
- **Bước 4:** Tổng hợp kết quả theo toàn bộ tập dữ liệu và theo từng mức L0–L6.

Môi trường: máy trạm cài đặt hệ thống chatbot, kho vector đã đồng bộ tài liệu KMA, mô hình ngôn ngữ cấu hình cho các tác tử. Thời điểm chạy đánh giá đầy đủ: **04/06/2026**.

---

### 4.3.4 Kết quả thực nghiệm

#### 4.3.4.1. Kết quả thực nghiệm

Sau quá trình thực nghiệm trên 100 câu, hệ thống đạt **độ chính xác tổng thể 90,0%** (90 câu Pass, 10 câu Fail). Kết quả chi tiết theo mức phức tạp và theo thời gian phản hồi được trình bày tại Bảng 4.4 và Bảng 4.5.

**Bảng 4.4** *Kết quả độ chính xác (Pass rate) theo mức phức tạp — 100 kịch bản*

| Mức | Số câu | Số câu Pass | Tỉ lệ Pass (%) |
|-----|--------|-------------|----------------|
| L0 | 8 | 8 | 100,0 |
| L1 | 20 | 19 | 95,0 |
| L2 | 22 | 17 | 77,3 |
| L3 | 17 | 16 | 94,1 |
| L4 | 15 | 14 | 93,3 |
| L5 | 12 | 10 | 83,3 |
| L6 | 6 | 6 | 100,0 |
| **Tổng** | **100** | **90** | **90,0** |

**Bảng 4.5** *Kết quả thời gian phản hồi (Latency) theo mức phức tạp — đơn vị: giây*

| Mức | Trung bình | Tối thiểu | Tối đa |
|-----|------------|-----------|--------|
| L0 | 0,5 | 0,0 | 2,0 |
| L1 | 17,5 | 5,1 | 30,4 |
| L2 | 17,3 | 4,5 | 29,8 |
| L3 | 25,1 | 7,5 | 40,1 |
| L4 | 24,6 | 6,9 | 37,8 |
| L5 | 25,8 | 0,1 | 51,0 |
| L6 | 9,3 | 0,1 | 16,8 |
| **Toàn bộ** | **18,9** | **0,0** | **51,0** |

*Nhận xét ngắn gắn trên bảng:* độ chính xác **tổng thể 90%** đạt trên toàn bộ 100 kịch bản; các mức L0, L1, L3, L4, L6 đều trên 93% trừ L2 và L5; thời gian phản hồi trung bình toàn tập khoảng **19 giây**, mức L0 gần như tức thời, mức L3–L5 cao hơn do xử lý đa tác tử và hội thoại dài.

#### 4.3.4.2. Đánh giá

Từ kết quả thực nghiệm, có thể rút ra các nhận xét sau:

- Hệ thống đạt **độ chính xác 90%** trên bộ 100 câu, cho thấy định tuyến đa tác tử kết hợp RAG trên tài liệu KMA đáp ứng tốt phần lớn nhu cầu tra cứu học vụ mô phỏng.

- Các mức **L0** (Guardrail) và **L6** (biểu mẫu) đạt **100%**, phù hợp thiết kế lớp kiểm soát phạm vi và luồng thủ tục có cấu trúc rõ.

- Các mức **L1, L3, L4** đạt trên **93%**, thể hiện khả năng xử lý câu đơn và câu đa nghiệp vụ (có Planner) ổn định.

- Mức **L2** (77,3%) và **L5** (83,3%) thấp hơn mức trung bình chung: L2 liên quan so sánh biểu mẫu, tra cứu điểm theo học kỳ; L5 phụ thuộc ngữ cảnh nhiều lượt. Đây là hướng cải thiện trong giai đoạn sau.

- **Latency** trung bình **18,9 giây**/câu; câu đơn giản (L0, L6) phản hồi nhanh; câu đa tác tử và multi-turn (L3–L5) chậm hơn, tối đa khoảng **51 giây** do nhiều vòng xử lý.

- Mười câu Fail tập trung ở tra cứu điểm chưa đủ chi tiết, so sánh đơn nghỉ, một số câu đa tác tử và hội thoại dài — chủ yếu do thiếu đúng cụm thông tin bắt buộc trong câu trả lời, không phải lỗi hạ tầng.

---

## 4.4 (đoạn gợi ý — đồng bộ số 90%)

Chương 4 trình bày triển khai và đánh giá hệ thống trợ lý ảo đa tác tử trên **100 kịch bản** thực tế. Kết quả thực nghiệm cho thấy hệ thống đạt **độ chính xác 90%**, với hiệu năng tốt ở lớp Guardrail, tra cứu đơn và đa tác tử; các mức trung bình (L2) và hội thoại nhiều lượt (L5) là hướng tinh chỉnh tiếp theo. Thời gian phản hồi trung bình khoảng **19 giây**, phù hợp bài toán tra cứu tài liệu học vụ có RAG.

---

## Kết luận chương (một câu gợi ý)

Đề tài đạt **90%** độ chính xác trên bộ thử nghiệm 100 câu, chứng minh khả năng ứng dụng hệ thống đa tác tử trong hỗ trợ sinh viên KMA.
