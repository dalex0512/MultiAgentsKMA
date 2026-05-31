"""
Tra cứu điểm theo MSSV (+ họ tên tùy chọn) — gom toàn bộ chunk bảng điểm, liệt kê đủ môn trong kỳ.
"""

from __future__ import annotations

import logging
import re
import time

from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    LLM_MODEL,
    GRADE_LOOKUP_MAX_CONTEXT,
    GRADE_LOOKUP_MAX_TOKENS,
)
from pipelines.retrieval import (
    QdrantRetriever,
    extract_mssv,
    extract_student_name,
)
from pipelines.rag_pipeline import _sources_from_docs
from agents.conversation_context import history_for_grade_lookup
from utils.rag.table_context import persona_suffix_for_agent

log = logging.getLogger(__name__)

_NOT_FOUND_RE = re.compile(
    r"kh[oô]ng\s+t[iì]m\s+th[aấ]y",
    re.IGNORECASE,
)

GRADE_LOOKUP_SYSTEM = (
    "Bạn là trợ lý tra cứu bảng điểm KMA (agent diem_thi).\n"
    "Nhiệm vụ: đọc bảng có MSSV và liệt kê ĐỦ từng môn / học phần của sinh viên trong đúng học kỳ.\n"
    "QUY TẮC BẮT BUỘC:\n"
    "- Nếu tài liệu user có chuỗi MSSV được hỏi (vd. CT060310) kèm điểm hoặc Đạt/Không đạt: "
    "PHẢI liệt kê hết các dòng/môn — KHÔNG được trả «Không tìm thấy thông tin trong tài liệu KMA».\n"
    "- Chỉ trả «Không tìm thấy» khi đã đọc hết tài liệu và không có MSSV hoặc tên sinh viên.\n"
    "- Giữ đúng cột/hàng bảng; không bịa điểm."
    + persona_suffix_for_agent("diem_thi")
)


def build_grade_lookup_system(session_summary: str = "") -> str:
    """System prompt riêng — không dùng PERSONA_ACCURACY_SUFFIX (gây trả lời «không tìm thấy» nhầm)."""
    base = GRADE_LOOKUP_SYSTEM
    if session_summary.strip():
        base += f"\n\nTóm tắt phiên chat trước:\n{session_summary.strip()}"
    return base

# «Môn thi: Tên học phần - C6» ngay trước bảng điểm (layout PDF KMA)
_MON_THI_INLINE_RE = re.compile(
    r"M[oô]n\s+thi\s*:\s*(.+?)(?:\s*-\s*[A-Z]?\d+)?\s+(?:STT|\|)",
    re.IGNORECASE | re.DOTALL,
)
_MON_THI_LINE_RE = re.compile(
    r"^M[oô]n\s+thi\s*:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_GRADE_TRIGGERS = (
    "điểm", "diem", "bảng điểm", "bang diem", "kết quả", "ket qua",
    "học kỳ", "hoc ky", "học phần", "hoc phan", "môn", "mon ",
    "đạt", "dat", "không đạt", "khong dat", "xem điểm", "tra cứu", "tra cuu",
    "phân loại", "phan loai", "tiếng anh", "tieng anh", "đầu vào", "dau vao",
    "kiểm tra", "kiem tra", "danh sách", "danh sach",
)

GRADE_LOOKUP_PROMPT = """\
Bạn tra cứu kết quả học tập từ bảng điểm / file điểm KMA (chỉ dùng tài liệu dưới đây).

Sinh viên tra cứu:
- MSSV: {mssv}
{name_line}

Câu hỏi: {question}

YÊU CẦU BẮT BUỘC:
0. Dữ liệu là BẢNG CÓ CẤU TRÚC (hàng/cột): đọc đúng từng hàng, không đảo MSSV/môn/điểm.
1. Liệt kê TẤT CẢ học phần / môn học (và điểm, hoặc Đạt/Không đạt, hoặc điểm chữ) của sinh viên này
   có trong tài liệu — dùng bảng markdown hoặc bullet từng dòng, KHÔNG gộp chung một câu.
   Mỗi nhóm điểm PHẢI ghi **tên môn đầy đủ** lấy từ dòng «Môn thi: …» ngay phía trên bảng
   (vd. «Cơ sở an toàn và bảo mật thông tin»), không chỉ liệt kê TP1/TP2/THI/HP.
2. Chỉ trả lời đúng học kỳ / đợt / năm mà sinh viên hỏi — đọc tên file nguồn
   (vd. hk2_20242025_dot1 = học kỳ 2, năm 2024-2025, đợt 1). Không liệt kê điểm kỳ khác.
3. Nếu trong tài liệu không có đúng kỳ được hỏi, nói rõ; không dùng dữ liệu hk1/hk2 khác thay thế.
4. Không bịa môn hoặc điểm không có trong tài liệu.
5. Nếu hội thoại trước có câu "không tìm thấy" nhưng bảng dưới đây có MSSV — ưu tiên bảng, không lặp lỗi cũ.
6. Dùng hội thoại trước để hiểu MSSV, học kỳ, đợt (memory); dữ liệu điểm chỉ lấy từ bảng tài liệu.
7. Nếu không thấy MSSV hoặc tên trong tài liệu, trả lời: "Không tìm thấy thông tin trong tài liệu KMA."
8. Nếu hỏi kết quả phân loại / kiểm tra tiếng Anh đầu vào: trả lời rõ sinh viên **ĐẠT** hay **KHÔNG ĐẠT**
   (hoặc có/không có trong danh sách), kèm lớp/khóa nếu có trong bảng.

Tài liệu (có thể nhiều trang / nhiều đoạn cùng bảng điểm):
{context}
"""


def wants_grade_lookup(agent_id: str, question: str, retrieval_query: str | None = None) -> bool:
    if agent_id != "diem_thi":
        return False
    blob = f"{question} {retrieval_query or ''}"
    if not extract_mssv(blob):
        return False
    low = blob.lower()
    if any(t in low for t in _GRADE_TRIGGERS):
        return True
    if extract_student_name(blob):
        return True
    return False


def _is_not_found_answer(answer: str) -> bool:
    return bool(_NOT_FOUND_RE.search(answer or ""))


def _mssv_present_in_docs(mssv: str, docs: list[dict]) -> bool:
    if not mssv:
        return False
    u = mssv.upper()
    return any(u in (d.get("text") or "").upper() for d in docs)


def _is_compact_grade_row(line: str, mssv: str) -> bool:
    """Lọc dòng điểm của SV, bỏ đoạn header «Môn thi… STT SBD…» dài."""
    if mssv.upper() not in (line or "").upper():
        return False
    if len(line) > 400 and ("STT" in line or "Mã HVSV" in line or "Ma HVSV" in line):
        return False
    if "|" in line and re.search(rf"\|\s*\d+\s*\|\s*\d+\s*\|\s*{re.escape(mssv)}", line, re.I):
        return True
    return len(line) < 320


def _extract_subject_from_chunk(text: str) -> str | None:
    """Tên môn từ «Môn thi: …» trong chunk bảng điểm."""
    if not text:
        return None
    m = _MON_THI_INLINE_RE.search(text)
    if m:
        name = re.sub(r"\s+", " ", m.group(1)).strip(" -–|")
        return name or None
    for line in text.splitlines():
        lm = _MON_THI_LINE_RE.match(line.strip())
        if lm:
            name = re.sub(r"\s+", " ", lm.group(1)).strip(" -–|")
            if name:
                return name
    return None


def _subjects_by_source_page(docs: list[dict]) -> dict[tuple[str, int], str]:
    """Ánh xạ (file, trang) → tên môn từ chunk có dòng «Môn thi:»."""
    out: dict[tuple[str, int], str] = {}
    for d in docs:
        subj = _extract_subject_from_chunk(d.get("text") or "")
        if subj:
            out[(d.get("source", ""), int(d.get("page") or 0))] = subj
    return out


def _build_subject_grade_index(docs: list[dict], mssv: str) -> str:
    """
    Gom điểm theo tên môn (từ «Môn thi:») — giúp LLM luôn hiển thị tên học phần.
    """
    u = mssv.upper()
    blocks: list[str] = []
    seen: set[tuple[str, str]] = set()
    page_subjects = _subjects_by_source_page(docs)

    for d in docs:
        text = d.get("text") or ""
        if u not in text.upper():
            continue
        src = d.get("source", "")
        page = int(d.get("page") or 0)
        subject = (
            _extract_subject_from_chunk(text)
            or page_subjects.get((src, page))
            or "(Không đọc được tên môn — xem đoạn dưới)"
        )
        row_lines = [
            ln.strip()
            for ln in text.splitlines()
            if u in ln.upper() and ln.strip() and _is_compact_grade_row(ln, mssv)
        ]
        if not row_lines:
            row_lines = [
                ln.strip()[:280]
                for ln in text.splitlines()
                if u in ln.upper() and ln.strip()
            ][:1]
        if not row_lines:
            continue
        key = (subject, row_lines[0][:120])
        if key in seen:
            continue
        seen.add(key)
        rows_txt = "\n".join(f"    · {rl}" for rl in row_lines[:3])
        blocks.append(
            f"• **{subject}** (nguồn: {src} tr.{page})\n{rows_txt}"
        )

    if not blocks:
        return ""
    return (
        "CHỈ MỤC MÔN THI + DÒNG ĐIỂM (trích từ «Môn thi:» và hàng có MSSV):\n"
        + "\n".join(blocks)
    )


def _extract_mssv_row_hints(docs: list[dict], mssv: str, limit: int = 40) -> str:
    """Trích các dòng/markdown row chứa MSSV — kèm tên môn trong cùng chunk."""
    u = mssv.upper()
    lines: list[str] = []
    seen: set[str] = set()
    for d in docs:
        src = d.get("source", "")
        page = d.get("page", 0)
        subject = _extract_subject_from_chunk(d.get("text") or "")
        subj_tag = f"[Môn: {subject}] " if subject else ""
        for line in (d.get("text") or "").splitlines():
            if u not in line.upper():
                continue
            key = line.strip()[:200]
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- ({src} tr.{page}) {subj_tag}{line.strip()}")
            if len(lines) >= limit:
                break
        if len(lines) >= limit:
            break
    if not lines:
        return ""
    return "Các dòng bảng có MSSV (trích từ tài liệu):\n" + "\n".join(lines)


def _build_merged_context(docs: list[dict], max_chars: int) -> str:
    parts: list[str] = []
    used = 0
    for i, d in enumerate(docs, 1):
        src = d.get("source", "")
        page = d.get("page", 0)
        block = f"[{i}] (Nguồn: {src} tr.{page})\n{d.get('text', '')}"
        if used + len(block) > max_chars and parts:
            parts.append(
                f"[...] (còn {len(docs) - i + 1} đoạn tài liệu không hiển thị hết — "
                "ưu tiên các đoạn trên)"
            )
            break
        parts.append(block)
        used += len(block) + 2
    return "\n\n".join(parts)


class GradeLookupPipeline:
    def __init__(self):
        self.openai = OpenAI(api_key=OPENAI_API_KEY)
        self.retriever = QdrantRetriever()

    def _generate_answer(self, messages: list[dict]) -> str:
        resp = self.openai.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            max_tokens=GRADE_LOOKUP_MAX_TOKENS,
            temperature=0.0,
        )
        return resp.choices[0].message.content.strip()

    def _prepare_docs(self, question: str, retrieval_query: str) -> tuple[list[dict], str | None, str, float]:
        rq = (retrieval_query or question).strip()
        mssv = extract_mssv(rq) or extract_mssv(question) or ""
        name = extract_student_name(rq) or extract_student_name(question)

        t0 = time.perf_counter()
        lookup_q = f"{question} {rq}".strip()
        docs = self.retriever.lookup_mssv_grade_docs(
            lookup_q,
            agent_id="diem_thi",
            student_name=name,
        )
        t_ret = round(time.perf_counter() - t0, 3)
        return docs, name, mssv, t_ret

    def run(
        self,
        question: str,
        history: list[dict] | None = None,
        *,
        retrieval_query: str | None = None,
        system_prompt: str | None = None,
    ) -> dict:
        t0 = time.perf_counter()
        docs, name, mssv, t_retrieval = self._prepare_docs(question, retrieval_query or question)

        if not docs:
            return {
                "answer":      "Không tìm thấy thông tin trong tài liệu KMA.",
                "t_total":     round(time.perf_counter() - t0, 3),
                "t_retrieval": t_retrieval,
                "t_llm":       0.0,
                "n_rounds":    1,
                "n_docs":      0,
                "sources":     [],
            }

        context = _build_merged_context(docs, GRADE_LOOKUP_MAX_CONTEXT)
        prefix_parts = [
            _build_subject_grade_index(docs, mssv),
            _extract_mssv_row_hints(docs, mssv),
        ]
        prefix = "\n\n".join(p for p in prefix_parts if p)
        if prefix:
            context = prefix + "\n\n" + context
        name_line = f"- Họ tên (đối chiếu): {name}" if name else "- Họ tên: (không gửi — chỉ lọc theo MSSV)"

        prompt = GRADE_LOOKUP_PROMPT.format(
            mssv=mssv,
            name_line=name_line,
            question=question.strip(),
            context=context,
        )
        sys_msg = system_prompt or build_grade_lookup_system()
        messages: list[dict] = [{"role": "system", "content": sys_msg}]
        messages.extend(history_for_grade_lookup(history))
        messages.append({"role": "user", "content": prompt})

        t_llm = time.perf_counter()
        answer = self._generate_answer(messages)
        if _is_not_found_answer(answer) and _mssv_present_in_docs(mssv, docs):
            log.warning("[grade_lookup] LLM «không tìm thấy» dù có MSSV — retry strict")
            retry_prompt = prompt + (
                f"\n\nLƯU Ý: Tài liệu trên CÓ chứa MSSV {mssv}. "
                "Bạn PHẢI liệt kê từng môn và điểm, không được trả lời không tìm thấy."
            )
            messages[-1] = {"role": "user", "content": retry_prompt}
            answer = self._generate_answer(messages)
        t_llm = round(time.perf_counter() - t_llm, 3)

        for d in docs:
            d["_rank_score"] = d.get("_rank_score", d.get("score", 0))

        return {
            "answer":      answer,
            "t_total":     round(time.perf_counter() - t0, 3),
            "t_retrieval": t_retrieval,
            "t_llm":       t_llm,
            "n_rounds":    1,
            "n_docs":      len(docs),
            "sources":     _sources_from_docs(docs, limit=5),
        }

    def run_stream(
        self,
        question: str,
        history: list[dict] | None = None,
        *,
        retrieval_query: str | None = None,
        system_prompt: str | None = None,
    ):
        t0 = time.perf_counter()
        docs, name, mssv, t_retrieval = self._prepare_docs(question, retrieval_query or question)

        for d in docs:
            d["_rank_score"] = d.get("_rank_score", d.get("score", 0))
        sources = _sources_from_docs(docs, limit=5) if docs else []
        yield {"type": "info", "t_retrieval": t_retrieval, "sources": sources}

        if not docs:
            yield {"type": "delta", "content": "Không tìm thấy thông tin trong tài liệu KMA."}
            yield {
                "type": "done",
                "t_total": round(time.perf_counter() - t0, 3),
                "t_retrieval": t_retrieval,
                "t_llm": 0.0,
                "n_rounds": 1,
            }
            return

        context = _build_merged_context(docs, GRADE_LOOKUP_MAX_CONTEXT)
        prefix_parts = [
            _build_subject_grade_index(docs, mssv),
            _extract_mssv_row_hints(docs, mssv),
        ]
        prefix = "\n\n".join(p for p in prefix_parts if p)
        if prefix:
            context = prefix + "\n\n" + context
        name_line = f"- Họ tên (đối chiếu): {name}" if name else "- Họ tên: (không gửi — chỉ lọc theo MSSV)"
        prompt = GRADE_LOOKUP_PROMPT.format(
            mssv=mssv,
            name_line=name_line,
            question=question.strip(),
            context=context,
        )
        sys_msg = system_prompt or build_grade_lookup_system()
        messages: list[dict] = [{"role": "system", "content": sys_msg}]
        messages.extend(history_for_grade_lookup(history))
        messages.append({"role": "user", "content": prompt})

        t_llm = time.perf_counter()
        stream = self.openai.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            max_tokens=GRADE_LOOKUP_MAX_TOKENS,
            temperature=0.0,
            stream=True,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield {"type": "delta", "content": content}

        yield {
            "type": "done",
            "t_total": round(time.perf_counter() - t0, 3),
            "t_retrieval": t_retrieval,
            "t_llm": round(time.perf_counter() - t_llm, 3),
            "n_rounds": 1,
        }
