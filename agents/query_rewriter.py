"""
Query Rewriter — làm rõ câu hỏi follow-up (đại từ, nối tiếp) trước Supervisor / Retrieve / Qc.
"""

import logging
import re
from dataclasses import dataclass

from openai import OpenAI
from config import LLM_MODEL, OPENAI_API_KEY
from agents.conversation_context import format_history_text, history_for_rewrite

log = logging.getLogger(__name__)

openai_client = OpenAI(api_key=OPENAI_API_KEY)

REWRITE_PROMPT = """\
Bạn hỗ trợ chatbot Học viện KMA. Nhiệm vụ: viết lại câu hỏi MỚI của sinh viên thành câu ĐỦ NGHĨA, đứng một mình.

Ngữ cảnh phiên (tóm tắt trước):
{session_summary}

Hội thoại gần đây:
{history_text}

Câu hỏi mới (có thể dùng "đó", "còn", "nữa", ...):
{question}

Quy tắc:
- Giữ nguyên ý; bổ sung chủ thể/mảng (tuyển sinh, biểu mẫu, quy chế, MSSV, ngành, môn…) nếu thiếu.
- Nếu hội thoại trước có MSSV, ngành, môn, biểu mẫu — PHẢI đưa vào câu rewrite (vd. «CT060310», «CNTT», «Tiếng Anh 2»).
- Không trả lời câu hỏi, chỉ xuất MỘT câu hỏi tiếng Việt (một dòng).
- Nếu câu đã đủ rõ, trả lại gần như nguyên văn."""


@dataclass
class RewriteResult:
    original:          str
    retrieval_query:   str
    was_rewritten:     bool


def _needs_rewrite_score(question: str, history: list[dict]) -> float:
    """Score [0, 1] — chỉ gọi LLM rewriter khi score > 0.65."""
    score = 0.0
    q = question.strip()
    q_lower = q.lower()
    words = len(q.split())

    strong_follow_markers = ("còn", "đó", "cái đó", "nó", "nó là", "thế", "vậy", "sao")
    if any(m in q_lower for m in strong_follow_markers):
        score += 0.55

    if any(m in q_lower for m in ("bạn ấy", "ban ay", "anh ấy", "sinh viên đó")):
        score += 0.3

    if words <= 8:
        score += 0.2

    if q.count("?") >= 2:
        score += 0.15

    # Không phạt khi câu rất ngắn + có strong follow-up marker (gần chắc là follow-up)
    if len(history) == 0 and words > 8:
        score -= 0.2

    context_keywords = (
        "ngành", "khoá", "kma", "mssv", "at", "ct",
        "môn", "tài chính", "phí", "học kỳ",
    )
    if any(kw in q_lower for kw in context_keywords):
        score -= 0.2

    if re.search(r"\b(?:AT|CT)\d{6}\b", q, re.I):
        score -= 0.3

    if words >= 20 and score < 0.1:
        score -= 0.15

    specific_topics = (
        "phục khảo", "phuc khao", "bảo lưu", "bao luu",
        "thực tập", "thuc tap", "tài chính", "tai chinh",
    )
    if any(t in q_lower for t in specific_topics):
        score = 0.0

    return max(0.0, min(1.0, score))


def _needs_rewrite(question: str, history: list[dict], session_summary: str) -> bool:
    """Quick heuristic: có dấu hiệu follow-up cần rewrite không."""
    q = question.strip()
    if not q:
        return False

    strong_markers = ("đó", "còn", "thế", "vậy", "sao", "nó")
    if not any(m in q.lower() for m in strong_markers):
        score = _needs_rewrite_score(q, history)
        if score < 0.65:
            return False

    follow_markers = (
        "đó", "đơn đó", "còn", "nữa", "tiếp", "vậy", "như vậy", "ở trên",
        "vừa nói", "phần đó", "mục đó", "chi tiết hơn", "giải thích thêm",
        "thế còn", "cái đó", "mẫu đó", "ngành đó",
        "bạn ấy", "ban ay", "anh ấy", "sinh viên đó", "sinh vien do",
        "thì sao", "thi sao", "thì bao nhiêu", "như trên", "y như",
    )
    if any(m in q.lower() for m in follow_markers):
        return True

    has_ctx = bool(history) or bool(session_summary.strip())
    return has_ctx and len(q.split()) <= 8


def rewrite(
    question: str,
    history: list[dict] | None = None,
    session_summary: str = "",
) -> RewriteResult:
    question = question.strip()
    history  = history_for_rewrite(history or [])
    summary  = (session_summary or "").strip()

    if not _needs_rewrite(question, history, summary):
        log.debug("[rewriter] skip (quick check): %s", question[:50])
        return RewriteResult(
            original=question,
            retrieval_query=question,
            was_rewritten=False,
        )

    score = _needs_rewrite_score(question, history)
    if score < 0.65:
        log.info("[rewriter] skip (low score=%.2f): %s", score, question[:50])
        return RewriteResult(
            original=question,
            retrieval_query=question,
            was_rewritten=False,
        )

    log.info("[rewriter] LLM rewrite (score=%.2f): %s", score, question[:50])

    try:
        resp = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{
                "role": "user",
                "content": REWRITE_PROMPT.format(
                    session_summary=summary or "(Chưa có.)",
                    history_text=format_history_text(history),
                    question=question,
                ),
            }],
            max_tokens=120,
            temperature=0.0,
        )
        rewritten = resp.choices[0].message.content.strip().split("\n")[0].strip()
        if not rewritten:
            raise ValueError("empty rewrite")

        log.info("[rewrite] was=True q=%r -> %r", question[:50], rewritten[:50])
        return RewriteResult(
            original=question,
            retrieval_query=rewritten,
            was_rewritten=True,
        )
    except Exception as e:
        log.warning("[rewrite] failed: %s, using original", e)
        return RewriteResult(
            original=question,
            retrieval_query=question,
            was_rewritten=False,
        )
