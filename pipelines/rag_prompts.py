"""
Prompt RAG dùng chung — chế độ chuẩn và chế độ ưu tiên độ chính xác.
"""

from config import ACCURACY_MODE

RAG_PROMPT_BASE = """\
Dựa vào các đoạn tài liệu dưới đây của Học viện Kỹ thuật Mật mã (KMA), hãy trả lời câu hỏi một cách đầy đủ và chi tiết.
- Liệt kê rõ ràng các thông tin cụ thể có trong tài liệu (số liệu, tên, ngày tháng, điều kiện, v.v.).
- Nếu có nhiều ý, trình bày theo từng mục rõ ràng.
- Nếu không có thông tin trong tài liệu, trả lời: "Không tìm thấy thông tin trong tài liệu KMA."
- Không bịa thêm thông tin ngoài tài liệu.

Tài liệu:
{context}

Câu hỏi: {question}
Trả lời:"""

ACCURACY_EXTRA_RULES = """
QUY TẮC ĐỘ CHÍNH XÁC TỐI ĐA (bắt buộc):
- Chỉ khẳng định số liệu, điều kiện, quy định khi có trong tài liệu; ghi kèm [số thứ tự đoạn] khi trích dẫn.
- Nếu câu hỏi yêu cầu danh sách (môn học, điều kiện, bước thủ tục, tiêu chí, ma trận, giấy tờ…): liệt kê ĐỦ TẤT CẢ mục có trong tài liệu, không gộp, không bỏ sót.
- Nếu câu hỏi so sánh (năm A vs B, ngành X vs Y): nêu rõ số liệu/fact của TỪNG bên, không chỉ mô tả chung.
- Nếu câu hỏi về tổng tiền, phí, mức tối thiểu, chỉ tiêu: trích đúng con số trong tài liệu (giữ dấu chấm/phẩy như bảng).
- Trả lời đầy đủ theo đúng phạm vi câu hỏi (kỳ học, môn, loại văn bản…) trước khi tóm tắt.
- Nếu tài liệu mâu thuẫn hoặc không đủ: nêu rõ phần chắc chắn và phần không có trong tài liệu.
- Không suy diễn, không dùng kiến thức ngoài KMA."""

PERSONA_ACCURACY_SUFFIX = (
    "\nƯu tiên độ chính xác: chỉ khẳng định khi có căn cứ trong tài liệu được cung cấp; "
    "chỉ trả «Không tìm thấy thông tin trong tài liệu KMA» sau khi đã đọc hết các đoạn trên."
)

_AGENT_ANSWER_RULES: dict[str, str] = {
    "tuyen_sinh": (
        "\nKhi tài liệu có bảng điểm chuẩn/trúng tuyển/chỉ tiêu theo ngành và năm: "
        "PHẢI trích đúng số liệu trong bảng (đúng năm tuyển sinh được hỏi). "
        "Không trả «không tìm thấy» nếu bảng có dòng ngành liên quan."
    ),
    "khao_thi": (
        "\nKhi tài liệu có bảng TOEIC/chuẩn ngoại ngữ hoặc quy định 120 tín chỉ cử nhân: "
        "liệt kê đủ các mức (TA1/TA2/TA3, VSTEP…). Không nhầm với khối lượng 150 tín chỉ nếu quy chế nêu 120."
    ),
    "bieu_mau": (
        "\nKhi hỏi catalog/tên file biểu mẫu: ghi rõ tên file gốc (vd. 24-Mau_khai_BHYT_sv_ATTT.doc). "
        "Khi hỏi giấy tờ/phí nhập học: liệt kê đủ mục từ hướng dẫn Thu_tuc_nhap_hoc_2024."
    ),
    "diem_thi": (
        "\nKhi câu hỏi tra cứu điểm cá nhân nhưng KHÔNG có MSSV dạng ATxxxxxx/CTxxxxxx: "
        "yêu cầu sinh viên cung cấp MSSV để tra cứu chính xác, ví dụ: "
        "«Vui lòng cung cấp MSSV dạng ATxxxxxx hoặc CTxxxxxx để tra cứu điểm.»\n"
        "Khi câu hỏi về tốt nghiệp CT4 hoặc kết quả Anh văn/chứng chỉ TA: "
        "tra trong file 04_ket_qua_tot_nghiep_ct4, 08_ket_qua_thi_anh_van, 12_ds_nhan_chung_chi_ta."
    ),
    "ma_tran": (
        "\nKhi tài liệu có dòng «Tổng số câu hỏi» / «Thời gian làm bài»: trích đúng số câu và số phút."
    ),
    "danh_sach_thi": (
        "\nBảng danh sách dự thi: header «Môn thi», «Hình thức thi»; cột STT, SBD, Mã HVSV, "
        "Ngày thi, Ca thi, Phòng, Ghi chú. Tra MSSV/SBD phải đúng hàng; ghi chú «Cấm thi/Nợ HP» "
        "thì thường không có SBD/ca/phòng. Không nhầm với tra điểm (diem_thi)."
    ),
    "lich_thi": (
        "\nKhi tài liệu là lịch KTHP: trích đúng học kỳ, đợt, tên môn, hình thức thi, khóa đào tạo, "
        "thời gian bắt đầu, địa điểm theo bảng. "
        "Mã khóa ghép: A19C7D6 = AT19 + CT7 + DT6 (A→AT, C→CT, D→DT + số); AT17/CT6 là một khóa. "
        "Ô khóa gộp nhiều dòng: dòng sau để trống vẫn thuộc khóa trên. "
        "File kthp_lan2_* = thi lại. Liệt kê môn phải ĐẦY ĐỦ theo điều kiện (khóa/HK/đợt)."
    ),
}


def build_rag_user_prompt(context: str, question: str) -> str:
    body = RAG_PROMPT_BASE.format(context=context, question=question)
    if ACCURACY_MODE:
        return body.replace("Trả lời:", ACCURACY_EXTRA_RULES + "\nTrả lời:")
    return body
