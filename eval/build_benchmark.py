"""
Sinh eval/benchmark.json + test_tay_100_cau.md — 100 câu test tay trên web chat.

Mục tiêu: copy câu hỏi → chatbot → so sánh với «Câu trả lời đúng cần có».
Chạy: python eval/build_benchmark.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent
OUT_JSON = ROOT / "benchmark.json"
OUT_TEST_TAY = ROOT / "test_tay_100_cau.md"
OUT_TECH = ROOT / "benchmark.md"

# Pipeline sets (khớp ACCURACY_MODE: native có thể được nâng hybrid)
PIPE_GUARDRAIL = ["guardrail"]
PIPE_SIMPLE = ["native_rag", "hybrid_rag"]
PIPE_MEDIUM = ["hybrid_rag", "agentic_rag"]
PIPE_COMPLEX = ["hybrid_rag", "agentic_rag", "multi_agent"]
PIPE_MULTI = ["multi_agent"]
PIPE_GRADE = ["grade_lookup", "hybrid_rag", "agentic_rag"]
PIPE_FORM = ["form_fill", "native_rag", "hybrid_rag"]

META = {
    "version": "3.0",
    "project": "KMA Multi-Agent Chatbot",
    "purpose": "test_tay",
    "description": (
        "100 câu test trực tiếp trên http://127.0.0.1:8000 — copy câu hỏi, "
        "so sánh câu trả lời chatbot với mục «Câu trả lời đúng cần có». "
        "Gold facts trích từ docs/. Cần ingest_all.py + Qdrant trước khi test."
    ),
    "api_endpoint": "POST /chat",
    "tier_distribution": {
        "L0": "Guardrail — không vào RAG (8)",
        "L1": "Đơn giản — 1 agent, native/hybrid, supervisor (20)",
        "L2": "Trung bình — hybrid/agentic/grade_lookup (22)",
        "L3": "Multi-agent — supervisor multi_domain (17)",
        "L4": "Phức tạp — planner + agentic/multi (15)",
        "L5": "Multi-turn — memory & rewrite (12)",
        "L6": "Biểu mẫu — catalog & form_fill (6)",
    },
    "scoring_notes": {
        "agents": "subset hoặc agents_exact; not_agents / min_agents cho multi",
        "supervisor_intent": "grade_result | form_procedure | multi_domain | single_domain",
        "pipeline": "pipeline_any trên response hoặc per_agent[].pipeline",
        "per_agent_pipelines": "Mỗi agent phải dùng pipeline trong danh sách",
        "content": "must_contain_* / gold_facts / source_file_any",
        "env": "KMA_ACCURACY_MODE=1, KMA_FAST_MODE=0, đã ingest_all.py",
    },
    "router_thresholds_local_qc": {
        "native_rag": "Qc < 0.50",
        "hybrid_rag": "0.50 ≤ Qc < 0.70",
        "agentic_rag": "Qc ≥ 0.70",
    },
}

CASES: list[dict] = []


def c(
    id: str,
    tier: str,
    title: str,
    question: str,
    *,
    agents: list[str],
    primary: str | None = None,
    pipeline_any: list[str] | None = None,
    per_agent_pipelines: list[dict] | None = None,
    supervisor_intent: str | None = None,
    agents_exact: bool = False,
    min_agents: int | None = None,
    not_agents: list[str] | None = None,
    planner: bool | None = None,
    in_scope: bool = True,
    scope: str = "kma",
    must_all: list[str] | None = None,
    must_any: list[str] | None = None,
    must_not: list[str] | None = None,
    gold: list[str] | None = None,
    sources: list[str] | None = None,
    qc_min: float | None = None,
    qc_max: float | None = None,
    tags: list[str] | None = None,
    notes: str = "",
):
    primary = primary or (agents[0] if agents else "")
    exp: dict = {
        "agents": agents,
        "primary": primary,
        "pipeline_any": pipeline_any or PIPE_SIMPLE,
        "in_scope": in_scope,
        "scope_category": scope,
    }
    if supervisor_intent:
        exp["supervisor_intent"] = supervisor_intent
    if agents_exact:
        exp["agents_exact"] = True
    if min_agents is not None:
        exp["min_agents"] = min_agents
    if not_agents:
        exp["not_agents"] = not_agents
    if planner is True:
        exp["planner_used"] = True
    elif planner is False:
        exp["planner_used"] = False
    if qc_min is not None:
        exp["qc_min"] = qc_min
    if qc_max is not None:
        exp["qc_max"] = qc_max
    if per_agent_pipelines:
        exp["per_agent_pipelines"] = per_agent_pipelines

    CASES.append({
        "id": id,
        "tier": tier,
        "title": title,
        "turns": [{"question": question.strip()}],
        "expected": exp,
        "rubric": {
            "must_contain_all": must_all or [],
            "must_contain_any": must_any or [],
            "must_not_contain": must_not or [],
            "gold_facts": gold or [],
            "source_file_any": sources or [],
        },
        "tags": tags or [],
        "notes": notes,
        "scoring_mode": "content",
    })


def mt(
    id: str,
    tier: str,
    title: str,
    turns_spec: list[dict],
    *,
    agents: list[str],
    primary: str | None = None,
    pipeline_any: list[str] | None = None,
    planner: bool | None = None,
    tags: list[str] | None = None,
    notes: str = "",
):
    primary = primary or (agents[0] if agents else "")
    turns = []
    for t in turns_spec:
        turns.append({
            "question": t["q"].strip(),
            "expected": t.get("exp", {}),
            "rubric": t.get("rubric", {}),
        })
    exp: dict = {
        "agents": agents,
        "primary": primary,
        "pipeline_any": pipeline_any or PIPE_SIMPLE + PIPE_MULTI + PIPE_FORM,
        "in_scope": True,
        "scope_category": "kma",
    }
    if planner is True:
        exp["planner_used"] = True
    CASES.append({
        "id": id,
        "tier": tier,
        "title": title,
        "multi_turn": True,
        "turns": turns,
        "expected": exp,
        "rubric": {"notes": notes},
        "tags": tags or [],
        "notes": notes,
        "scoring_mode": "content",
    })


# ═══ L0 — Guardrail (6) ═══════════════════════════════════════════════════
c("L0-01", "L0", "Chào hỏi", "Xin chào!",
  agents=[], in_scope=False, scope="chitchat", pipeline_any=PIPE_GUARDRAIL,
  must_any=["KMA", "trợ lý"], tags=["guardrail", "chitchat"])

c("L0-02", "L0", "Cảm ơn", "Cảm ơn bạn nhé!",
  agents=[], in_scope=False, scope="chitchat", pipeline_any=PIPE_GUARDRAIL, tags=["chitchat"])

c("L0-03", "L0", "Off-topic thời tiết", "Thời tiết Hà Nội ngày mai thế nào?",
  agents=[], in_scope=False, scope="off_topic", pipeline_any=PIPE_GUARDRAIL,
  must_any=["ngoài phạm vi", "KMA"], tags=["off_topic"])

c("L0-04", "L0", "Off-topic lập trình", "Viết code Python sắp xếp danh sách như thế nào?",
  agents=[], in_scope=False, scope="off_topic", pipeline_any=PIPE_GUARDRAIL, tags=["off_topic"])

c("L0-05", "L0", "Trường khác", "Điểm chuẩn Đại học Bách Khoa Hà Nội năm 2025?",
  agents=[], in_scope=False, scope="off_topic", pipeline_any=PIPE_GUARDRAIL,
  must_any=["ngoài phạm vi"], tags=["off_topic"])

c("L0-06", "L0", "Giới thiệu khả năng", "Bạn có thể giúp gì cho sinh viên KMA?",
  agents=[], in_scope=False, scope="chitchat", pipeline_any=PIPE_GUARDRAIL,
  must_any=["tuyển sinh", "biểu mẫu", "quy chế", "ma trận", "điểm"], tags=["chitchat", "capability"])


# ═══ L1 — Đơn giản: 1 agent + native/hybrid (14) ═══════════════════════════
# tuyen_sinh
c("L1-01", "L1", "Mã trường KMA", "Mã trường của Học viện Kỹ thuật Mật mã trong đề án tuyển sinh 2025 là gì?",
  agents=["tuyen_sinh"], agents_exact=True, supervisor_intent="single_domain",
  pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  gold=["KMA"], sources=["01_de_an_tuyen_sinh_2025.pdf"], tags=["tuyen_sinh", "fact"])

c("L1-02", "L1", "Website tuyển sinh", "Trang web tuyển sinh chính thức của KMA là gì?",
  agents=["tuyen_sinh"], agents_exact=True, supervisor_intent="single_domain",
  pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  must_any=["tuyensinh.actvn.edu.vn", "actvn"], sources=["01_de_an_tuyen_sinh_2025.pdf"], tags=["tuyen_sinh"])

# khao_thi
c("L1-03", "L1", "Khối tín chỉ cử nhân", "Khối lượng học tập tối thiểu chương trình cử nhân theo quy chế đào tạo KMA 2025 là bao nhiêu tín chỉ?",
  agents=["khao_thi"], agents_exact=True, supervisor_intent="single_domain",
  pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  gold=["120"], sources=["25_quy_che_dao_tao_dai_hoc_2025.pdf"], tags=["khao_thi"])

c("L1-04", "L1", "TOEIC Tiếng Anh 1", "Sinh viên cần đạt tối thiểu bao nhiêu điểm TOEIC khi kết thúc học phần Tiếng Anh 1 theo quy định chuẩn ngoại ngữ KMA?",
  agents=["khao_thi"], agents_exact=True, supervisor_intent="single_domain",
  pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  gold=["300"], sources=["03_quy_dinh_chuan_ngoai_ngu_2025.pdf"], tags=["khao_thi"])

# ma_tran
c("L1-05", "L1", "Ma trận THĐC — số câu", "Môn Tin học đại cương: tổng số câu trắc nghiệm và thời gian làm bài theo ma trận đề thi KMA?",
  agents=["ma_tran"], agents_exact=True, supervisor_intent="single_domain",
  pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  must_all=["50", "60"], sources=["13_ma_tran_de_thi_tin_hoc_dai_cuong.pdf"], tags=["ma_tran"])

c("L1-06", "L1", "Ma trận Toán A3 — khoa", "Môn Toán cao cấp A3 thuộc khoa nào theo ma trận đề thi?",
  agents=["ma_tran"], agents_exact=True, supervisor_intent="single_domain",
  pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  must_any=["Cơ bản"], sources=["21_ma_tran_toan_cao_cap_a3.pdf"], tags=["ma_tran"])

# bieu_mau
c("L1-07", "L1", "Đơn phúc khảo", "KMA có mẫu đơn xin phúc khảo bài thi không? Tên file trong catalog?",
  agents=["bieu_mau"], agents_exact=True, supervisor_intent="form_procedure",
  pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  must_any=["phúc khảo", "15-Don_phuc_khao"], tags=["bieu_mau", "catalog"])

c("L1-08", "L1", "Đơn nghỉ dưới 7 ngày", "Sinh viên xin nghỉ học tạm thời dưới 7 ngày dùng đơn nào?",
  agents=["bieu_mau"], agents_exact=True, supervisor_intent="form_procedure",
  pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  must_any=["08-Don", "dưới 7"], tags=["bieu_mau"])

# diem_thi — không MSSV (danh sách / file chung)
c("L1-09", "L1", "SV đạt TA đầu vào", "Mã sinh viên AT200201 có đạt kiểm tra phân loại tiếng Anh đầu vào khóa A20C8D7 năm 2024 (lần 2) không?",
  agents=["diem_thi"], agents_exact=True, supervisor_intent="grade_result",
  pipeline_any=PIPE_GRADE + PIPE_MEDIUM, qc_max=0.65,
  must_any=["ĐẠT", "đạt", "AT200201"], sources=["08_ket_qua_thi_anh_van_2024.pdf"], tags=["diem_thi"])

c("L1-10", "L1", "SV không đạt TA", "Sinh viên AT200401 có trong danh sách ĐẠT tiếng Anh đầu vào A20C8D7 2024 (lần 2) không?",
  agents=["diem_thi"], agents_exact=True, supervisor_intent="grade_result",
  pipeline_any=PIPE_GRADE + PIPE_MEDIUM, qc_max=0.65,
  must_any=["KHÔNG", "không đạt", "AT200401"], sources=["08_ket_qua_thi_anh_van_2024.pdf"], tags=["diem_thi"])

# Routing edge — supervisor phân loại đúng mảng
c("L1-11", "L1", "Điểm chuẩn CNTT (không diem_thi)", "Điểm chuẩn ngành Công nghệ thông tin năm 2024 theo đề án tuyển sinh KMA là bao nhiêu?",
  agents=["tuyen_sinh"], agents_exact=True, not_agents=["diem_thi"],
  supervisor_intent="single_domain", pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  must_any=["26.20", "26,20", "26.60", "26,60"], sources=["02_de_an_tuyen_sinh_2024.pdf"],
  tags=["routing", "tuyen_sinh", "admission"],
  notes="Supervisor không được gán diem_thi cho «điểm chuẩn».")

c("L1-12", "L1", "Chuẩn VSTEP", "Học viện có công nhận chứng chỉ VSTEP không?",
  agents=["khao_thi"], agents_exact=True, not_agents=["diem_thi", "tuyen_sinh"],
  supervisor_intent="single_domain", pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  must_any=["VSTEP"], sources=["03_quy_dinh_chuan_ngoai_ngu_2025.pdf"], tags=["khao_thi"])

c("L1-13", "L1", "Ma trận — không nhầm tuyển sinh", "Ma trận đề thi môn Tin học đại cương gồm những phần nào?",
  agents=["ma_tran"], agents_exact=True, not_agents=["tuyen_sinh"],
  supervisor_intent="single_domain", pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  sources=["13_ma_tran_de_thi_tin_hoc_dai_cuong.pdf"], tags=["ma_tran"])

c("L1-14", "L1", "Tổng phí nhập học", "Tổng số tiền phải nộp khi làm thủ tục nhập học theo hướng dẫn KMA 2024 là bao nhiêu?",
  agents=["bieu_mau"], agents_exact=True, supervisor_intent="form_procedure",
  pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  gold=["10.896.940", "10896940"], sources=["Thu_tuc_nhap_hoc_2024.pdf"], tags=["bieu_mau"])


# ═══ L2 — Trung bình: hybrid/agentic / grade_lookup (16) ═══════════════════
c("L2-01", "L2", "So sánh điểm TS ATTT", "So sánh điểm trúng tuyển năm 2023 và 2024 của ngành An toàn thông tin (cơ sở Hà Nội) theo đề án tuyển sinh KMA.",
  agents=["tuyen_sinh"], agents_exact=True, not_agents=["diem_thi"],
  supervisor_intent="single_domain", pipeline_any=PIPE_MEDIUM, qc_min=0.45,
  must_any=["25.60", "25.90", "25,90", "25.95"], tags=["tuyen_sinh", "compare"])

c("L2-02", "L2", "Liệt kê tổ hợp TS 2025", "Liệt kê các tổ hợp môn xét tuyển đại học chính quy KMA năm 2025.",
  agents=["tuyen_sinh"], agents_exact=True, pipeline_any=PIPE_MEDIUM, qc_min=0.40,
  must_any=["A00", "A01", "Toán"], tags=["tuyen_sinh", "list"])

c("L2-03", "L2", "CDIO CNTT", "Chương trình CNTT chính quy KMA theo hướng tiếp cận nào và mã chương trình là gì?",
  agents=["tuyen_sinh"], agents_exact=True, pipeline_any=PIPE_MEDIUM, qc_min=0.40,
  must_all=["CDIO", "KMC.1.1.1"], sources=["23_chuong_trinh_dao_tao_cntt.pdf"], tags=["tuyen_sinh"])

c("L2-04", "L2", "Đối tượng chuẩn NN", "Quy định chuẩn ngoại ngữ KMA không áp dụng cho những đối tượng sinh viên nào?",
  agents=["khao_thi"], agents_exact=True, pipeline_any=PIPE_MEDIUM, qc_min=0.40,
  must_any=["kỹ sư tài năng", "chất lượng cao"], tags=["khao_thi"])

c("L2-05", "L2", "TOEIC TA2", "Theo bảng chuẩn tiếng Anh, sinh viên cần bao nhiêu tín chỉ tích lũy và TOEIC tối thiểu khi kết thúc Tiếng Anh 2?",
  agents=["khao_thi"], agents_exact=True, pipeline_any=PIPE_MEDIUM, qc_min=0.45,
  must_all=["3", "350"], tags=["khao_thi", "table"])

c("L2-06", "L2", "Ma trận THĐC — mức độ", "Trong ma trận Tin học đại cương, tổng điểm phân bổ NB, TH, VD, VDC lần lượt là bao nhiêu?",
  agents=["ma_tran"], agents_exact=True, pipeline_any=PIPE_MEDIUM, qc_min=0.45,
  must_any=["10", "22"], sources=["13_ma_tran_de_thi_tin_hoc_dai_cuong.pdf"], tags=["ma_tran"])

c("L2-07", "L2", "Ma trận CSDL", "Ma trận đề thi môn Lý thuyết cơ sở dữ liệu có những phần nội dung chính nào?",
  agents=["ma_tran"], agents_exact=True, pipeline_any=PIPE_MEDIUM, qc_min=0.40,
  sources=["14_ma_tran_de_thi_ly_thuyet_csdl.pdf"], tags=["ma_tran"])

c("L2-08", "L2", "Giấy tờ nhập học", "Liệt kê ít nhất 6 loại giấy tờ sinh viên phải mang khi làm thủ tục nhập học KMA 2024.",
  agents=["bieu_mau"], agents_exact=True, supervisor_intent="form_procedure",
  pipeline_any=PIPE_MEDIUM, qc_min=0.45,
  must_any=["trúng tuyển", "học bạ", "CCCD"], sources=["Thu_tuc_nhap_hoc_2024.pdf"], tags=["bieu_mau", "list"])

c("L2-09", "L2", "So sánh đơn nghỉ", "Khác nhau giữa đơn nghỉ học dưới 7 ngày và trên 7 ngày của KMA?",
  agents=["bieu_mau"], agents_exact=True, pipeline_any=PIPE_MEDIUM, qc_min=0.40,
  must_any=["08-Don", "09-Don", "7 ngày"], tags=["bieu_mau", "compare"])

c("L2-10", "L2", "File HK1 đợt 2", "File bảng điểm học kỳ 1 năm 2024-2025 đợt 2 của KMA tổng hợp những học phần nào (nêu ít nhất 3 tên)?",
  agents=["diem_thi"], agents_exact=True, pipeline_any=PIPE_MEDIUM, qc_min=0.40,
  must_any=["hk1_20242025", "2024", "2025"], sources=["hk1_20242025_dot2.pdf"], tags=["diem_thi"])

# grade_lookup — MSSV + học kỳ
c("L2-11", "L2", "CT060310 HK2 đợt 1", "CT060310 điểm học kỳ 2 năm 2024-2025 đợt 1",
  agents=["diem_thi"], agents_exact=True, supervisor_intent="grade_result",
  pipeline_any=PIPE_GRADE, qc_min=0.35,
  per_agent_pipelines=[{"agent_id": "diem_thi", "pipeline_any": PIPE_GRADE}],
  must_any=["CT060310"], must_not=["không tìm thấy thông tin trong tài liệu"],
  sources=["hk2_20242025_dot1"], tags=["diem_thi", "grade_lookup", "mssv"],
  notes="Kỳ vọng grade_lookup; trả lời có điểm/môn, không «không tìm thấy» khi MSSV có trong PDF.")

c("L2-12", "L2", "AT200106 TA đầu vào", "Sinh viên AT200106 có đạt phân loại tiếng Anh đầu vào A20C8D7 2024 (lần 2) không? Cho biết lớp nếu có.",
  agents=["diem_thi"], agents_exact=True, supervisor_intent="grade_result",
  pipeline_any=PIPE_GRADE + PIPE_MEDIUM,
  must_any=["AT200106", "ĐẠT", "đạt"], sources=["08_ket_qua_thi_anh_van_2024.pdf"], tags=["diem_thi", "grade_lookup"])

c("L2-13", "L2", "AT200201 điểm HK1 đợt 2", "Cho xem điểm học kỳ 1 năm 2024-2025 đợt 2 của sinh viên AT200201.",
  agents=["diem_thi"], agents_exact=True, supervisor_intent="grade_result",
  pipeline_any=PIPE_GRADE,
  per_agent_pipelines=[{"agent_id": "diem_thi", "pipeline_any": PIPE_GRADE}],
  must_any=["AT200201"], tags=["diem_thi", "grade_lookup"])

c("L2-14", "L2", "TOEIC trước đồ án", "Điểm TOEIC tối thiểu trước khi nhận đề tài đồ án tốt nghiệp theo quy định chuẩn ngoại ngữ KMA?",
  agents=["khao_thi"], agents_exact=True, not_agents=["diem_thi"],
  pipeline_any=PIPE_MEDIUM, qc_min=0.40,
  gold=["450"], tags=["khao_thi"])

c("L2-15", "L2", "Hướng dẫn thi TN online", "KMA có tài liệu hướng dẫn thi tốt nghiệp online không? Nêu tên file.",
  agents=["khao_thi"], agents_exact=True, pipeline_any=PIPE_MEDIUM,
  sources=["22_huong_dan_thi_tot_nghiep_online.pdf"], tags=["khao_thi"])

c("L2-16", "L2", "Thực tập — catalog", "Sinh viên cần giấy giới thiệu thực tập — tên biểu mẫu trong catalog KMA?",
  agents=["bieu_mau"], agents_exact=True, supervisor_intent="form_procedure",
  pipeline_any=PIPE_SIMPLE + PIPE_MEDIUM, qc_max=0.60,
  must_any=["18-Giay_gioi_thieu_thuc_tap", "thực tập"], tags=["bieu_mau", "catalog"])


# ═══ L3 — Multi-agent (12) ═════════════════════════════════════════════════
c("L3-01", "L3", "TS + phí nhập học", (
    "Theo đề án tuyển sinh KMA 2025, phương thức tuyển sinh đại học chính quy là gì? "
    "Đồng thời theo hướng dẫn nhập học 2024, tổng số tiền phải nộp khi làm thủ tục là bao nhiêu?"
), agents=["tuyen_sinh", "bieu_mau"], primary="tuyen_sinh", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI + PIPE_COMPLEX,
  must_any=["xét tuyển", "10.896"], tags=["multi_agent", "supervisor"])

c("L3-02", "L3", "Quy chế + đơn phúc khảo", (
    "Theo quy chế đào tạo KMA 2025, chương trình học được xây dựng theo đơn vị gì? "
    "Và sinh viên muốn phúc khảo bài thi cần dùng đơn/mẫu nào trong catalog?"
), agents=["khao_thi", "bieu_mau"], primary="bieu_mau", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI,
  must_any=["tín chỉ", "phúc khảo", "15-Don"], tags=["multi_agent"])

c("L3-03", "L3", "Chuẩn NN + điểm TA", (
    "Chuẩn TOEIC tối thiểu trước khi nhận đề tài đồ án của KMA là bao nhiêu? "
    "Và sinh viên AT200106 có đạt tiếng Anh đầu vào khóa A20C8D7 2024 (lần 2) không?"
), agents=["khao_thi", "diem_thi"], primary="khao_thi", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI + PIPE_COMPLEX,
  must_all=["450"], must_any=["AT200106", "ĐẠT", "đạt"], tags=["multi_agent"])

c("L3-04", "L3", "Ma trận + quy chế thi", (
    "Ma trận Tin học đại cương quy định thời gian thi bao lâu? "
    "Quy chế đào tạo KMA 2025 quy định khối lượng tối thiểu cử nhân bao nhiêu tín chỉ?"
), agents=["ma_tran", "khao_thi"], primary="ma_tran", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI,
  must_any=["60", "120"], tags=["multi_agent"])

c("L3-05", "L3", "CTĐT + ma trận toán", (
    "Chương trình CNTT KMA theo CDIO có mã ngành gì? "
    "Ma trận môn Toán cao cấp A3 thuộc khoa nào?"
), agents=["tuyen_sinh", "ma_tran"], primary="tuyen_sinh", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI,
  must_any=["CDIO", "7.48", "Cơ bản"], tags=["multi_agent"])

c("L3-06", "L3", "Điểm chuẩn + mẫu nhập học", (
    "Điểm trúng tuyển ngành CNTT Hà Nội năm 2024 của KMA là bao nhiêu? "
    "Và có mẫu đơn/biểu mẫu nào liên quan thủ tục nhập học trong catalog?"
), agents=["tuyen_sinh", "bieu_mau"], primary="tuyen_sinh", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI + PIPE_COMPLEX,
  must_any=["26.20", "26.60", "26.1", "nhập học", "Thu_tuc"], tags=["multi_agent"])

c("L3-07", "L3", "TOEIC TA3 + ma trận THĐC", (
    "Yêu cầu TOEIC khi kết thúc Tiếng Anh 3 theo quy định chuẩn ngoại ngữ KMA? "
    "Và môn Tin học đại cương có bao nhiêu câu trắc nghiệm theo ma trận?"
), agents=["khao_thi", "ma_tran"], primary="khao_thi", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI,
  must_all=["450", "50"], tags=["multi_agent"])

c("L3-08", "L3", "Kết quả TA + đơn hoãn thi", (
    "Tài liệu kết quả thi Anh văn công bố 2024 của KMA dùng để tra cứu gì? "
    "Và đơn xin hoãn thi trong bộ biểu mẫu tên file gì?"
), agents=["diem_thi", "bieu_mau"], primary="diem_thi", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI,
  must_any=["14-Don_hoan_thi", "Anh văn", "08_ket_qua"], tags=["multi_agent"])

c("L3-09", "L3", "Quy chế + CTĐT CNTT", (
    "Quy chế đào tạo 2025: khối lượng tối thiểu cử nhân? "
    "Chương trình CNTT: mã ngành đào tạo?"
), agents=["khao_thi", "tuyen_sinh"], primary="khao_thi", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI,
  must_all=["120", "7.48.01.01"], tags=["multi_agent"])

c("L3-10", "L3", "Thạc sĩ + mã trường", (
    "KMA có danh sách trúng tuyển thạc sĩ ATTT 2025 không? "
    "Đề án tuyển sinh đại học 2025 ghi mã trường là gì?"
), agents=["tuyen_sinh"], agents_exact=True,
  supervisor_intent="single_domain", pipeline_any=PIPE_MEDIUM,
  must_any=["KMA", "thạc sĩ"], sources=["09_trung_tuyen_thac_si_attt_2025.pdf"],
  tags=["tuyen_sinh", "multi_topic"],
  notes="Một agent đủ nếu cả hai ý cùng corpus tuyển sinh — không bắt 2 agent.")

c("L3-11", "L3", "Đơn nghỉ + BHYT", (
    "Sinh viên nghỉ học trên 7 ngày và cần cấp lại thẻ BHYT: dùng những đơn/mẫu nào trong catalog KMA?"
), agents=["bieu_mau"], agents_exact=True, supervisor_intent="form_procedure",
  pipeline_any=PIPE_MEDIUM, min_agents=1,
  must_any=["09-Don", "16-Don", "BHYT"], tags=["bieu_mau", "multi_topic"])

c("L3-12", "L3", "DT070103 + chứng chỉ TA", (
    "Sinh viên DT070103 có đạt phân loại tiếng Anh đầu vào 2024 không? "
    "File danh sách nhận chứng chỉ tiếng Anh TA 2024 dùng để tra cứu gì?"
), agents=["diem_thi"], agents_exact=True, supervisor_intent="grade_result",
  pipeline_any=PIPE_GRADE + PIPE_MEDIUM,
  must_any=["DT070103"], sources=["12_ds_nhan_chung_chi_ta_2024.pdf"],
  tags=["diem_thi", "multi_topic"])


# ═══ L4 — Planner / phức tạp (10) ══════════════════════════════════════════
c("L4-01", "L4", "Tổng hợp tân SV", (
    "Em là tân sinh viên KMA nhập học 2024: cho em biết tổng tiền phải nộp khi làm thủ tục, "
    "học viện có ký túc xá không, cần mang những giấy tờ gì (ít nhất 5 mục), và trang tuyển sinh chính thức là gì?"
), agents=["bieu_mau", "tuyen_sinh"], primary="bieu_mau", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI + PIPE_COMPLEX, planner=True,
  must_any=["10.896", "không có Ký túc xá", "tuyensinh"], tags=["planner", "multi_agent"])

c("L4-02", "L4", "Roadmap ngoại ngữ", (
    "Giải thích lộ trình chuẩn tiếng Anh KMA: TOEIC tối thiểu sau Tiếng Anh 1, Tiếng Anh 2, Tiếng Anh 3, "
    "trước khi nhận đề tài đồ án; nêu rõ số tín chỉ tích lũy tương ứng từng mốc."
), agents=["khao_thi"], agents_exact=True, pipeline_any=PIPE_COMPLEX, planner=True, qc_min=0.50,
  must_any=["300", "350", "450"], tags=["planner", "khao_thi", "agentic"])

c("L4-03", "L4", "So sánh ngành TS", (
    "So sánh chỉ tiêu, số nhập học và điểm trúng tuyển năm 2024 của ngành CNTT và An toàn thông tin "
    "(cơ sở Hà Nội) theo đề án tuyển sinh KMA."
), agents=["tuyen_sinh"], agents_exact=True, pipeline_any=PIPE_COMPLEX, planner=True,
  must_any=["26.20", "26.60", "25.90", "25.95"], tags=["planner", "compare", "tuyen_sinh"])

c("L4-04", "L4", "Thi + đơn + quy chế", (
    "Sinh viên KMA muốn phúc khảo kết quả thi, xin hoãn thi và cần biết quy chế đào tạo quy định "
    "chương trình học theo đơn vị tín chỉ — hướng dẫn từng thủ tục và tên đơn tương ứng."
), agents=["khao_thi", "bieu_mau"], primary="bieu_mau", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI + PIPE_COMPLEX, planner=True,
  must_any=["phúc khảo", "hoãn thi", "tín chỉ", "15-Don", "14-Don"], tags=["planner"])

c("L4-05", "L4", "Ma trận 3 môn", (
    "Trong tài liệu ma trận đề thi KMA, nêu tổng số câu và thời gian thi của Tin học đại cương, "
    "khoa phụ trách Toán cao cấp A3, và ít nhất hai phần nội dung của Lý thuyết CSDL."
), agents=["ma_tran"], agents_exact=True, pipeline_any=PIPE_COMPLEX, planner=True,
  must_all=["50", "60"], must_any=["Cơ bản", "CSDL"], tags=["planner", "ma_tran"])

c("L4-06", "L4", "Điểm TA + quy chế", (
    "Cho biết sinh viên AT200401 và AT200201 trong kết quả phân loại tiếng Anh đầu vào A20C8D7 2024 (lần 2), "
    "đồng thời nêu điểm TOEIC tối thiểu trước đồ án theo quy định chuẩn ngoại ngữ KMA."
), agents=["diem_thi", "khao_thi"], primary="diem_thi", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI + PIPE_COMPLEX, planner=True,
  must_any=["AT200401", "AT200201", "450"], tags=["planner", "multi_agent"])

c("L4-07", "L4", "Bảo lưu / tiếp tục / thôi học", (
    "Sinh viên KMA đang cân nhắc bảo lưu kết quả, sau đó tiếp tục học hoặc thôi học: "
    "mỗi trường hợp dùng đơn nào trong catalog, khác nhau thế nào?"
), agents=["bieu_mau"], agents_exact=True, pipeline_any=PIPE_COMPLEX, planner=True,
  must_any=["10-Don", "11-Don", "12-Don", "bảo lưu"], tags=["planner", "bieu_mau"])

c("L4-08", "L4", "CNTT + thực tập + đồ án", (
    "Sinh viên ngành CNTT KMA: mã ngành, hướng CDIO, đơn đăng ký đồ án lần 2 và giấy giới thiệu thực tập — "
    "tên file và mục đích từng biểu mẫu."
), agents=["tuyen_sinh", "bieu_mau"], primary="tuyen_sinh", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI + PIPE_COMPLEX, planner=True,
  must_any=["7.48.01.01", "17-Don", "18-Giay"], tags=["planner"])

c("L4-09", "L4", "Ưu tiên nhập học + MBank", (
    "Thủ tục nhập học KMA 2024: các khoản phí bắt buộc (học phí HK1 tạm thu, BHYT, thư viện, thẻ SV, khám SK), "
    "tài khoản ngân hàng nhận tiền, hướng dẫn mở tài khoản MBank và mẫu đăng ký TK MBank."
), agents=["bieu_mau"], agents_exact=True, pipeline_any=PIPE_COMPLEX, planner=True,
  must_any=["9.000.000", "MBank", "26-Dang_ky"], tags=["planner", "bieu_mau"])

c("L4-10", "L4", "HK điểm + tra cứu", (
    "Bảng điểm học kỳ 1 năm 2024-2025 đợt 2 của KMA gồm những học phần/khóa nào, "
    "file PDF tên gì, và sinh viên tra cứu điểm cá nhân theo MSSV cần lưu ý gì?"
), agents=["diem_thi"], agents_exact=True, pipeline_any=PIPE_COMPLEX, planner=True,
  must_any=["hk1_20242025_dot2"], tags=["planner", "diem_thi"])


# ═══ L5 — Multi-turn (8) ═══════════════════════════════════════════════════
mt("L5-01", "L5", "Follow-up biểu mẫu", [
    {"q": "Cho tôi biết đơn xin nghỉ học dưới 7 ngày của KMA.",
     "exp": {"agents": ["bieu_mau"], "agents_exact": True, "supervisor_intent": "form_procedure"}},
    {"q": "Còn nếu nghỉ trên 7 ngày thì sao?",
     "exp": {"agents": ["bieu_mau"], "was_rewritten": True, "must_any": ["09-Don", "trên 7"]},
     "rubric": {"must_contain_any": ["09-Don", "trên 7", "7 ngày"]}},
], agents=["bieu_mau"], tags=["memory", "rewrite"])

mt("L5-02", "L5", "Follow-up tuyển sinh", [
    {"q": "Điểm trúng tuyển CNTT Hà Nội năm 2024 của KMA?",
     "exp": {"agents": ["tuyen_sinh"], "agents_exact": True, "not_agents": ["diem_thi"]}},
    {"q": "Còn an toàn thông tin thì điểm bao nhiêu?",
     "exp": {"agents": ["tuyen_sinh"], "was_rewritten": True},
     "rubric": {"must_contain_any": ["25.90", "25.95", "25,95", "ATTT", "an toàn"]}},
], agents=["tuyen_sinh"], tags=["memory", "rewrite"])

mt("L5-03", "L5", "Follow-up ma trận", [
    {"q": "Ma trận đề thi Tin học đại cương có bao nhiêu câu?",
     "exp": {"agents": ["ma_tran"], "agents_exact": True}},
    {"q": "Thời gian làm bài là bao lâu?",
     "exp": {"agents": ["ma_tran"], "was_rewritten": True},
     "rubric": {"must_contain_any": ["60", "phút"]}},
], agents=["ma_tran"], tags=["memory", "rewrite"])

mt("L5-04", "L5", "Đổi mảng giữa phiên", [
    {"q": "Chuẩn TOEIC trước khi làm đồ án tốt nghiệp KMA?",
     "exp": {"agents": ["khao_thi"], "agents_exact": True}},
    {"q": "Giờ cho tôi mẫu đơn phúc khảo bài thi.",
     "exp": {"agents": ["bieu_mau"], "agents_exact": True, "supervisor_intent": "form_procedure"},
     "rubric": {"must_contain_any": ["phúc khảo", "15-Don"]}},
], agents=["bieu_mau"], primary="bieu_mau", tags=["memory", "topic_shift"])

mt("L5-05", "L5", "Đại từ — điền đơn", [
    {"q": "Tôi cần giấy xác nhận sinh viên để vay vốn ngân hàng.",
     "exp": {"agents": ["bieu_mau"], "agents_exact": True}},
    {"q": "Điền giúp tôi đơn đó được không?",
     "exp": {"pipeline_any": ["form_fill"], "agents": ["bieu_mau"]},
     "rubric": {"must_contain_any": ["điền", "mục", "họ tên", "xác nhận"]}},
], agents=["bieu_mau"], pipeline_any=PIPE_FORM, tags=["form_fill", "memory"])

mt("L5-06", "L5", "Follow-up điểm MSSV", [
    {"q": "CT060310 điểm học kỳ 2 năm 2024-2025 đợt 1",
     "exp": {"agents": ["diem_thi"], "agents_exact": True, "supervisor_intent": "grade_result",
             "pipeline_any": PIPE_GRADE}},
    {"q": "Liệt kê các môn và điểm của bạn ấy.",
     "exp": {"agents": ["diem_thi"], "was_rewritten": True},
     "rubric": {"must_contain_any": ["CT060310"], "must_not_contain": []}},
], agents=["diem_thi"], tags=["memory", "grade_lookup"])

mt("L5-07", "L5", "Off-topic chen giữa", [
    {"q": "Quy định miễn thi chuẩn tiếng Anh đầu ra KMA?",
     "exp": {"agents": ["khao_thi"], "agents_exact": True}},
    {"q": "Cho em hỏi giá Bitcoin hôm nay?",
     "exp": {"in_scope": False, "scope_category": "off_topic", "pipeline_any": PIPE_GUARDRAIL}},
    {"q": "Vậy TOEIC tối thiểu trước đồ án là bao nhiêu?",
     "exp": {"agents": ["khao_thi"]},
     "rubric": {"must_contain_any": ["450"]}},
], agents=["khao_thi"], tags=["memory", "guardrail_mid"])

mt("L5-08", "L5", "Hai mảng trong phiên", [
    {"q": "Em cần biết điểm trúng tuyển CNTT 2024 và học phí tạm thu HK1 khi nhập học.",
     "exp": {"agents": ["tuyen_sinh", "bieu_mau"], "min_agents": 2}},
    {"q": "Tóm lại em phải chuẩn bị bao nhiêu tiền mặt theo hướng dẫn nhập học?",
     "exp": {"agents": ["bieu_mau"]},
     "rubric": {"must_contain_any": ["10.896", "10896940"]}},
], agents=["bieu_mau", "tuyen_sinh"], tags=["memory", "multi_topic"])


# ═══ L6 — Form / catalog (4) ═══════════════════════════════════════════════
c("L6-01", "L6", "Catalog BHYT ATTT", "Trong catalog biểu mẫu KMA, mẫu khai BHYT sinh viên ATTT và file hướng dẫn khai BHYT tên gì?",
  agents=["bieu_mau"], agents_exact=True, supervisor_intent="form_procedure",
  pipeline_any=PIPE_SIMPLE, must_any=["24-Mau_khai_BHYT", "25-Huong_dan_khai_BHYT"], tags=["catalog"])

c("L6-02", "L6", "Điền đơn xác nhận SV", "Điền giúp tôi giấy xác nhận sinh viên.",
  agents=["bieu_mau"], pipeline_any=PIPE_FORM,
  must_any=["điền", "mục", "họ tên", "xác nhận"], tags=["form_fill"])

c("L6-03", "L6", "Tải đơn bảo lưu", "Tôi muốn tải đơn bảo lưu kết quả học tập — cho tên file trong catalog KMA.",
  agents=["bieu_mau"], agents_exact=True, pipeline_any=PIPE_SIMPLE,
  must_any=["10-Don_bao_luu", "bảo lưu"], tags=["catalog"])

c("L6-04", "L6", "Điểm chuẩn — routing negative", "Điểm chuẩn ngành DTVT năm 2024 của KMA?",
  agents=["tuyen_sinh"], agents_exact=True, not_agents=["diem_thi"],
  supervisor_intent="single_domain", pipeline_any=PIPE_SIMPLE,
  must_any=["24.5", "24,5", "25.0", "25.35", "DTVT"], tags=["routing", "tuyen_sinh"])

# Bổ sung đủ 80 case — phủ thêm fact đơn + routing
c("L1-15", "L1", "SĐT tuyển sinh", "Số điện thoại liên hệ tuyển sinh KMA trong đề án 2025?",
  agents=["tuyen_sinh"], agents_exact=True, pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  gold=["0986622772"], sources=["01_de_an_tuyen_sinh_2025.pdf"], tags=["tuyen_sinh"])

c("L1-16", "L1", "Phương thức TS 2025", "Phương thức tuyển sinh đại học chính quy KMA năm 2025 là gì?",
  agents=["tuyen_sinh"], agents_exact=True, pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  must_any=["xét tuyển", "THPT"], sources=["01_de_an_tuyen_sinh_2025.pdf"], tags=["tuyen_sinh"])

c("L2-17", "L2", "Điểm trúng tuyển CNTT 2024", "Điểm trúng tuyển ngành Công nghệ thông tin (Hà Nội) năm 2024 theo đề án KMA?",
  agents=["tuyen_sinh"], agents_exact=True, not_agents=["diem_thi"],
  pipeline_any=PIPE_MEDIUM, qc_min=0.35, gold=["26.20"], tags=["tuyen_sinh"])

c("L2-18", "L2", "KTX nhập học", "Học viện có ký túc xá cho sinh viên hệ đóng học phí khi nhập học không?",
  agents=["bieu_mau"], agents_exact=True, pipeline_any=PIPE_SIMPLE + PIPE_MEDIUM,
  must_any=["không có", "Ký túc xá"], sources=["Thu_tuc_nhap_hoc_2024.pdf"], tags=["bieu_mau"])

c("L3-13", "L3", "Điểm DTVT + phiếu ra trường", (
    "Điểm trúng tuyển ngành Điện tử viễn thông 2025 và mẫu phiếu thanh toán ra trường cá nhân 2026 trong tài liệu KMA?"
), agents=["tuyen_sinh", "bieu_mau"], primary="tuyen_sinh", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI,
  sources=["10_trung_tuyen_dtvt_2025.pdf", "13-Phieu_thanh_toan"], tags=["multi_agent"])

c("L3-14", "L3", "Ma trận kiểm thử + quy chế", (
    "Môn Kiểm thử an toàn hệ thống thông tin thuộc ma trận nào? "
    "Quy chế đào tạo 2025 áp dụng cho cơ sở Hà Nội và TP.HCM không?"
), agents=["ma_tran", "khao_thi"], primary="ma_tran", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI,
  sources=["20_ma_tran_kiem_thu_athttt.pdf"], tags=["multi_agent"])

c("L4-11", "L4", "Ba mảng tân SV", (
    "Tân sinh viên KMA: điểm chuẩn CNTT 2024, tổng tiền nhập học 2024, và mẫu đơn đăng ký học — "
    "trả lời từng phần theo tài liệu."
), agents=["tuyen_sinh", "bieu_mau"], primary="tuyen_sinh", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI + PIPE_COMPLEX, planner=True,
  must_any=["26.20", "26.60", "10.896", "04-Don"], tags=["planner", "multi_agent"])

c("L4-12", "L4", "Chuẩn NN đầy đủ", (
    "Tổng hợp: TOEIC sau TA1, TA2, TA3, trước đồ án và điều kiện công nhận VSTEP theo quy định chuẩn ngoại ngữ KMA."
), agents=["khao_thi"], agents_exact=True, pipeline_any=PIPE_COMPLEX, planner=True,
  must_any=["300", "350", "450", "VSTEP"], tags=["planner", "khao_thi"])

mt("L5-09", "L5", "Điểm chuẩn follow-up", [
    {"q": "Điểm chuẩn ngành CNTT năm 2024 của KMA?",
     "exp": {"agents": ["tuyen_sinh"], "agents_exact": True, "not_agents": ["diem_thi"]}},
    {"q": "Năm 2023 thì sao?",
     "exp": {"agents": ["tuyen_sinh"], "was_rewritten": True},
     "rubric": {"must_contain_any": ["25.5", "25,5", "2023"]}},
], agents=["tuyen_sinh"], tags=["memory", "admission"])

mt("L5-10", "L5", "MSSV + học kỳ follow-up", [
    {"q": "CT060310 điểm học kỳ 2 năm 2024-2025 đợt 1",
     "exp": {"agents": ["diem_thi"], "pipeline_any": PIPE_GRADE, "supervisor_intent": "grade_result"}},
    {"q": "Có môn nào không đạt không?",
     "exp": {"agents": ["diem_thi"]},
     "rubric": {"must_contain_any": ["CT060310", "Không đạt", "không đạt", "Đạt", "đạt"]}},
], agents=["diem_thi"], tags=["memory", "grade_lookup"])


# ═══ Mở rộng → 100 case (+20) ═══════════════════════════════════════════════

# L0 +2
c("L0-07", "L0", "Tạm biệt", "Tạm biệt nhé, hẹn gặp lại!",
  agents=[], in_scope=False, scope="chitchat", pipeline_any=PIPE_GUARDRAIL, tags=["chitchat"])

c("L0-08", "L0", "Off-topic y tế", "Thuốc hạ sốt cho trẻ 5 tuổi uống liều bao nhiêu?",
  agents=[], in_scope=False, scope="off_topic", pipeline_any=PIPE_GUARDRAIL,
  must_any=["ngoài phạm vi", "KMA"], tags=["off_topic"])

# L1 +4
c("L1-17", "L1", "Địa chỉ PHCM", "Địa chỉ Phân hiệu KMA tại TP.HCM theo đề án tuyển sinh 2025?",
  agents=["tuyen_sinh"], agents_exact=True, supervisor_intent="single_domain",
  pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  must_any=["Cộng Hòa", "Tân Bình", "TP.HCM"], sources=["01_de_an_tuyen_sinh_2025.pdf"], tags=["tuyen_sinh"])

c("L1-18", "L1", "Phân hiệu quy chế", "Quy chế đào tạo KMA 2025 có áp dụng cho Phân hiệu TP.HCM không?",
  agents=["khao_thi"], agents_exact=True, pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  must_any=["Phân hiệu", "Hồ Chí Minh", "Hà Nội"], sources=["25_quy_che_dao_tao_dai_hoc_2025.pdf"], tags=["khao_thi"])

c("L1-19", "L1", "Đơn cấp lại thẻ SV", "Sinh viên mất thẻ sinh viên cần đơn nào trong catalog KMA?",
  agents=["bieu_mau"], agents_exact=True, supervisor_intent="form_procedure",
  pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  must_any=["06-Don_cap_lai_the", "thẻ sinh viên"], tags=["bieu_mau", "catalog"])

c("L1-20", "L1", "Ma trận ATHT", "Môn Kiểm thử an toàn hệ thống thông tin có trong ma trận đề thi KMA không?",
  agents=["ma_tran"], agents_exact=True, not_agents=["khao_thi"],
  pipeline_any=PIPE_SIMPLE, qc_max=0.55,
  sources=["20_ma_tran_kiem_thu_athttt.pdf"], tags=["ma_tran"])

# L2 +4
c("L2-19", "L2", "Cú pháp chuyển khoản", "Cú pháp nộp kinh phí nhập học vào tài khoản MB theo hướng dẫn KMA 2024?",
  agents=["bieu_mau"], agents_exact=True, pipeline_any=PIPE_MEDIUM, qc_min=0.40,
  must_any=["0021145666888", "Mã trúng tuyển"], sources=["Thu_tuc_nhap_hoc_2024.pdf"], tags=["bieu_mau"])

c("L2-20", "L2", "Kết quả CT4", "Tài liệu kết quả tốt nghiệp CT4 năm 2024 của KMA dùng để tra cứu thông tin gì?",
  agents=["diem_thi"], agents_exact=True, pipeline_any=PIPE_MEDIUM, qc_min=0.40,
  sources=["04_ket_qua_tot_nghiep_ct4_2024.pdf"], tags=["diem_thi"])

c("L2-21", "L2", "Chỉ tiêu CNTT 2025", "Chỉ tiêu tuyển sinh ngành Công nghệ thông tin năm 2025 của KMA là bao nhiêu?",
  agents=["tuyen_sinh"], agents_exact=True, not_agents=["diem_thi"],
  pipeline_any=PIPE_MEDIUM, qc_min=0.35,
  sources=["01_de_an_tuyen_sinh_2025.pdf"], tags=["tuyen_sinh"])

c("L2-22", "L2", "Miễn thi NN", "Sinh viên có thể được miễn thi chuẩn tiếng Anh đầu ra theo quy định KMA trong trường hợp nào?",
  agents=["khao_thi"], agents_exact=True, pipeline_any=PIPE_MEDIUM, qc_min=0.40,
  sources=["03_quy_dinh_chuan_ngoai_ngu_2025.pdf"], tags=["khao_thi"])

# L3 +3
c("L3-15", "L3", "Thi TN + đơn phúc khảo", (
    "KMA có hướng dẫn thi tốt nghiệp online không? "
    "Và sinh viên phúc khảo bài thi dùng đơn nào trong catalog?"
), agents=["khao_thi", "bieu_mau"], primary="khao_thi", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI,
  must_any=["thi tốt nghiệp", "phúc khảo", "15-Don"], tags=["multi_agent"])

c("L3-16", "L3", "Điểm chuẩn + quy chế tín chỉ", (
    "Điểm trúng tuyển ngành An toàn thông tin Hà Nội năm 2024? "
    "Quy chế đào tạo 2025 quy định chương trình học theo đơn vị gì?"
), agents=["tuyen_sinh", "khao_thi"], primary="tuyen_sinh", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI,
  must_any=["25.90", "25.95", "tín chỉ"], tags=["multi_agent"])

c("L3-17", "L3", "Catalog thực tập + CDIO", (
    "Tên file giấy giới thiệu thực tập trong catalog KMA? "
    "Chương trình CNTT được xây dựng theo hướng tiếp cận nào?"
), agents=["bieu_mau", "tuyen_sinh"], primary="bieu_mau", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI,
  must_any=["18-Giay", "CDIO"], tags=["multi_agent"])

# L4 +3
c("L4-13", "L4", "Nhập học đầy đủ", (
    "Tân sinh viên KMA 2024: tổng tiền nhập học, có ký túc xá không, "
    "cú pháp chuyển khoản MB và mẫu đăng ký tài khoản MBank — trả lời theo hướng dẫn nhập học."
), agents=["bieu_mau"], agents_exact=True, pipeline_any=PIPE_COMPLEX, planner=True,
  must_any=["10.896", "MBank", "26-Dang_ky", "0021145666888"], tags=["planner", "bieu_mau"])

c("L4-14", "L4", "So sánh 3 ngành TS", (
    "So sánh điểm trúng tuyển năm 2024 của ngành CNTT, An toàn thông tin và Điện tử viễn thông "
    "(cơ sở Hà Nội) theo đề án tuyển sinh KMA."
), agents=["tuyen_sinh"], agents_exact=True, pipeline_any=PIPE_COMPLEX, planner=True,
  must_any=["26.20", "26.60", "25.90", "25.95", "25.0", "25.35"], tags=["planner", "compare", "tuyen_sinh"])

c("L4-15", "L4", "Điểm + đơn + ma trận", (
    "Sinh viên AT200106 đạt tiếng Anh đầu vào 2024 chưa? "
    "Đơn xin hoãn thi tên file gì? "
    "Ma trận Tin học đại cương có bao nhiêu câu và thời gian thi?"
), agents=["diem_thi", "bieu_mau", "ma_tran"], primary="diem_thi", min_agents=2,
  supervisor_intent="multi_domain", pipeline_any=PIPE_MULTI + PIPE_COMPLEX, planner=True,
  must_any=["AT200106", "14-Don", "50", "60"], tags=["planner", "multi_agent"])

# L5 +2
mt("L5-11", "L5", "Follow-up khao_thi", [
    {"q": "TOEIC tối thiểu sau Tiếng Anh 1 của KMA là bao nhiêu?",
     "exp": {"agents": ["khao_thi"], "agents_exact": True}},
    {"q": "Còn sau Tiếng Anh 2 thì sao?",
     "exp": {"agents": ["khao_thi"], "was_rewritten": True},
     "rubric": {"must_contain_any": ["350", "3"]}},
], agents=["khao_thi"], tags=["memory", "rewrite"])

mt("L5-12", "L5", "Form → hủy", [
    {"q": "Điền giúp tôi đơn xin nghỉ học dưới 7 ngày.",
     "exp": {"pipeline_any": PIPE_FORM, "agents": ["bieu_mau"]}},
    {"q": "Thôi, hủy đi.",
     "exp": {"agents": ["bieu_mau"]},
     "rubric": {"must_contain_any": ["hủy", "dừng", "thôi", "bỏ"]}},
], agents=["bieu_mau"], pipeline_any=PIPE_FORM + PIPE_SIMPLE, tags=["form_fill", "cancel"])

# L6 +3
c("L6-05", "L6", "Đơn đăng ký học", "Trong catalog KMA, đơn đăng ký học tên file gì?",
  agents=["bieu_mau"], agents_exact=True, supervisor_intent="form_procedure",
  pipeline_any=PIPE_SIMPLE, must_any=["04-Don_dang_ky_hoc"], tags=["catalog"])

c("L6-06", "L6", "Điền đơn phúc khảo", "Điền giúp tôi đơn xin phúc khảo bài thi.",
  agents=["bieu_mau"], pipeline_any=PIPE_FORM,
  must_any=["điền", "phúc khảo", "mục"], tags=["form_fill"])


assert len(CASES) == 100, f"Expected 100 cases, got {len(CASES)}"


def _demo_for_turn(exp: dict, rub: dict) -> str:
    lines: list[str] = []
    if not exp.get("in_scope", True):
        if exp.get("scope_category") == "chitchat":
            lines.append(
                "Chào hỏi / giới thiệu trợ lý KMA và các mảng hỗ trợ. Không tra cứu tài liệu."
            )
        else:
            lines.append(
                "Từ chối nhẹ — câu ngoài phạm vi KMA. Gợi ý hỏi đúng mảng (tuyển sinh, quy chế, …)."
            )
        return "\n".join(lines)

    agents = exp.get("agents") or []
    if agents:
        lines.append(f"Mảng phù hợp: **{', '.join(agents)}** (gợi ý, không cần đúng pipeline).")
    if rub.get("gold_facts"):
        lines.append("**Phải có:** " + " · ".join(rub["gold_facts"]))
    if rub.get("must_contain_all"):
        lines.append("**Phải có đủ:** " + ", ".join(rub["must_contain_all"]))
    if rub.get("must_contain_any"):
        lines.append("**Phải có (một trong):** " + ", ".join(rub["must_contain_any"]))
    if rub.get("must_not_contain"):
        lines.append("**Không được:** " + ", ".join(rub["must_not_contain"]))
    if rub.get("source_file_any"):
        lines.append("**Tài liệu tham chiếu:** " + ", ".join(rub["source_file_any"]))
    return "\n".join(lines) if lines else "Trả lời đúng theo tài liệu KMA, khớp câu hỏi."


def attach_demo_blocks(cases: list[dict]) -> None:
    for case in cases:
        case.setdefault("scoring_mode", "content")
        if case.get("multi_turn"):
            turn_demos = []
            for t in case["turns"]:
                exp = {**case.get("expected", {}), **t.get("expected", {})}
                rub = {**case.get("rubric", {}), **t.get("rubric", {})}
                turn_demos.append(_demo_for_turn(exp, rub))
            case["demo"] = {
                "expected_answer": turn_demos,
                "how_to_test": "Gửi lần lượt các lượt trong CÙNG một cửa sổ chat (không F5).",
            }
        else:
            case["demo"] = {
                "expected_answer": _demo_for_turn(case.get("expected", {}), case.get("rubric", {})),
                "how_to_test": "Dán câu hỏi vào ô chat tại http://127.0.0.1:8000",
            }


def render_test_tay_md(cases: list, meta: dict) -> str:
    from collections import Counter

    lines = [
        "# Test tay — 100 câu hỏi KMA Chatbot",
        "",
        f"**Phiên bản:** {meta['version']} · **{len(cases)} câu**",
        "",
        meta["description"],
        "",
        "## Cách dùng",
        "",
        "1. Bật server: `uvicorn api.main:app --host 127.0.0.1 --port 8000`",
        "2. Mở http://127.0.0.1:8000",
        "3. **Copy** khối câu hỏi (```text```) → dán vào chat",
        "4. So sánh câu trả lời với **Câu trả lời đúng cần có**",
        "5. **L5 (multi-turn):** gửi lượt 1 → đợi trả lời → lượt 2 **cùng tab**, không refresh",
        "",
        "## Mục lục",
        "",
        "| ID | Tier | Tiêu đề |",
        "|----|------|---------|",
    ]
    for c in cases:
        lines.append(f"| [{c['id']}](#{c['id'].lower()}) | {c['tier']} | {c['title']} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    tier_labels = {
        "L0": "Guardrail — chào / off-topic",
        "L1": "Đơn giản — một mảng",
        "L2": "Trung bình — liệt kê, so sánh, tra điểm MSSV",
        "L3": "Hai mảng trở lên",
        "L4": "Câu dài / nhiều ý",
        "L5": "Nhiều lượt hội thoại",
        "L6": "Biểu mẫu / điền đơn",
    }
    current = None
    for case in cases:
        if case["tier"] != current:
            current = case["tier"]
            cnt = Counter(x["tier"] for x in cases)[current]
            lines.append(f"## {current} — {tier_labels.get(current, '')} ({cnt} câu)")
            lines.append("")

        lines.append(f"### {case['id']} — {case['title']}")
        lines.append("")

        demo = case.get("demo", {})
        if case.get("multi_turn"):
            lines.append(f"*{demo.get('how_to_test', '')}*")
            lines.append("")
            for i, t in enumerate(case["turns"], 1):
                ans = demo.get("expected_answer", [])
                exp_ans = ans[i - 1] if i - 1 < len(ans) else ""
                lines.append(f"#### Lượt {i}")
                lines.append("")
                lines.append("**Câu hỏi (copy):**")
                lines.append("```text")
                lines.append(t["question"].strip())
                lines.append("```")
                lines.append("")
                if exp_ans:
                    lines.append("**Câu trả lời đúng cần có:**")
                    lines.append("")
                    for ln in exp_ans.split("\n"):
                        lines.append(f"- {ln}")
                    lines.append("")
        else:
            lines.append("**Câu hỏi (copy):**")
            lines.append("```text")
            lines.append(case["turns"][0]["question"].strip())
            lines.append("```")
            lines.append("")
            exp_ans = demo.get("expected_answer", "")
            if exp_ans:
                lines.append("**Câu trả lời đúng cần có:**")
                lines.append("")
                for ln in str(exp_ans).split("\n"):
                    lines.append(f"- {ln}")
                lines.append("")
        if case.get("notes"):
            lines.append(f"*Ghi chú:* {case['notes']}")
            lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("*Nguồn máy đọc: `eval/benchmark.json` · Chấm tự động nội dung: `python eval/run_benchmark.py`*")
    return "\n".join(lines)


def render_md(cases: list, meta: dict) -> str:
    from collections import Counter

    lines = [
        "# Benchmark v2 — KMA Multi-Agent (Supervisor + Router)",
        "",
        f"**Phiên bản:** {meta['version']}  ",
        f"**Tổng case:** {len(cases)}  ",
        f"**API:** `{meta['api_endpoint']}`  ",
        "",
        meta["description"],
        "",
        "## Ngưỡng Router (Qc cục bộ, `KMA_ACCURACY_MODE=1`)",
        "",
        "| Qc | Pipeline |",
        "|----|----------|",
    ]
    for pipe, rule in meta.get("router_thresholds_local_qc", {}).items():
        lines.append(f"| {rule} | `{pipe}` |")
    lines.extend([
        "",
        "## Phân bổ tier",
        "",
        "| Tier | Mô tả | Số case |",
        "|------|--------|---------|",
    ])
    cnt = Counter(c["tier"] for c in cases)
    for tier, desc in meta["tier_distribution"].items():
        lines.append(f"| {tier} | {desc.split('(')[0].strip()} | {cnt.get(tier, 0)} |")
    lines.extend([
        "",
        "## Cách chạy",
        "",
        "```bash",
        "python eval/build_benchmark.py",
        "uvicorn api.main:app --host 127.0.0.1 --port 8000",
        "python ingest_all.py   # nếu đổi docs",
        "python eval/run_benchmark.py",
        "python eval/run_benchmark.py --tier L1",
        "python eval/run_benchmark.py --id L2-11",
        "```",
        "",
        "Môi trường: `KMA_FAST_MODE=0`, `KMA_ACCURACY_MODE=1`, Qdrant đã ingest.",
        "",
        "---",
        "",
    ])
    tier_names = {
        "L0": "Guardrail",
        "L1": "Đơn giản — Supervisor 1 agent + native/hybrid",
        "L2": "Trung bình — hybrid/agentic/grade_lookup",
        "L3": "Multi-agent — Supervisor multi_domain",
        "L4": "Phức tạp — Planner",
        "L5": "Multi-turn",
        "L6": "Biểu mẫu & form fill",
    }
    current_tier = None
    for case in cases:
        if case["tier"] != current_tier:
            current_tier = case["tier"]
            lines.append(f"## {current_tier} — {tier_names.get(current_tier, '')}")
            lines.append("")
        lines.append(f"### {case['id']} — {case['title']}")
        if case.get("multi_turn"):
            for i, t in enumerate(case["turns"], 1):
                lines.append(f"**Lượt {i}:** {t['question']}")
        else:
            lines.append(f"**Câu hỏi:** {case['turns'][0]['question']}")
        exp = case["expected"]
        ag = ", ".join(exp["agents"]) or "(không)"
        lines.append(f"**Agents:** `{ag}` | primary=`{exp.get('primary', '')}`")
        if exp.get("supervisor_intent"):
            lines.append(f"**Supervisor intent:** `{exp['supervisor_intent']}`")
        if exp.get("not_agents"):
            lines.append(f"**Không được dùng:** `{exp['not_agents']}`")
        if exp.get("min_agents"):
            lines.append(f"**Tối thiểu agents:** {exp['min_agents']}")
        lines.append(f"**Pipeline ∈** `{exp.get('pipeline_any', [])}`")
        if exp.get("planner_used"):
            lines.append("**Planner:** bật")
        rub = case.get("rubric", {})
        if rub.get("gold_facts"):
            lines.append(f"**Gold:** {'; '.join(rub['gold_facts'])}")
        if rub.get("must_contain_all"):
            lines.append(f"**Phải có:** {', '.join(rub['must_contain_all'])}")
        if rub.get("must_contain_any"):
            lines.append(f"**Phải có (một):** {', '.join(rub['must_contain_any'])}")
        if case.get("notes"):
            lines.append(f"*{case['notes']}*")
        lines.append("")
    lines.append("---")
    lines.append("*Machine-readable: `eval/benchmark.json`*")
    return "\n".join(lines)


def main():
    attach_demo_blocks(CASES)
    payload = {**META, "total_cases": len(CASES), "cases": CASES}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_TEST_TAY.write_text(render_test_tay_md(CASES, META), encoding="utf-8")
    OUT_TECH.write_text(render_md(CASES, META), encoding="utf-8")
    print(f"Wrote {OUT_JSON} ({len(CASES)} cases)")
    print(f"Wrote {OUT_TEST_TAY}  (mo file nay de test tay tren web)")
    print(f"Wrote {OUT_TECH} (kỹ thuật routing)")


if __name__ == "__main__":
    main()
