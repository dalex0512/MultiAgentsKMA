"""
Complexity Estimator — đánh giá Qc + intent (JSON có cấu trúc) cho Router pipeline.
"""

from __future__ import annotations

import json
import logging
import re

from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    LLM_MODEL,
    FAST_MODE,
    USE_LOCAL_QC,
    USE_QC_HYBRID,
    ACCURACY_MODE,
    ROUTER_T1,
    ROUTER_T2,
)
from pipelines.retrieval import extract_mssv
from agents.routing_intel import (
    ComplexityAssessment,
    INTENT_COMPARE,
    INTENT_FACTUAL,
    INTENT_GRADE_LOOKUP,
    INTENT_LIST,
    INTENT_MULTI_HOP,
    INTENT_PROCEDURAL,
    VALID_COMPLEXITY_INTENTS,
)

log = logging.getLogger(__name__)

openai_client = OpenAI(api_key=OPENAI_API_KEY)

COMPLEXITY_PROMPT = """\
Bạn là bộ phân tích độ phức tạp câu hỏi cho chatbot RAG của Học viện KMA (Học viện Kỹ thuật Mật mã).

Đánh giá câu hỏi sau theo 2 việc:
1) Chấm điểm 0–10 (0=rất đơn, 10=rất phức tạp).
2) Gán intent (chọn ĐÚNG MỘT):
   - fact_lookup: một thông tin cụ thể (mã, số, ngày, tên file, điều kiện đơn).
   - list_enumerate: liệt kê, có bao nhiêu, những môn/điều kiện nào.
   - compare: so sánh, khác nhau, trước/sau, A và B.
   - multi_hop: cần ghép nhiều thông tin hoặc suy luận nhiều bước.
   - procedural: quy trình, thủ tục, các bước làm đơn.
   - grade_lookup: điểm, bảng điểm, MSSV, kết quả thi, học kỳ của sinh viên.

needs_multi_doc: true nếu cần đọc nhiều đoạn/tài liệu; false nếu một chỗ là đủ.

Ví dụ:
- "Mã trường KMA là gì?" → score 2, fact_lookup, needs_multi_doc false
- "So sánh điểm chuẩn 2023 và 2024" → score 6, compare, needs_multi_doc true
- "Điểm HK1 của AT200201" → score 5, grade_lookup, needs_multi_doc true

Câu hỏi: {question}

Trả lời ĐÚNG MỘT JSON (không markdown):
{{"score_0_10": <int>, "intent": "<slug>", "needs_multi_doc": <true|false>, "reason": "<tiếng Việt ngắn>"}}"""

_COMPLEX_MARKERS = (
    " so sánh ", " khác nhau ", " đồng thời ", " tại sao ", " giải thích ",
    " liệt kê ", " các bước ", " quy trình đầy đủ ", " tổng hợp ", " phân tích ",
)

_ADMISSION_MARKERS = ("điểm chuẩn", "diem chuan", "ngưỡng", "trúng tuyển", "chỉ tiêu")
_GRADE_MARKERS = ("điểm", "diem", "bảng điểm", "bang diem", "mssv", "at20", "học kỳ", "hoc ky")


def _parse_json(raw: str) -> dict | None:
    raw = raw.strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def _heuristic_assessment(question: str) -> ComplexityAssessment:
    q = question.strip()
    words = len(q.split())
    n_q = q.count("?")
    low = q.lower()

    if any(m in low for m in _ADMISSION_MARKERS):
        intent = INTENT_FACTUAL
        score = 3
    elif any(m in low for m in _GRADE_MARKERS) or re.search(r"\b(?:AT|CT)\d{6}\b", q, re.I):
        intent = INTENT_GRADE_LOOKUP
        score = 5
    elif any(m in low for m in _COMPLEX_MARKERS):
        if " so sánh " in low or " khác nhau " in low:
            intent = INTENT_COMPARE
        elif " các bước " in low or " quy trình " in low:
            intent = INTENT_PROCEDURAL
        elif " liệt kê " in low:
            intent = INTENT_LIST
        else:
            intent = INTENT_MULTI_HOP
        score = 7 if words >= 28 or n_q >= 2 else 5
    elif words <= 14 and n_q <= 1:
        intent = INTENT_FACTUAL
        score = 2
    elif " liệt kê " in low or " những " in low or " các " in low:
        intent = INTENT_LIST
        score = 4
    else:
        intent = INTENT_FACTUAL
        score = 4

    score = max(0, min(10, score))
    qc = round(score / 10.0, 3)
    multi = intent in (INTENT_COMPARE, INTENT_MULTI_HOP, INTENT_LIST, INTENT_GRADE_LOOKUP, INTENT_PROCEDURAL)
    return ComplexityAssessment(
        qc=qc,
        score_0_10=score,
        intent=intent,
        needs_multi_doc=multi,
        reason="Heuristic (FAST_MODE hoặc lỗi LLM).",
    )


_MULTI_PART_MARKERS = (
    " và ", " đồng thời ", " so sánh ", " khác nhau ", " cùng lúc ",
    " ngoài ra ", " đồng thời ", " ngoai ra ",
)


def _is_multi_part_question(question: str) -> bool:
    q = (question or "").strip()
    if not q:
        return False
    if q.count("?") >= 2:
        return True
    if len(q.split()) >= 24:
        return True
    low = f" {q.lower()} "
    return any(m in low for m in _MULTI_PART_MARKERS)


def _llm_assess(question: str) -> ComplexityAssessment:
    resp = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": COMPLEXITY_PROMPT.format(question=question)}],
        max_tokens=120,
        temperature=0.0,
    )
    raw = resp.choices[0].message.content.strip()
    data = _parse_json(raw)
    if not data:
        raise ValueError(f"Invalid JSON: {raw[:100]}")

    score = int(data.get("score_0_10", 5))
    score = max(0, min(10, score))
    intent = str(data.get("intent", INTENT_FACTUAL)).strip()
    if intent not in VALID_COMPLEXITY_INTENTS:
        intent = INTENT_MULTI_HOP if score >= 7 else (INTENT_LIST if score >= 5 else INTENT_FACTUAL)

    qc = round(score / 10.0, 3)
    multi = bool(data.get("needs_multi_doc", score >= 5))
    reason = str(data.get("reason", "")).strip() or "Đánh giá LLM."
    return ComplexityAssessment(
        qc=qc, score_0_10=score, intent=intent, needs_multi_doc=multi, reason=reason,
    )


def _needs_llm_qc_refine(local: ComplexityAssessment, question: str) -> bool:
    """Chỉ gọi LLM khi cần — ưu tiên chính xác cho câu nhiều ý / vùng ngưỡng."""
    if _is_multi_part_question(question):
        return True
    if local.intent in (
        INTENT_COMPARE, INTENT_MULTI_HOP, INTENT_PROCEDURAL, INTENT_LIST,
    ):
        return True
    margin = 0.07
    if (ROUTER_T1 - margin) <= local.qc <= (ROUTER_T2 + margin):
        return True
    return False


def assess_complexity_hybrid(
    question: str,
    *,
    similarity_scores: list[float] | None = None,
) -> ComplexityAssessment:
    """
    Qc cục bộ (E/R/L/S + prefetch S) làm nền; LLM bổ sung khi câu phức tạp / gần ngưỡng.
    qc_final = max(local, llm) — thiên leo pipeline khi nghi ngờ (accuracy-first).
    """
    from utils.qc_calculator import assess_complexity_local

    local = assess_complexity_local(question, similarity_scores)
    if not ACCURACY_MODE and not _needs_llm_qc_refine(local, question):
        return ComplexityAssessment(
            qc=local.qc,
            score_0_10=local.score_0_10,
            intent=local.intent,
            needs_multi_doc=local.needs_multi_doc,
            reason=f"Qc hybrid (cục bộ): {local.reason}",
        )

    try:
        llm = _llm_assess(question)
    except Exception as e:
        log.warning(f"[complexity:hybrid] LLM skip: {e}")
        return local

    qc = round(max(local.qc, llm.qc), 3)
    score_0_10 = max(local.score_0_10, llm.score_0_10)

    if local.intent == INTENT_GRADE_LOOKUP and extract_mssv(question):
        intent = INTENT_GRADE_LOOKUP
    elif llm.intent in (INTENT_COMPARE, INTENT_MULTI_HOP, INTENT_PROCEDURAL, INTENT_LIST):
        intent = llm.intent
    elif llm.qc > local.qc + 0.12:
        intent = llm.intent
    else:
        intent = local.intent

    multi = local.needs_multi_doc or llm.needs_multi_doc
    reason = (
        f"Qc hybrid: cục bộ={local.qc:.3f} ({local.intent}); "
        f"LLM={llm.qc:.3f} ({llm.intent}) → qc={qc:.3f}, intent={intent}. "
        f"{llm.reason}"
    )
    log.info("[complexity:hybrid] qc=%s intent=%s (local=%s llm=%s)", qc, intent, local.qc, llm.qc)
    return ComplexityAssessment(
        qc=qc,
        score_0_10=score_0_10,
        intent=intent,
        needs_multi_doc=multi,
        reason=reason,
    )


def assess_complexity(
    question: str,
    *,
    similarity_scores: list[float] | None = None,
) -> ComplexityAssessment:
    question = (question or "").strip()
    if not question:
        return ComplexityAssessment(0.0, 0, INTENT_FACTUAL, False, "Câu rỗng.")

    if FAST_MODE:
        a = _heuristic_assessment(question)
        log.debug(f"[complexity:fast] qc={a.qc} intent={a.intent}")
        return a

    if USE_QC_HYBRID and USE_LOCAL_QC:
        return assess_complexity_hybrid(question, similarity_scores=similarity_scores)

    if USE_LOCAL_QC:
        from utils.qc_calculator import assess_complexity_local
        return assess_complexity_local(question, similarity_scores)

    try:
        return _llm_assess(question)
    except Exception as e:
        log.warning(f"[complexity] LLM failed: {e}")
        return _heuristic_assessment(question)


def estimate(question: str) -> float:
    """API tương thích cũ — chỉ trả Qc."""
    return assess_complexity(question).qc
