"""
Trích xuất lịch thi KTHP từ chunk bảng Qdrant — không LLM (nhanh, đủ cột).
"""

from __future__ import annotations

import re
import logging
import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from utils.ingest.metadata_schema import parse_table_headers
from utils.rag.kma_cohort_codes import cohort_matches_filter, expand_khoa_cell

if TYPE_CHECKING:
    from pipelines.retrieval import QdrantRetriever

log = logging.getLogger(__name__)

_MD_ROW_RE = re.compile(r"^\|\s*[-:]+")
_TT_RE = re.compile(r"^\d{1,3}$")
_SUBJECT_SKIP_RE = re.compile(
    r"^(tt|stt|môn thi|mon thi|hình thức|hinh thuc|khóa|khoa|địa điểm|"
    r"iii\.|phần\s|mục\s|hạn nộp|tổ chức|sinh viên|phòng kh)",
    re.IGNORECASE,
)
_COHORT_LABEL_RE = re.compile(
    r"(?:khóa|khoa|khoá|lớp|lop)\s+([A-Za-z]{1,3}\d{1,2}[A-Za-z0-9]*)",
    re.IGNORECASE,
)
_COHORT_DAO_TAO_RE = re.compile(
    r"(?:đào\s+tạo|dao\s+tao)\s+([A-Za-z]{1,3}\d{1,2}[A-Za-z0-9]*)",
    re.IGNORECASE,
)
_COHORT_CODE_RE = re.compile(r"\b(AT|CT|DT)\d{1,2}[A-Za-z0-9]*\b", re.IGNORECASE)
_SUBJECT_QUERY_RE = re.compile(
    r"(?:môn|mon)\s+([^,;:.!?]+?)(?=\s+(?:thi|học kỳ|hoc ky|kì|ki|đợt|dot|năm|nam|ở đâu|o dau|$))",
    re.IGNORECASE,
)
_STOP_WORDS = {
    "thi", "hoc", "học", "ky", "kỳ", "ki", "kì", "dot", "đợt", "nam", "năm",
    "ket", "kết", "thuc", "thúc", "phan", "phần", "dia", "địa", "diem", "điểm",
    "phong", "phòng", "gio", "giờ", "o", "ở", "dau", "đâu", "la", "là",
}


@dataclass
class ScheduleRow:
    tt: int
    mon_thi: str
    hinh_thuc: str = ""
    khoa_raw: str = ""
    khoa_expanded: list[str] = field(default_factory=list)
    thoi_gian: str = ""
    dia_diem: str = ""
    han_nop_de: str = ""
    han_lam_phach: str = ""
    han_cham: str = ""


def wants_full_subject_list(question: str) -> bool:
    blob = (question or "").lower()
    if any(
        m in blob
        for m in (
            "những môn", "cac mon", "các môn", "danh sách môn", "danh sach mon",
            "liệt kê môn", "liet ke mon", "co nhung mon", "có những môn",
            "môn nào", "mon nao", "thi những môn", "thi nhung mon",
        )
    ):
        return True
    if "môn thi" in blob or "mon thi" in blob:
        if any(m in blob for m in ("là gì", "la gi", "nào", "nao", "gồm", "gom", "những", "cac", "các")):
            return True
    if "kthp" in blob and any(m in blob for m in ("môn", "mon", "lịch", "lich")):
        return True
    return False


def wants_schedule_table_query(question: str) -> bool:
    """Câu hỏi tra cứu bảng lịch KTHP (môn, giờ, phòng, hình thức, khóa…)."""
    if wants_full_subject_list(question):
        return True
    blob = (question or "").lower()
    if not any(
        m in blob
        for m in (
            "lịch thi", "lich thi", "kthp", "hình thức", "hinh thuc",
            "phòng thi", "phong thi", "giờ thi", "gio thi", "ngày thi",
            "thời gian thi", "thoi gian thi", "bắt đầu thi", "bat dau thi",
            "thời gian bắt đầu", "thoi gian bat dau", "khi nào thi", "khi nao thi",
            "địa điểm", "dia diem", "khóa đào tạo", "khoa dao tao", "khoá đào tạo",
            "thi kết thúc học phần", "thi ket thuc hoc phan", "ở đâu", "o dau",
            "hạn nộp", "han nop", "hạn chấm", "han cham",
        )
    ):
        return False
    return any(
        m in blob
        for m in ("thi", "môn", "mon", "đợt", "dot", "học kỳ", "hoc ky", "kì", "ki ")
    )


def parse_schedule_file_hints(query: str) -> dict[str, str | bool | None]:
    q = (query or "").lower()
    hints: dict[str, str | bool | None] = {
        "ki": None, "dot": None, "year_key": None, "lan2": False,
    }
    if any(p in q for p in ("học kỳ 2", "hoc ky 2", "hk2", "học kỳ ii", "ki2", "ki 2", "ky 2", "kì 2", "hoc ki 2")):
        hints["ki"] = "ki2"
    elif any(
        p in q
        for p in (
            "học kỳ 1", "hoc ky 1", "hk1", "học kỳ i", "ki1", "ky 1",
            "kì 1", "ki 1", "học kì 1", "hoc ki 1",
        )
    ):
        hints["ki"] = "ki1"
    if any(p in q for p in ("đợt 1", "dot 1", "đợt một", "dot1", "đợt1")):
        hints["dot"] = "dot1"
    elif any(p in q for p in ("đợt 2", "dot 2", "đợt hai", "dot2", "đợt2")):
        hints["dot"] = "dot2"
    if any(p in q for p in ("thi lại", "thi lai", "lần 2", "lan 2", "lan2", "học lại", "hoc lai")):
        hints["lan2"] = True
    ym = re.search(r"20(\d{2})\s*[-–/]?\s*20(\d{2})", q)
    if ym:
        hints["year_key"] = f"20{ym.group(1)}20{ym.group(2)}"
    else:
        years = re.findall(r"\b(20\d{2})\b", q)
        if len(years) >= 2:
            hints["year_key"] = f"{years[0]}{years[1]}"
        elif len(years) == 1:
            y = years[0]
            hints["year_key"] = f"{y}{int(y) + 1}"
    return hints


def score_schedule_source(source: str, hints: dict) -> float:
    src = (source or "").lower().replace(".pdf", "").replace("-", "_")
    score = 0.0
    if "kthp" in src or "danh" in src:
        score += 0.3
    ki = hints.get("ki")
    if ki:
        score += 3.0 if ki in src else -4.0
    dot = hints.get("dot")
    if dot:
        if dot in src:
            score += 3.0
        elif dot == "dot2" and "dot1" in src:
            score -= 3.0
        elif dot == "dot1" and "dot2" in src:
            score -= 3.0
    yk = hints.get("year_key")
    if yk and yk in src.replace("_", ""):
        score += 4.0
    if hints.get("lan2"):
        score += 4.0 if "lan2" in src else -2.0
    elif "lan2" in src:
        score -= 1.5
    return score


def _parse_md_cells(line: str) -> list[str]:
    line = line.strip()
    if not line.startswith("|"):
        return []
    parts = [c.strip() for c in line.split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def _col_index(headers: list[str], *needles: str) -> int | None:
    for i, h in enumerate(headers):
        hlow = h.lower().strip()
        for n in needles:
            if n in hlow:
                return i
    return None


def _header_map(headers: list[str]) -> dict[str, int | None]:
    return {
        "tt": _col_index(headers, "tt", "stt") or 0,
        "mon": _col_index(headers, "môn thi", "mon thi"),
        "hinh_thuc": _col_index(headers, "hình thức", "hinh thuc"),
        "khoa": _col_index(headers, "khóa đào tạo", "khoa dao tao", "khóa", "khoa"),
        "thoi_gian": _col_index(headers, "thời gian", "thoi gian"),
        "dia_diem": _col_index(headers, "địa điểm", "dia diem"),
        "han_nop": _col_index(headers, "hạn nộp", "han nop"),
        "han_phach": _col_index(headers, "làm phách", "lam phach", "phách"),
        "han_cham": _col_index(headers, "hạn chấm", "han cham"),
    }


def _cell(cells: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(cells):
        return ""
    return cells[idx].strip()


def parse_cohort_from_query(query: str) -> str | None:
    q = query or ""
    m = _COHORT_DAO_TAO_RE.search(q)
    if m:
        return m.group(1).upper()
    m = _COHORT_LABEL_RE.search(q)
    if m:
        return m.group(1).upper()
    low = q.lower()
    if any(k in low for k in ("khóa", "khoa", "khoá", "lớp", "lop", "đào tạo", "dao tao")):
        codes = _COHORT_CODE_RE.findall(q)
        if codes:
            return codes[-1].upper()
        m2 = re.search(r"\b([ACD]\d{1,2})\b", q, re.I)
        if m2:
            expanded = expand_khoa_cell(m2.group(1))
            if expanded:
                return expanded[0]
    return None


def extract_schedule_rows_from_docs(
    docs: list[dict],
    *,
    cohort_filter: str | None = None,
) -> list[ScheduleRow]:
    ordered = sorted(
        docs,
        key=lambda d: (d.get("page", 0), d.get("table_index", 0), d.get("child_index", 0)),
    )
    seen: set[str] = set()
    out: list[ScheduleRow] = []
    last_khoa = ""
    last_hinh_thuc = ""
    last_thoi_gian = ""
    last_dia_diem = ""

    for doc in ordered:
        headers = parse_table_headers(doc.get("table_headers"))
        if not headers:
            continue
        cols = _header_map(headers)

        for line in (doc.get("text") or "").splitlines():
            if not line.strip().startswith("|") or _MD_ROW_RE.match(line.strip()):
                continue
            cells = _parse_md_cells(line)
            if len(cells) < 2 or cells == headers:
                continue

            cell_khoa = _cell(cells, cols["khoa"])
            if cell_khoa and not _SUBJECT_SKIP_RE.match(cell_khoa):
                last_khoa = cell_khoa

            cell_ht = _cell(cells, cols["hinh_thuc"])
            if cell_ht and not _SUBJECT_SKIP_RE.match(cell_ht):
                last_hinh_thuc = cell_ht

            cell_tg = _cell(cells, cols["thoi_gian"])
            if cell_tg:
                last_thoi_gian = cell_tg

            cell_dd = _cell(cells, cols["dia_diem"])
            if cell_dd:
                last_dia_diem = cell_dd

            effective_khoa = last_khoa
            if cohort_filter and not cohort_matches_filter(effective_khoa, cohort_filter):
                continue

            name = _cell(cells, cols["mon"])
            if not name and cols["mon"] is None and len(cells) >= 2:
                name = cells[1].strip()
            if not name or len(name) < 3 or _SUBJECT_SKIP_RE.match(name):
                continue
            if re.match(r"^[-–—\s]+$", name):
                continue

            tt_val = 9999
            raw_tt = re.sub(r"\D", "", _cell(cells, cols["tt"]))
            if raw_tt and _TT_RE.match(raw_tt):
                tt_val = int(raw_tt)

            key = name.lower()
            if key in seen:
                continue
            seen.add(key)

            hinh = cell_ht or last_hinh_thuc
            thoigian = cell_tg or last_thoi_gian
            diadiem = cell_dd or last_dia_diem

            out.append(ScheduleRow(
                tt=tt_val,
                mon_thi=name,
                hinh_thuc=hinh,
                khoa_raw=effective_khoa,
                khoa_expanded=expand_khoa_cell(effective_khoa),
                thoi_gian=thoigian,
                dia_diem=diadiem,
                han_nop_de=_cell(cells, cols["han_nop"]),
                han_lam_phach=_cell(cells, cols["han_phach"]),
                han_cham=_cell(cells, cols["han_cham"]),
            ))

    out.sort(key=lambda r: (r.tt, r.mon_thi.lower()))
    return out


def extract_subjects_from_docs(
    docs: list[dict],
    *,
    cohort_filter: str | None = None,
) -> list[tuple[int, str]]:
    return [(r.tt, r.mon_thi) for r in extract_schedule_rows_from_docs(docs, cohort_filter=cohort_filter)]


def _norm_text(text: str) -> str:
    decomp = unicodedata.normalize("NFD", (text or "").lower())
    plain = "".join(c for c in decomp if unicodedata.category(c) != "Mn")
    plain = re.sub(r"[^a-z0-9\s]", " ", plain)
    return re.sub(r"\s+", " ", plain).strip()


def _subject_tokens(text: str) -> set[str]:
    out = set()
    for tok in _norm_text(text).split():
        if len(tok) < 2:
            continue
        if tok in _STOP_WORDS:
            continue
        out.add(tok)
    return out


def _extract_subject_query(question: str) -> str | None:
    q = (question or "").strip()
    m = _SUBJECT_QUERY_RE.search(q)
    if m:
        cand = m.group(1).strip(" -")
        if len(cand) >= 3:
            return cand
    low = q.lower()
    if any(mk in low for mk in ("địa điểm thi môn", "dia diem thi mon", "giờ thi môn", "gio thi mon")):
        idx = low.find("môn")
        if idx >= 0:
            tail = q[idx + 3:].strip()
            tail = re.split(r"\b(?:thi|học kỳ|hoc ky|kì|ki|đợt|dot|năm|nam)\b", tail, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            if len(tail) >= 3:
                return tail
    return None


def _filter_rows_by_subject(question: str, rows: list[ScheduleRow]) -> tuple[list[ScheduleRow], str | None]:
    subject_q = _extract_subject_query(question)
    if not subject_q:
        return rows, None
    q_norm = _norm_text(subject_q)
    q_tokens = _subject_tokens(subject_q)
    if not q_tokens:
        return rows, None
    scored: list[tuple[tuple[int, int, int], ScheduleRow]] = []
    for r in rows:
        row_norm = _norm_text(r.mon_thi)
        rt = _subject_tokens(r.mon_thi)
        overlap = len(q_tokens & rt)
        if overlap <= 0:
            continue
        exact = 1 if row_norm == q_norm else 0
        contains = 1 if q_norm and q_norm in row_norm else 0
        extra = len(rt - q_tokens)
        score = (exact, contains, overlap * 100 - extra)
        scored.append((score, r))
    if not scored:
        return rows, subject_q
    scored.sort(key=lambda x: x[0], reverse=True)
    best_row = scored[0][1]
    return [best_row], subject_q


def _format_row_line(idx: int, row: ScheduleRow, *, show_khoa: bool) -> str:
    parts = [f"{idx}. **{row.mon_thi}**"]
    if row.hinh_thuc:
        parts.append(f"Hình thức: {row.hinh_thuc}")
    if row.thoi_gian:
        parts.append(f"Thời gian: {row.thoi_gian}")
    if row.dia_diem:
        parts.append(f"Địa điểm: {row.dia_diem}")
    if show_khoa and row.khoa_expanded:
        parts.append(f"Khóa: {', '.join(row.khoa_expanded)}")
    elif show_khoa and row.khoa_raw:
        parts.append(f"Khóa: {row.khoa_raw}")
    return " — ".join(parts)


def _format_period_title(hints: dict, source: str, *, cohort: str | None = None) -> str:
    ki = hints.get("ki")
    hk = "1" if ki == "ki1" else ("2" if ki == "ki2" else "")
    dot_s = {"dot1": " (đợt 1)", "dot2": " (đợt 2)"}.get(hints.get("dot") or "", "")
    yk = hints.get("year_key") or ""
    year_s = f" năm học {yk[:4]}–{yk[4:]}" if len(yk) == 8 else (f" ({yk})" if yk else "")
    khoa_s = f" khóa {cohort}" if cohort else ""
    if hk:
        return f"Lịch thi KTHP{khoa_s} học kỳ {hk}{year_s}{dot_s} (theo `{source}`):"
    return f"Lịch thi trong tài liệu `{source}`:"


def build_schedule_answer(question: str, docs: list[dict], source: str) -> str | None:
    cohort = parse_cohort_from_query(question)
    rows = extract_schedule_rows_from_docs(docs, cohort_filter=cohort)
    hints = parse_schedule_file_hints(question)
    title = _format_period_title(hints, source, cohort=cohort)

    if cohort and not rows:
        return (
            f"{title}\n\n"
            f"Không có dòng nào cho khóa **{cohort}** trong file này.\n"
            f"- Mã ghép kiểu **A19C7D6** = AT19, CT7, DT6 (môn chung nhiều khóa).\n"
            f"- Kiểm tra đúng học kỳ/đợt/năm hoặc mã khóa trong PDF (vd. DT5 thay vì CT5)."
        )

    if not cohort and len(rows) < 5:
        log.warning("[schedule_lookup] chỉ %s dòng — fallback LLM", len(rows))
        return None

    if not rows:
        return None

    filtered_rows, subject_q = _filter_rows_by_subject(question, rows)
    if filtered_rows:
        rows = filtered_rows

    show_khoa = not cohort
    lines = [title, ""]
    if cohort:
        lines.append(
            f"*(Ô khóa dạng ghép A19C7D6 được hiểu là AT19, CT7, DT6 — chỉ lấy dòng có **{cohort}**.)*\n"
        )
    for i, row in enumerate(rows, 1):
        lines.append(_format_row_line(i, row, show_khoa=show_khoa))
    log.info("[schedule_lookup] %s dòng từ %s (khóa=%s)", len(rows), source, cohort)
    return "\n".join(lines)


def build_subject_list_answer(question: str, docs: list[dict], source: str) -> str | None:
    return build_schedule_answer(question, docs, source)


def fetch_schedule_table_docs(
    retriever: "QdrantRetriever",
    query: str,
    agent_id: str,
) -> tuple[list[dict], str, float]:
    import time
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    from config import COLLECTION_NAME
    from pipelines.retrieval import _payload_to_doc

    t0 = time.perf_counter()
    hints = parse_schedule_file_hints(query)
    seed, _ = retriever.retrieve(query, agent_id=agent_id, top_k=8)
    if not seed:
        return [], "", round(time.perf_counter() - t0, 3)

    by_src: dict[str, list[dict]] = {}
    for d in seed:
        src = (d.get("source") or "").strip()
        if src:
            by_src.setdefault(src, []).append(d)

    best_src = max(
        by_src.keys(),
        key=lambda s: score_schedule_source(s, hints)
        + max(float(c.get("_rank_score", c.get("score", 0))) for c in by_src[s]),
    )
    flt = Filter(must=[
        FieldCondition(key="agent_id", match=MatchValue(value=agent_id)),
        FieldCondition(key="source", match=MatchValue(value=best_src)),
    ])

    found: list[dict] = []
    seen: set[tuple] = set()
    offset = None
    while True:
        pts, offset = retriever.qdrant.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=flt,
            limit=64,
            offset=offset,
            with_payload=True,
        )
        for p in pts:
            text = p.payload.get("text") or ""
            dtype = p.payload.get("document_type") or ""
            if dtype not in ("table", "matrix") and "|" not in text:
                continue
            key = (p.payload.get("source"), p.payload.get("page"), text[:80])
            if key in seen:
                continue
            seen.add(key)
            found.append(_payload_to_doc(p, score=0.92))
        if offset is None:
            break

    t_ret = round(time.perf_counter() - t0, 3)
    log.info("[schedule_lookup] scroll %s → %s chunk(s) in %.2fs", best_src, len(found), t_ret)
    return found, best_src, t_ret
