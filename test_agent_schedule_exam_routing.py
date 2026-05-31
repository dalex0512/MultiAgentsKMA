from agents.supervisor import _mssv_exam_list_route, _sbd_exam_list_route, _subject_schedule_route
from pipelines.specialist_runner import _schedule_table_fast_path
from utils.rag.schedule_lookup import (
    ScheduleRow,
    _filter_rows_by_subject,
    parse_schedule_file_hints,
    wants_schedule_table_query,
)
from utils.rag.exam_list_lookup import wants_exam_list_query


def test_lich_thi_schedule_intent_variants():
    cases = [
        "Cho tôi biết địa điểm thi môn Công nghệ phần mềm thi kết thúc học phần kì 1 năm 2024 2025 đợt1",
        "Lich thi KTHP hk1 2024-2025 dot1 mon CSDL thi phong nao?",
        "Thi kết thúc học phần đợt2 học kỳ 2 môn Toán cao cấp ở đâu?",
        "Cho lịch thi lại lần 2 học kỳ 2 năm 2024-2025",
        "Giờ thi và địa điểm thi môn kiểm thử phần mềm kì 1 đợt 2",
        "Thời gian bắt đầu thi môn Công nghệ phần mềm là khi nào?",
    ]
    for q in cases:
        assert wants_schedule_table_query(q), f"Should detect schedule-table intent: {q}"
        assert _schedule_table_fast_path("lich_thi", q, q), f"Should enable lich_thi fast-path: {q}"


def test_lich_thi_parse_period_hints_variants():
    h1 = parse_schedule_file_hints("Lịch thi kì 1 năm 2024-2025 đợt1")
    assert h1["ki"] == "ki1", f"Expected ki1, got {h1}"
    assert h1["dot"] == "dot1", f"Expected dot1, got {h1}"
    assert h1["year_key"] == "20242025", f"Expected 20242025, got {h1}"

    h2 = parse_schedule_file_hints("Thi kết thúc học phần ki 2 2025 2026 dot2")
    assert h2["ki"] == "ki2", f"Expected ki2, got {h2}"
    assert h2["dot"] == "dot2", f"Expected dot2, got {h2}"

    h3 = parse_schedule_file_hints("Lịch thi học kỳ 2 năm học 2025-2026")
    assert h3["ki"] == "ki2", f"Expected ki2, got {h3}"
    assert h3["year_key"] == "20252026", f"Expected 20252026, got {h3}"


def test_danh_sach_thi_exam_list_intent_variants():
    cases = [
        "MSSV CT060310 thi phòng nào ngày 21/04/2026 buổi sáng?",
        "AT200201 ca thi chiều ở đâu?",
        "Cho tôi tra danh sách dự thi của CT100101 ngày 22/04/2026",
        "Số báo danh của CT060310 là gì trong danh sách thi?",
    ]
    for q in cases:
        assert wants_exam_list_query(q), f"Should detect exam-list intent: {q}"
        dec = _mssv_exam_list_route(q)
        assert dec is not None, f"Should route MSSV exam-list query: {q}"
        assert dec.primary == "danh_sach_thi", f"Primary should be danh_sach_thi: {q}"
        assert "danh_sach_thi" in dec.agents, f"Agents should include danh_sach_thi: {q}"

    sbd_q = "Cho tôi xem số báo danh SBD 491, ca thi và phòng thi?"
    assert wants_exam_list_query(sbd_q), "SBD query should be exam-list intent"
    dec_sbd = _sbd_exam_list_route(sbd_q)
    assert dec_sbd is not None and dec_sbd.primary == "danh_sach_thi", "SBD should route to danh_sach_thi"


def test_negative_boundaries_between_two_agents():
    # Lich thi: không có MSSV nhưng vẫn là lịch/phòng thi theo môn-học kỳ
    q_schedule = "Địa điểm thi môn CSDL học kỳ 1 đợt 1 là ở đâu?"
    assert wants_schedule_table_query(q_schedule), "Should be schedule intent"
    assert not wants_exam_list_query(q_schedule), "Schedule-by-subject should not trigger exam-list intent"
    assert _mssv_exam_list_route(q_schedule) is None, "Should not route to danh_sach_thi without MSSV"

    # Danh sách thi: có MSSV + phòng/ca thi, không phải hỏi điểm
    q_exam_list = "CT060310 thi phòng nào ca sáng?"
    assert wants_exam_list_query(q_exam_list), "Should be exam-list intent"
    assert not ("điểm" in q_exam_list.lower() or "kết quả" in q_exam_list.lower())
    dec = _mssv_exam_list_route(q_exam_list)
    assert dec is not None and dec.primary == "danh_sach_thi", "Should route to danh_sach_thi"


def test_supervisor_subject_schedule_route_stability():
    cases = [
        "Địa điểm thi môn Phát triển game trên Android thi kết thúc học phần học kỳ 1 năm 2024 2025 đợt 1",
        "Cho biết giờ thi môn Công nghệ phần mềm học kỳ 1 năm 2024-2025 đợt1",
        "Môn Cơ sở dữ liệu thi ở đâu học kỳ 2 đợt2",
        "Thời gian bắt đầu thi môn Phát triển game trên Android là khi nào?",
    ]
    for q in cases:
        dec = _subject_schedule_route(q)
        assert dec is not None, f"Should hard-route to lich_thi: {q}"
        assert dec.primary == "lich_thi", f"Primary must be lich_thi: {q}"

    not_schedule = "Ma trận đề môn Tin học đại cương có bao nhiêu câu và bao nhiêu phút?"
    assert _subject_schedule_route(not_schedule) is None, "Matrix structure query should not force lich_thi"


def test_schedule_subject_filter_by_query():
    rows = [
        ScheduleRow(tt=1, mon_thi="C chuyên đề chuyên ngành chuyên sâu", dia_diem="P201"),
        ScheduleRow(tt=2, mon_thi="Công nghệ web an toàn", dia_diem="TA1"),
        ScheduleRow(tt=3, mon_thi="Mã độc", dia_diem="TA2"),
    ]
    q = "Địa điểm thi môn Công nghệ web an toàn học kỳ 1 đợt 1?"
    filtered, subject = _filter_rows_by_subject(q, rows)
    assert subject is not None, "Should extract subject phrase"
    assert len(filtered) == 1, f"Expected one row, got {len(filtered)}"
    assert filtered[0].mon_thi == "Công nghệ web an toàn", "Should keep exact subject row"


if __name__ == "__main__":
    test_lich_thi_schedule_intent_variants()
    test_lich_thi_parse_period_hints_variants()
    test_danh_sach_thi_exam_list_intent_variants()
    test_negative_boundaries_between_two_agents()
    test_supervisor_subject_schedule_route_stability()
    test_schedule_subject_filter_by_query()
    print("PASS: schedule + exam-list routing regression tests passed!")
