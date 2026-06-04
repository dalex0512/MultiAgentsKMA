"""
Response Aggregator — gộp câu trả lời từ nhiều specialist agents.
"""

import logging
import time
from openai import OpenAI
from config import LLM_MODEL, OPENAI_API_KEY, AGG_MAX_TOKENS, AGENTS, ACCURACY_MODE

log = logging.getLogger(__name__)

openai_client = OpenAI(api_key=OPENAI_API_KEY)

AGGREGATE_PROMPT = """\
Bạn là Aggregator của hệ thống trợ lý đa tác tử KMA.
Nhiệm vụ: gộp các câu trả lời từ nhiều chuyên gia thành MỘT câu trả lời mạch lạc cho sinh viên.

Tóm tắt phiên (nếu có):
{session_summary}

Câu hỏi gốc: {question}

Các chuyên gia đã trả lời:
{blocks}

Yêu cầu:
- Giữ đủ thông tin quan trọng từ mỗi chuyên gia, tránh trùng lặp.
- Nêu rõ từng phần nếu câu hỏi đa lĩnh vực (đánh số 1), 2)… — vd. kết quả phân loại TA riêng, chuẩn TOEIC/quy chế riêng).
- Không làm mất số liệu cụ thể (450, ĐẠT/KHÔNG ĐẠT, tên MSSV).
- Không bịa thêm ngoài nội dung các chuyên gia đã cung cấp.
- Tiếng Việt, lịch sự, dễ đọc."""

_AGG_PROMPT_EXTRA = (
    "\n- Ưu tiên độ chính xác: không gộp làm mất số liệu; nếu hai chuyên gia mâu thuẫn, nêu rõ theo từng nguồn."
    if ACCURACY_MODE
    else ""
)

_AGG_ACCURACY = (
    "\n- Ưu tiên độ chính xác câu trả lời: giữ nguyên số liệu, tên môn, điều kiện, ngày; "
    "không tóm tắt làm mất chi tiết; nếu hai chuyên gia mâu thuẫn, nêu rõ theo từng phần."
    if ACCURACY_MODE
    else ""
)

AGGREGATE_STREAM_SYSTEM = (
    "Bạn là Aggregator KMA — gộp câu trả lời đa chuyên gia thành một bản duy nhất, "
    "không thêm thông tin ngoài các nguồn đã cho."
    + _AGG_ACCURACY
)


def _format_blocks(agent_results: list[dict]) -> str:
    parts = []
    for r in agent_results:
        aid = r.get("agent_id", "")
        name = AGENTS.get(aid, {}).get("name", aid)
        parts.append(
            f"### {name} (pipeline: {r.get('pipeline', '')}, Qc={r.get('qc', '')})\n"
            f"{r.get('answer', '')}"
        )
    return "\n\n".join(parts)


class ResponseAggregator:
    def aggregate(
        self,
        question: str,
        agent_results: list[dict],
        session_summary: str = "",
    ) -> tuple[str, float]:
        blocks = _format_blocks(agent_results)
        t0 = time.perf_counter()
        resp = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{
                "role": "user",
                "content": (AGGREGATE_PROMPT + _AGG_PROMPT_EXTRA).format(
                    session_summary=session_summary or "(Không có.)",
                    question=question,
                    blocks=blocks,
                ),
            }],
            max_tokens=AGG_MAX_TOKENS,
            temperature=0.0,
        )
        answer = resp.choices[0].message.content.strip()
        return answer, round(time.perf_counter() - t0, 3)

    def aggregate_stream(
        self,
        question: str,
        agent_results: list[dict],
        session_summary: str = "",
    ):
        blocks = _format_blocks(agent_results)
        prompt = (AGGREGATE_PROMPT + _AGG_PROMPT_EXTRA).format(
            session_summary=session_summary or "(Không có.)",
            question=question,
            blocks=blocks,
        )
        stream = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": AGGREGATE_STREAM_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=AGG_MAX_TOKENS,
            temperature=0.0,
            stream=True,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content
