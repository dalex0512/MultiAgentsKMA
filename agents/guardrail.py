"""
Scope Guardrail — phát hiện câu hỏi ngoài phạm vi tài liệu KMA, trả lời chung hợp lý.
Chạy TRƯỚC Supervisor/RAG để tránh retrieve bừa và hallucination.
"""

import json
import logging
import re
from dataclasses import dataclass

from openai import OpenAI
from config import LLM_MODEL, OPENAI_API_KEY, AGENTS
from agents.conversation_context import format_history_text
from agents.session_memory import session_store

log = logging.getLogger(__name__)

openai_client = OpenAI(api_key=OPENAI_API_KEY)

_MSSV_RE = re.compile(r"\b(?:AT|CT)\d{6}\b", re.IGNORECASE)

_CAPABILITY_TEXT = "\n".join(
    f"• **{cfg['name']}**: {cfg['description']}"
    for cfg in AGENTS.values()
)

OFF_TOPIC_REPLY = f"""\
Em là trợ lý ảo **Học viện Kỹ thuật Mật mã (KMA)**. Câu hỏi của bạn **nằm ngoài phạm vi** tài liệu và chức năng em hỗ trợ, nên em không tra cứu hay suy đoán thêm.

Em có thể giúp các mảng sau (dựa trên tài liệu KMA):

{_CAPABILITY_TEXT}

Bạn hãy đặt câu hỏi liên quan một trong các mảng trên (ví dụ: chuẩn đầu ra ngoại ngữ, đơn xin nghỉ học, ma trận đề thi, tuyển sinh 2025).\
"""

CHITCHAT_REPLY = """\
Xin chào! Em là trợ lý ảo **đa tác tử** của Học viện Kỹ thuật Mật mã (KMA).

Em hỗ trợ tra cứu **tài liệu chính thức** về: tuyển sinh & CTĐT, khảo thí & quy chế, ma trận đề thi, kết quả thi công bố, biểu mẫu & thủ tục.

Bạn muốn hỏi về mảng nào?\
"""

SCOPE_PROMPT = """\
Bạn là bộ lọc phạm vi cho chatbot KMA (Học viện Kỹ thuật Mật mã).

Phạm vi IN-SCOPE: tuyển sinh, CTĐT, quy chế, khảo thí, chuẩn đầu ra, thi/tốt nghiệp, ma trận đề thi, điểm/kết quả công bố, biểu mẫu/đơn từ KMA.

OUT-OF-SCOPE: trường khác, kiến thức phổ thông không liên quan KMA, lập trình bài tập, thời tiết, giải trí, tin tức, y tế, chính trị, v.v.

CHITCHAT: chào hỏi, cảm ơn, tạm biệt (không hỏi nội dung KMA).

Tóm tắt phiên: {session_summary}
Hội thoại gần đây:
{history_text}

Câu hỏi: {question}

Trả JSON (không markdown):
{{"category": "kma"|"off_topic"|"chitchat", "confidence": 0.0-1.0}}"""


@dataclass
class ScopeResult:
    in_scope:   bool
    category:   str          # kma | off_topic | chitchat
    answer:     str | None   # có sẵn nếu không cần RAG
    confidence: float = 1.0


_KMA_EXPLICIT = (
    "kma", "học viện kỹ thuật", "hoc vien ky thuat", "mật mã", "mat ma",
    "kỹ thuật mật mã", "ky thuat mat ma",
)

_KMA_MARKERS = _KMA_EXPLICIT + (
    "tuyển sinh", "tuyen sinh", "quy chế", "quy che", "chuẩn đầu ra", "ma trận", "ma tran",
    "biểu mẫu", "bieu mau", "đơn ", "don ", "nhập học", "nhap hoc",
    "ctđt", "ctdt", "thạc sĩ", "thac si", "phúc khảo", "phuc khao",
    "bảng điểm", "bang diem", "điểm thi", "diem thi", "điểm học kỳ", "diem hoc ky",
    "điểm chuẩn", "diem chuan", "trúng tuyển", "trung tuyen", "toeic", "vstep",
    "mã sinh viên", "ma sinh vien", "mssv", "phân loại tiếng anh", "phan loai tieng anh",
    "lịch thi", "lich thi", "kthp", "khóa đào tạo", "khoa dao tao", "khoá đào tạo",
    "môn thi", "mon thi", "đợt 2", "dot 2", "học kỳ", "hoc ky",
    "danh sách thi", "danh sach thi", "số báo danh", "so bao danh", "sbd",
    "ca thi", "phòng thi", "phong thi",
)

_CHITCHAT_MARKERS = (
    "xin chào", "chào bạn", "hello", "hi ", "cảm ơn", "cam on",
    "thank", "tạm biệt", "bye", "bạn là ai",
)

_CAPABILITY_MARKERS = (
    "giúp gì", "giup gi", "làm được gì", "lam duoc gi", "hỗ trợ gì", "ho tro gi",
    "chức năng", "chuc nang", "khả năng", "kha nang", "làm gì được", "lam gi duoc",
)

_FORM_FILL_MARKERS = (
    "điền", "dien", "mục", "muc", "ghi nhận", "ghi nhan", "/12", "/10",
    "xác nhận", "xac nhan", "biểu mẫu", "bieu mau", "đơn ", "don ",
)

_OFF_TOPIC_STRONG = (
    "thời tiết", "bóng đá", "bitcoin", "nấu ăn", "python là gì",
    "đại học bách khoa", "đhqg", "harvard", "gpt là gì",
    "bầu cử", "covid", "giá vàng",
)


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    t = text.lower()
    return any(m in t for m in markers)


def _parse_scope_json(raw: str) -> dict | None:
    m = re.search(r"\{.*\}", raw.strip(), re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def _active_form_fill(session_id: str | None) -> bool:
    if not session_id:
        return False
    st = session_store.get(session_id)
    if not st or not getattr(st, "form_fill", None):
        return False
    status = getattr(st.form_fill, "status", "")
    return status in ("collecting", "confirm_profile")


def check_scope(
    question: str,
    *,
    history: list[dict] | None = None,
    session_summary: str = "",
    session_id: str | None = None,
) -> ScopeResult:
    q = question.strip()

    if _active_form_fill(session_id):
        return ScopeResult(in_scope=True, category="kma", answer=None)

    if not q:
        return ScopeResult(
            in_scope=False,
            category="chitchat",
            answer="Bạn vui lòng nhập câu hỏi về thông tin KMA.",
        )

    if _MSSV_RE.search(q):
        return ScopeResult(in_scope=True, category="kma", answer=None)

    if _has_any(q, _OFF_TOPIC_STRONG) and not _has_any(q, _KMA_EXPLICIT):
        return ScopeResult(in_scope=False, category="off_topic", answer=OFF_TOPIC_REPLY)

    if _has_any(q, _CAPABILITY_MARKERS) and _has_any(q, _KMA_EXPLICIT + ("sinh viên", "sinh vien")):
        return ScopeResult(in_scope=False, category="chitchat", answer=CHITCHAT_REPLY)

    if _has_any(q, _CHITCHAT_MARKERS) and len(q.split()) <= 12:
        if not _has_any(q, _KMA_MARKERS):
            return ScopeResult(in_scope=False, category="chitchat", answer=CHITCHAT_REPLY)

    if _has_any(q, _KMA_MARKERS):
        return ScopeResult(in_scope=True, category="kma", answer=None)

    # Câu ngắn trong phiên đang điền đơn / bàn KMA → vẫn cho qua
    if history and len(q.split()) <= 20:
        hist_text = " ".join(m["content"].lower() for m in history[-8:])
        if _has_any(hist_text, _KMA_MARKERS + _FORM_FILL_MARKERS):
            return ScopeResult(in_scope=True, category="kma", answer=None)
        if re.search(r"\*\*\d+/\d+\.\*\*", hist_text) or re.search(r"\d+/\d+\.", hist_text):
            return ScopeResult(in_scope=True, category="kma", answer=None)

    try:
        resp = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{
                "role": "user",
                "content": SCOPE_PROMPT.format(
                    session_summary=(session_summary or "").strip() or "(Chưa có.)",
                    history_text=format_history_text(history or [], max_chars=2000),
                    question=q,
                ),
            }],
            max_tokens=60,
            temperature=0.0,
        )
        raw  = resp.choices[0].message.content.strip()
        data = _parse_scope_json(raw)
        if not data:
            raise ValueError("bad json")

        cat  = str(data.get("category", "kma")).lower()
        conf = float(data.get("confidence", 0.8))

        if cat == "chitchat":
            return ScopeResult(
                in_scope=False, category="chitchat",
                answer=CHITCHAT_REPLY, confidence=conf,
            )
        if cat == "off_topic" and conf >= 0.55:
            return ScopeResult(
                in_scope=False, category="off_topic",
                answer=OFF_TOPIC_REPLY, confidence=conf,
            )
        return ScopeResult(in_scope=True, category="kma", answer=None, confidence=conf)

    except Exception as e:
        log.warning(f"[guardrail] LLM failed: {e}, default in_scope")
        return ScopeResult(in_scope=True, category="kma", answer=None)
