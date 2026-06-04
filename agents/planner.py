"""
Question Planner — tách câu hỏi phức tạp thành sub-questions (Phase 3).
Mỗi sub-question được Supervisor gán agent riêng.
"""

import json
import logging
import re
from dataclasses import dataclass, field

from openai import OpenAI
from config import LLM_MODEL, OPENAI_API_KEY, PLANNER_MAX_SUB_QUESTIONS, PLANNER_MIN_WORDS
from agents.complexity_estimator import assess_complexity
from agents.conversation_context import format_history_text

log = logging.getLogger(__name__)

openai_client = OpenAI(api_key=OPENAI_API_KEY)

PLANNER_PROMPT = """\
Bạn là Planner của chatbot KMA. Tách câu hỏi thành các ý con (sub-question) độc lập để từng chuyên gia trả lời.

Tóm tắt phiên:
{session_summary}

Hội thoại gần đây:
{history_text}

Câu hỏi (đã làm rõ):
{question}

Quy tắc:
- Nếu câu chỉ MỘT ý đơn giản → trả sub_questions có 1 phần tử (giữ nguyên câu).
- Nếu nhiều ý (so sánh, và, đồng thời, nhiều mảng: tuyển sinh + biểu mẫu + quy chế...) → tách tối đa {max_n} câu con, mỗi câu đủ nghĩa.
- Câu gộp MSSV/kết quả TA + TOEIC/chuẩn ngoại ngữ/đồ án → tách 2 câu: (1) tra MSSV/kết quả TA, (2) TOEIC/quy chế.
- Không trả lời nội dung, chỉ JSON.

Ví dụ tách:
Q: "AT200401 và AT200201 trong phân loại TA A20C8D7 2024 lần 2, TOEIC tối thiểu trước đồ án?"
→ ["Cho biết AT200401 và AT200201 trong kết quả phân loại tiếng Anh đầu vào A20C8D7 2024 lần 2.",
   "Điểm TOEIC tối thiểu trước đề tài đồ án theo quy định chuẩn ngoại ngữ KMA là bao nhiêu?"]

Trả lời ĐÚNG MỘT JSON:
{{"sub_questions": ["câu 1", "câu 2"], "reason": "giải thích ngắn"}}"""


@dataclass
class PlanResult:
    sub_questions:  list[str]
    use_decomposition: bool
    reason:         str = ""


_COMPLEX_MARKERS = (
    " và ", " đồng thời ", " so sánh ", " khác nhau ", " cùng lúc ",
    " ngoài ra ", " đồng thời ", " các môn ", " các điều ", " những ",
)

_MSSV_RE = re.compile(r"\b(?:AT|CT|DT)\d{6}\b", re.IGNORECASE)
_GRADE_MARKERS = (
    "phân loại", "phan loai", "tiếng anh", "tieng anh", "đầu vào", "dau vao",
    "kết quả", "ket qua", "đạt", "dat", "bảng điểm", "bang diem",
)
_POLICY_MARKERS = (
    "toeic", "vstep", "chuẩn ngoại ngữ", "chuan ngoai ngu",
    "chuẩn đầu ra", "chuan dau ra", "quy chế", "quy che",
    "đồ án", "do an", "de tai do an", "đề tài đồ án",
    "trước khi nhận đề tài", "truoc khi nhan de tai",
    "trước đồ án", "truoc do an",
)


def _is_schedule_list_question(question: str) -> bool:
    try:
        from utils.rag.schedule_lookup import wants_schedule_table_query
        return wants_schedule_table_query(question)
    except Exception:
        return False


def _is_exam_list_question(question: str) -> bool:
    try:
        from utils.rag.exam_list_lookup import wants_exam_list_query
        return wants_exam_list_query(question)
    except Exception:
        return False


def _heuristic_complex(question: str) -> bool:
    q = question.strip()
    if _is_schedule_list_question(q) or _is_exam_list_question(q):
        return False
    if _grade_policy_presplit(q):
        return True
    words = len(q.split())
    if words >= PLANNER_MIN_WORDS:
        return True
    if q.count("?") >= 2:
        return True
    if assess_complexity(q).qc >= 0.62:
        return True
    low = q.lower()
    return any(m in low for m in _COMPLEX_MARKERS)


def _grade_policy_presplit(question: str) -> list[str] | None:
    """Tách cố định MSSV/kết quả TA + TOEIC/quy chế."""
    if not _MSSV_RE.search(question):
        return None
    low = question.lower()
    has_grade = any(m in low for m in _GRADE_MARKERS)
    has_policy = any(m in low for m in _POLICY_MARKERS)
    if not (has_grade and has_policy):
        return None

    policy_part = question
    grade_part = question
    for sep in (". ", "? ", ".\n", "?\n"):
        if sep.strip() in question:
            parts = re.split(r"[.?]\s+", question, maxsplit=1)
            if len(parts) == 2:
                p0, p1 = parts[0].strip(), parts[1].strip()
                p0_low, p1_low = p0.lower(), p1.lower()
                if any(m in p0_low for m in _POLICY_MARKERS) and any(
                    m in p1_low for m in _GRADE_MARKERS
                ):
                    policy_part, grade_part = p0, p1
                    break
                if any(m in p1_low for m in _POLICY_MARKERS) and any(
                    m in p0_low for m in _GRADE_MARKERS
                ):
                    grade_part, policy_part = p0, p1
                    break

    if grade_part == policy_part:
        policy_pos = min((low.find(m) for m in _POLICY_MARKERS if m in low), default=-1)
        if policy_pos <= 0:
            grade_part = question
            policy_part = (
                "Điểm TOEIC tối thiểu trước đề tài đồ án theo quy định chuẩn ngoại ngữ "
                "Học viện Kỹ thuật Mật mã là bao nhiêu?"
            )
        else:
            grade_part = question[:policy_pos].strip(" .?,")
            policy_part = question[policy_pos:].strip(" .?,")
            if not policy_part.endswith("?"):
                policy_part += "?"

    if not grade_part.endswith("?"):
        grade_part = grade_part.rstrip(".") + "?"
    if not policy_part.endswith("?"):
        policy_part = policy_part.rstrip(".") + "?"

    return [grade_part, policy_part]


def _parse_json(raw: str) -> dict | None:
    m = re.search(r"\{.*\}", raw.strip(), re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def plan_questions(
    question: str,
    *,
    history: list[dict] | None = None,
    session_summary: str = "",
) -> PlanResult:
    question = question.strip()
    if not question:
        return PlanResult(sub_questions=[""], use_decomposition=False)

    presplit = _grade_policy_presplit(question)
    if presplit:
        log.info("[planner] grade+policy presplit → 2 sub-questions")
        return PlanResult(
            sub_questions=presplit,
            use_decomposition=True,
            reason="Tách cố định: tra MSSV/kết quả TA + TOEIC/quy chế.",
        )

    if not _heuristic_complex(question):
        return PlanResult(
            sub_questions=[question],
            use_decomposition=False,
            reason="Câu đơn ý — không tách.",
        )

    try:
        resp = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{
                "role": "user",
                "content": PLANNER_PROMPT.format(
                    session_summary=(session_summary or "").strip() or "(Chưa có.)",
                    history_text=format_history_text(history or [], max_chars=2500),
                    question=question,
                    max_n=PLANNER_MAX_SUB_QUESTIONS,
                ),
            }],
            max_tokens=280,
            temperature=0.0,
        )
        raw  = resp.choices[0].message.content.strip()
        data = _parse_json(raw)
        if not data:
            raise ValueError("invalid planner json")

        subs = [str(s).strip() for s in data.get("sub_questions", []) if str(s).strip()]
        if not subs:
            raise ValueError("empty sub_questions")

        subs = subs[:PLANNER_MAX_SUB_QUESTIONS]
        use = len(subs) > 1
        reason = str(data.get("reason", "")).strip() or "Planner tách câu hỏi."
        log.info(f"[planner] use={use} subs={len(subs)}")
        return PlanResult(sub_questions=subs, use_decomposition=use, reason=reason)

    except Exception as e:
        log.warning(f"[planner] failed: {e}, single question fallback")
        return PlanResult(
            sub_questions=[question],
            use_decomposition=False,
            reason="Planner lỗi — xử lý một câu.",
        )
