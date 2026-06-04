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
    extract_all_mssv,
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
    "Nhiệm vụ: đọc bảng có MSSV và trả lời đúng phạm vi câu hỏi (môn cụ thể hoặc toàn bộ học kỳ).\n"
    "QUY TẮC BẮT BUỘC:\n"
    "- Nếu tài liệu có chuỗi MSSV được hỏi kèm điểm hoặc Đạt/Không đạt: "
    "PHẢI trả lời — KHÔNG được trả «Không tìm thấy thông tin trong tài liệu KMA».\n"
    "- Nếu câu hỏi hỏi MÔN CỤ THỂ: chỉ trả lời đúng môn đó, không liệt kê môn khác.\n"
    "- Nếu câu hỏi hỏi CHUNG: liệt kê đủ các môn trong đúng học kỳ/đợt.\n"
    "- Nếu câu hỏi không rõ học kỳ và tài liệu có nhiều kỳ: hỏi lại học kỳ/đợt cụ thể.\n"
    "- Không tính hoặc bịa GPA/xếp loại khi không đủ dữ liệu tín chỉ.\n"
    "- Chỉ trả «Không tìm thấy» khi đã đọc hết tài liệu và không có MSSV.\n"
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
    r"M[oô]n\s+thi\s*:\s*(.+?)(?:\s*-\s*(?:[A-Z]?\d+|[ACD]\d+[ACD]\d+[ACD]\d+))?\s+(?:STT|\|)",
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
    # Tốt nghiệp CT4, chứng chỉ, Anh văn
    "tốt nghiệp", "tot nghiep", "ct4", "chứng chỉ", "chung chi",
    "anh văn", "anh van", "nhận chứng", "nhan chung",
    "hoàn thành", "hoan thanh", "ra trường", "ra truong",
)

GRADE_LOOKUP_PROMPT = """\
Bạn tra cứu kết quả học tập từ bảng điểm / file điểm KMA (chỉ dùng tài liệu dưới đây).

Sinh viên tra cứu:
- MSSV: {mssv}
{name_line}

Câu hỏi: {question}

YÊU CẦU BẮT BUỘC:
0. Dữ liệu là BẢNG CÓ CẤU TRÚC (hàng/cột): đọc đúng từng hàng, không đảo MSSV/môn/điểm.
1. Xác định phạm vi câu hỏi:
   a) Nếu câu hỏi nêu TÊN MÔN CỤ THỂ (vd. "môn Thực tập cơ sở", "môn Toán cao cấp") →
      CHỈ trả lời điểm của đúng môn đó, không liệt kê các môn khác.
   b) Nếu câu hỏi hỏi chung (vd. "điểm học kỳ X", "kết quả các môn", "có môn nào khác không") →
      Liệt kê TẤT CẢ học phần có trong tài liệu thuộc đúng học kỳ/đợt — dùng bảng markdown hoặc bullet.
   Mỗi môn PHẢI ghi **tên môn đầy đủ** lấy từ dòng «Môn thi: …» ngay phía trên bảng.
2. Xác định học kỳ/đợt từ câu hỏi và tên file nguồn (vd. hk2_20242025_dot1 = HK2 2024-2025 đợt 1):
   a) Nếu câu hỏi nêu rõ 1 học kỳ/đợt cụ thể → chỉ lấy dữ liệu từ file khớp, bỏ qua file kỳ khác.
   b) Nếu câu hỏi hỏi NHIỀU kỳ cùng lúc (vd. "HK1 và HK2", "tất cả các kỳ", "toàn bộ") →
      liệt kê theo từng kỳ riêng biệt, ghi rõ tên kỳ cho mỗi nhóm.
   c) Nếu câu hỏi KHÔNG nêu học kỳ/đợt nhưng tài liệu có nhiều kỳ → hỏi lại:
      "Bạn muốn xem điểm học kỳ nào? (vd. HK1 2024-2025 đợt 1, HK2 2024-2025 đợt 1…)"
   d) Nếu câu hỏi KHÔNG nêu học kỳ/đợt nhưng tài liệu chỉ có 1 kỳ → hiển thị kỳ đó, ghi rõ tên kỳ.
3. Nếu trong tài liệu không có đúng kỳ được hỏi, nói rõ; không dùng dữ liệu hk1/hk2 khác thay thế.
4. Không bịa môn hoặc điểm không có trong tài liệu.
5. Nếu hội thoại trước có câu "không tìm thấy" nhưng bảng dưới đây có MSSV — ưu tiên bảng, không lặp lỗi cũ.
6. Dùng hội thoại trước để hiểu MSSV, học kỳ, đợt (memory); dữ liệu điểm chỉ lấy từ bảng tài liệu.
7. Nếu không thấy MSSV hoặc tên trong tài liệu, trả lời: "Không tìm thấy thông tin trong tài liệu KMA."
8. Nếu hỏi kết quả phân loại / kiểm tra tiếng Anh đầu vào: trả lời rõ sinh viên **ĐẠT** hay **KHÔNG ĐẠT**
   (hoặc có/không có trong danh sách), kèm lớp/khóa nếu có trong bảng.
   Khi hỏi phân loại tiếng Anh đầu vào: CHỈ dùng file/bảng «KẾT QUẢ KIỂM TRA PHÂN LOẠI TIẾNG ANH»
   hoặc nguồn `08_ket_qua_thi_anh_van`; BỎ QUA bảng «Môn thi: … - A20C8D7» từ file hk1/hk2 (đó là điểm học phần, không phải phân loại TA).
9. Nếu câu hỏi nêu NHIỀU MSSV: trả lời riêng từng MSSV, không gộp hoặc hoán đổi kết quả.
10. Nếu hỏi "có môn nào khác không", "còn môn nào không" → đối chiếu với môn đã nhắc trong hội thoại,
   chỉ liệt kê các môn còn lại trong cùng học kỳ/đợt; nếu không còn môn nào → trả lời rõ "không có môn nào khác".
11. Nếu hỏi GPA / điểm tổng kết / xếp loại tốt nghiệp: tính GPA từ cột HP và số tín chỉ nếu có đủ dữ liệu;
    nếu không đủ dữ liệu → nói rõ "Không đủ dữ liệu để tính GPA/xếp loại từ tài liệu hiện có."
    Không bịa ra GPA hoặc xếp loại.
12. Ngưỡng điểm KMA (dùng khi hỏi "trượt", "không đạt", "đạt", "cải thiện"):
    - HP >= 5.0 → ĐẠT (tích lũy được tín chỉ)
    - HP < 5.0 → KHÔNG ĐẠT (phải thi lại hoặc học lại)
    - HP < 4.0 → KHÔNG TÍCH LŨY tín chỉ (trượt hoàn toàn)
    Áp dụng ngưỡng này để xác định môn nào đạt/trượt khi người dùng hỏi.

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


def _mssv_list_for_query(question: str, retrieval_query: str, primary: str) -> list[str]:
    blob = f"{question} {retrieval_query}".strip()
    found = extract_all_mssv(blob)
    if found:
        return found
    return [primary] if primary else []


def _build_grade_context_prefix(docs: list[dict], mssv_list: list[str]) -> str:
    parts: list[str] = []
    for m in mssv_list:
        idx = _build_subject_grade_index(docs, m)
        hints = _extract_mssv_row_hints(docs, m)
        if idx:
            parts.append(idx)
        if hints:
            parts.append(hints)
    return "\n\n".join(parts)


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
        mssv_list = _mssv_list_for_query(question, retrieval_query or question, mssv)
        mssv_display = ", ".join(mssv_list) if mssv_list else mssv
        prefix = _build_grade_context_prefix(docs, mssv_list)
        if prefix:
            context = prefix + "\n\n" + context
        name_line = f"- Họ tên (đối chiếu): {name}" if name else "- Họ tên: (không gửi — chỉ lọc theo MSSV)"

        prompt = GRADE_LOOKUP_PROMPT.format(
            mssv=mssv_display,
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
        if _is_not_found_answer(answer) and any(_mssv_present_in_docs(m, docs) for m in mssv_list):
            log.warning("[grade_lookup] LLM «không tìm thấy» dù có MSSV — retry strict")
            retry_prompt = prompt + (
                f"\n\nLƯU Ý: Tài liệu trên CÓ chứa MSSV {mssv_display}. "
                "Bạn PHẢI trả lời đúng từng MSSV được hỏi, không được trả lời không tìm thấy."
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
        mssv_list = _mssv_list_for_query(question, retrieval_query or question, mssv)
        mssv_display = ", ".join(mssv_list) if mssv_list else mssv
        prefix = _build_grade_context_prefix(docs, mssv_list)
        if prefix:
            context = prefix + "\n\n" + context
        name_line = f"- Họ tên (đối chiếu): {name}" if name else "- Họ tên: (không gửi — chỉ lọc theo MSSV)"
        prompt = GRADE_LOOKUP_PROMPT.format(
            mssv=mssv_display,
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
