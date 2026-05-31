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
- Không trả lời nội dung, chỉ JSON.

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
    words = len(q.split())
    if words >= PLANNER_MIN_WORDS:
        return True
    if q.count("?") >= 2:
        return True
    if assess_complexity(q).qc >= 0.62:
        return True
    low = q.lower()
    return any(m in low for m in _COMPLEX_MARKERS)


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
