"""
Tiện ích chuẩn hóa history hội thoại cho toàn hệ thống.
"""

from config import (
    HISTORY_MAX_MESSAGES,
    HISTORY_FOR_REWRITE,
    HISTORY_FOR_SUPERVISOR,
    HISTORY_FOR_GENERATE,
)


def trim_history(history: list[dict] | None, max_messages: int = HISTORY_MAX_MESSAGES) -> list[dict]:
    if not history:
        return []
    out = []
    for m in history[-max_messages:]:
        role = m.get("role", "")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            out.append({"role": role, "content": content})
    return out


def slice_history(history: list[dict] | None, n: int) -> list[dict]:
    if not history or n <= 0:
        return []
    return history[-n:]


def history_for_rewrite(history: list[dict]) -> list[dict]:
    return slice_history(history, HISTORY_FOR_REWRITE)


def history_for_supervisor(history: list[dict]) -> list[dict]:
    return slice_history(history, HISTORY_FOR_SUPERVISOR)


def history_for_generate(history: list[dict]) -> list[dict]:
    return slice_history(history, HISTORY_FOR_GENERATE)


_NOT_FOUND_STUB_MARKERS = (
    "không tìm thấy thông tin trong tài liệu kma",
    "khong tim thay thong tin trong tai lieu kma",
)


def _is_failed_lookup_stub(content: str) -> bool:
    """Câu trợ lý lỗi retrieve cũ — bỏ khi đã có bảng điểm để không bias LLM."""
    c = (content or "").strip().lower()
    if not c:
        return True
    if any(m in c for m in _NOT_FOUND_STUB_MARKERS) and len(c) < 200:
        return True
    return False


def history_for_grade_lookup(history: list[dict]) -> list[dict]:
    """
    Cùng memory với generate (HISTORY_FOR_GENERATE).
    Chỉ bỏ các lượt assistant thuần 'không tìm thấy' — giữ user + câu trả lời có nội dung.
    """
    base = history_for_generate(history)
    out: list[dict] = []
    for m in base:
        if m["role"] == "assistant" and _is_failed_lookup_stub(m.get("content", "")):
            continue
        out.append(m)
    return out


def format_history_text(history: list[dict], max_chars: int = 4000) -> str:
    if not history:
        return "(Không có lượt trước.)"
    lines = []
    total = 0
    for m in history:
        role = "Sinh viên" if m["role"] == "user" else "Trợ lý"
        line = f"{role}: {m['content']}"
        if total + len(line) > max_chars:
            lines.append("...")
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)
