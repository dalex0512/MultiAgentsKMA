"""
Kiểm tra offline routing accuracy (Supervisor keyword/fallback + Qc local).
Chạy: python -m eval.test_routing_offline
"""

from __future__ import annotations

import json
from pathlib import Path

from agents.supervisor import _keyword_fallback, route as supervisor_route
from agents.routing_intel import SUP_INTENT_MULTI
from agents.planner import plan_questions, _grade_policy_presplit
from agents.complexity_estimator import assess_complexity
from pipelines.retrieval import extract_all_mssv, _is_english_classification_query, _keyword_adjust
from pipelines.specialist_runner import _is_policy_only_query, _should_grade_lookup
from agents.router import route_pipeline
from agents.guardrail import check_scope
from config import ACCURACY_MODE, SUPERVISOR_FAST_PATH, USE_LOAD_ROUTER


def _load_cases():
    path = Path(__file__).parent / "routing_accuracy_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def test_supervisor_keyword_fallback():
    cases = _load_cases()
    failed = []
    for c in cases:
        if c.get("expect_intent"):
            dec = supervisor_route(c["question"])
            if c["expect_intent"] not in (dec.intent,):
                failed.append((c["id"], f"intent want {c['expect_intent']}, got {dec.intent}"))
        else:
            dec = _keyword_fallback(c["question"])
        for aid in c.get("expect_agents", []):
            if aid not in dec.agents:
                failed.append((c["id"], f"missing agent {aid} in {dec.agents}"))
        for aid in c.get("expect_not_agents", []):
            if aid in dec.agents:
                failed.append((c["id"], f"unwanted agent {aid} in {dec.agents}"))
    return failed


def test_qc_admission_not_grade_intent():
    q = "Điểm chuẩn CNTT 2024"
    a = assess_complexity(q)
    if a.intent == "grade_lookup":
        return [("R-01-qc", f"intent should not be grade_lookup, got {a.intent}")]
    return []


def test_grade_lookup_system_prompt():
    """PERSONA_ACCURACY_SUFFIX trên specialist không được dùng cho grade_lookup."""
    from pipelines.grade_lookup import build_grade_lookup_system
    from pipelines.rag_prompts import PERSONA_ACCURACY_SUFFIX
    from pipelines.specialist_runner import _persona_system

    gsys = build_grade_lookup_system()
    psys = _persona_system("diem_thi", "")
    if PERSONA_ACCURACY_SUFFIX.strip() in gsys:
        return [("grade-sys", "grade_lookup system must not include PERSONA_ACCURACY_SUFFIX")]
    if "PHẢI trả lời" not in gsys and "liệt kê đủ" not in gsys:
        return [("grade-sys", "grade_lookup system missing answer/list rule")]
    if PERSONA_ACCURACY_SUFFIX.strip() not in psys:
        return [("grade-sys", "sanity: diem_thi persona should still have accuracy suffix for RAG")]
    return []


def test_guardrail_scope():
    """Guardrail — off_topic / chitchat / MSSV in-scope (không cần API)."""
    failed = []

    r = check_scope("Điểm chuẩn Đại học Bách Khoa Hà Nội năm 2025?")
    if r.in_scope or r.category != "off_topic":
        failed.append(("G-01", f"Bách Khoa should be off_topic, got {r.category} in_scope={r.in_scope}"))

    r = check_scope("Bạn có thể giúp gì cho sinh viên KMA?")
    if r.category != "chitchat":
        failed.append(("G-02", f"capability should be chitchat, got {r.category}"))

    r = check_scope(
        "Mã sinh viên AT200201 có đạt kiểm tra phân loại tiếng Anh đầu vào khóa A20C8D7 năm 2024 (lần 2) không?"
    )
    if not r.in_scope or r.category != "kma":
        failed.append(("G-03", f"MSSV TA should be in_scope kma, got {r.category} in_scope={r.in_scope}"))

    return failed


def test_supervisor_live_route():
    """Supervisor.route (heuristic) — MSSV + multi-domain."""
    failed = []
    dec = supervisor_route(
        "Mã sinh viên AT200201 có đạt kiểm tra phân loại tiếng Anh đầu vào khóa A20C8D7 năm 2024 (lần 2) không?"
    )
    if "diem_thi" not in dec.agents:
        failed.append(("S-07", f"MSSV route missing diem_thi: {dec.agents}"))
    if "khao_thi" in dec.agents:
        failed.append(("S-07", f"single MSSV TA should not include khao_thi: {dec.agents}"))

    dec = supervisor_route(
        "Theo đề án tuyển sinh KMA 2025, phương thức tuyển sinh đại học chính quy là gì? "
        "Đồng thời theo hướng dẫn nhập học 2024, tổng số tiền phải nộp khi làm thủ tục là bao nhiêu?"
    )
    for aid in ("tuyen_sinh", "bieu_mau"):
        if aid not in dec.agents:
            failed.append(("S-08", f"multi-domain missing {aid} in {dec.agents}"))

    dec = supervisor_route(
        "Chuẩn TOEIC tối thiểu trước khi nhận đề tài đồ án của KMA là bao nhiêu? "
        "Và sinh viên AT200106 có đạt tiếng Anh đầu vào khóa A20C8D7 2024 (lần 2) không?"
    )
    for aid in ("diem_thi", "khao_thi"):
        if aid not in dec.agents:
            failed.append(("S-09", f"L3-03 compound missing {aid} in {dec.agents}"))
    if dec.intent != SUP_INTENT_MULTI:
        failed.append(("S-09", f"L3-03 intent should be multi_domain, got {dec.intent}"))

    dec = supervisor_route(
        "Cho biet AT200401 va AT200201 trong ket qua phan loai tieng Anh dau vao A20C8D7 2024 lan 2. "
        "Diem TOEIC toi thieu truoc de tai do an la bao nhieu?"
    )
    for aid in ("diem_thi", "khao_thi"):
        if aid not in dec.agents:
            failed.append(("S-10", f"L4-06 compound missing {aid} in {dec.agents}"))
    if dec.intent != SUP_INTENT_MULTI:
        failed.append(("S-10", f"L4-06 intent should be multi_domain, got {dec.intent}"))

    return failed


def test_planner_grade_policy_presplit():
    q = (
        "Cho biet AT200401 va AT200201 trong ket qua phan loai tieng Anh dau vao A20C8D7 2024 lan 2. "
        "Diem TOEIC toi thieu truoc de tai do an la bao nhieu?"
    )
    failed = []
    subs = _grade_policy_presplit(q)
    if not subs or len(subs) != 2:
        failed.append(("P-01", f"presplit expected 2 subs, got {subs}"))
    plan = plan_questions(q)
    if not plan.use_decomposition or len(plan.sub_questions) < 2:
        failed.append(("P-01", f"planner should decompose compound, got {plan.sub_questions}"))
    return failed


def test_extract_all_mssv_l4():
    q = (
        "Cho biet AT200401 va AT200201 trong ket qua phan loai tieng Anh dau vao A20C8D7 2024 lan 2."
    )
    mssvs = extract_all_mssv(q)
    if mssvs != ["AT200401", "AT200201"]:
        return [("M-01", f"expected both MSSVs, got {mssvs}")]
    return []


def test_grade_lookup_policy_guard():
    """grade_lookup không chạy cho sub-q thuần TOEIC."""
    rq = "Điểm TOEIC tối thiểu trước đề tài đồ án theo quy định chuẩn ngoại ngữ KMA là bao nhiêu?"
    if not _is_policy_only_query(rq):
        return [("GL-01", "TOEIC-only query should be policy-only")]
    assessment = assess_complexity(rq)
    if _should_grade_lookup("diem_thi", rq, rq, assessment):
        return [("GL-01", "grade_lookup should be off for policy-only sub-q")]
    return []


def test_english_classification_keyword_boost():
    q = "AT200201 phan loai tieng Anh dau vao A20C8D7 2024 lan 2"
    if not _is_english_classification_query(q):
        return [("R-EN", "should detect English classification query")]
    good = {"source": "diem_thi/08_ket_qua_thi_anh_van_2024.pdf", "text": "AT200201"}
    bad = {"source": "diem_thi/hk1_20242025_dot1.pdf", "text": "AT200201"}
    if _keyword_adjust(q, good, "diem_thi") <= _keyword_adjust(q, bad, "diem_thi"):
        return [("R-EN", "08_ket_qua should rank above hk1 for TA query")]
    return []


def main():
    print(f"ACCURACY_MODE={ACCURACY_MODE} SUPERVISOR_FAST_PATH={SUPERVISOR_FAST_PATH} USE_LOAD_ROUTER={USE_LOAD_ROUTER}")
    all_fail = []
    all_fail.extend(test_supervisor_keyword_fallback())
    all_fail.extend(test_supervisor_live_route())
    all_fail.extend(test_planner_grade_policy_presplit())
    all_fail.extend(test_extract_all_mssv_l4())
    all_fail.extend(test_grade_lookup_policy_guard())
    all_fail.extend(test_english_classification_keyword_boost())
    all_fail.extend(test_guardrail_scope())
    all_fail.extend(test_qc_admission_not_grade_intent())
    all_fail.extend(test_grade_lookup_system_prompt())
    if all_fail:
        for fid, msg in all_fail:
            print(f"FAIL {fid}: {msg}")
        raise SystemExit(1)
    n = len(_load_cases())
    print(f"OK — {n} routing cases + Qc admission + grade_lookup prompt")


if __name__ == "__main__":
    main()
