"""
Trích xuất danh sách dự thi (SBD, MSSV, ca, phòng, môn) — không LLM.
Form chuẩn: header Môn thi / Hình thức + bảng STT, SBD, Mã HVSV, Ca thi, Phòng…
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from utils.ingest.metadata_schema import parse_table_headers
from pipelines.retrieval import extract_mssv, _payload_to_doc

if TYPE_CHECKING:
    from pipelines.retrieval import QdrantRetriever

log = logging.getLogger(__name__)

_MD_ROW_RE = re.compile(r"^\|\s*[-:]+")
_MSSV_CELL_RE = re.compile(r"\b(AT|CT|DT)\d{6}\b", re.IGNORECASE)
_MSSV_ALL_RE = re.compile(r"\b(?:AT|CT|DT)\d{6}\b", re.IGNORECASE)
_SBD_LABEL_RE = re.compile(
    r"(?:sbd|số báo danh|so bao danh)\s*[:#]?\s*(\d{1,5})",
    re.IGNORECASE,
)
_MON_HEADER_RE = re.compile(
    r"môn\s*thi\s*:\s*(.+?)(?:\s+hình thức|\s+hinh thuc|$)",
    re.IGNORECASE,
)
_HINH_THUC_HEADER_RE = re.compile(
    r"hình\s*thức\s*thi\s*:\s*(.+?)(?:\s+thời gian|\s+thoi gian|$)",
    re.IGNORECASE,
)
_DATE_IN_QUERY_RE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})")
# Ngày viết bằng chữ: "ngày 21 tháng 4 năm 2026" hoặc "ngày 21 tháng 4"
_DATE_VI_RE = re.compile(
    r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})(?:\s+năm\s+(\d{4}))?",
    re.IGNORECASE,
)
# Phòng thi: "phòng H1.101", "phòng thi 201", "phòng A3", "phòng TA1"
# Yêu cầu phải có ít nhất một chữ số → tránh bắt nhầm "phòng nào", "phòng gì"
# (Các ký tự có dấu tiếng Việt như "à", "ô" không nằm trong [A-Za-z] nên không khớp)
_ROOM_RE = re.compile(
    r"phòng\s+(?:thi\s+)?([A-Za-z]*\d[A-Za-z0-9./\-]{0,13})",
    re.IGNORECASE,
)


@dataclass
class ExamListMeta:
    mon_thi: str = ""
    hinh_thuc: str = ""
    thoi_gian_lam_bai: str = ""
    tong_thi_sinh: str = ""


@dataclass
class ExamListRow:
    stt: str = ""
    sbd: str = ""
    mssv: str = ""
    ho_ten: str = ""
    ngay_thi: str = ""
    ca_thi: str = ""
    phong: str = ""
    ghi_chu: str = ""
    tp1: str = ""
    tp2: str = ""
    dqt: str = ""


@dataclass
class ExamListChunk:
    meta: ExamListMeta
    rows: list[ExamListRow] = field(default_factory=list)
    source: str = ""
    page: int = 0


def wants_exam_list_query(question: str) -> bool:
    blob = (question or "").lower()
    if extract_mssv(question) or parse_sbd(question):
        return True
    explicit_markers = (
        "danh sách thi", "danh sach thi", "danh sách dự thi", "danh sach du thi",
        "số báo danh", "so bao danh", "sbd",
        "ca thi", "ca sáng", "ca sang", "ca chiều", "ca chieu",
        "phòng thi", "phong thi", "mã hssv", "ma hssv", "mã sv",
    )
    if any(
        m in blob
        for m in explicit_markers
    ):
        return True
    return False


def parse_sbd(question: str) -> str | None:
    m = _SBD_LABEL_RE.search(question or "")
    if m:
        return m.group(1).strip()
    return None


def extract_all_mssv(question: str) -> list[str]:
    """Tìm tất cả MSSV (AT/CT/DT) trong câu hỏi, bảo toàn thứ tự, không trùng."""
    return list(dict.fromkeys(m.upper() for m in _MSSV_ALL_RE.findall(question or "")))


def _parse_room_from_query(question: str) -> str | None:
    """Trích tên phòng thi từ câu hỏi — vd. 'phòng H1.101', 'phòng thi A3'."""
    m = _ROOM_RE.search(question or "")
    return m.group(1).strip() if m else None


def parse_date_hints(query: str) -> dict[str, str]:
    """Ngày / thứ / sáng-chiều từ câu hỏi để khớp tên file danh-sach-thi-*."""
    q = (query or "").lower()
    hints: dict[str, str] = {}

    # Ưu tiên dạng số: 21/04/2026, 21.04.2026, 21-04-2026
    dm = _DATE_IN_QUERY_RE.search(query or "")
    if dm:
        d, mo, y = dm.group(1), dm.group(2), dm.group(3)
        if len(y) == 2:
            y = "20" + y
        hints["day"] = d.zfill(2) if len(d) < 2 else d
        hints["month"] = mo.zfill(2) if len(mo) < 2 else mo
        hints["year"] = y
        hints["file_date"] = f"ngay-{int(d)}-{int(mo)}-{y}"
    else:
        # Dạng chữ tiếng Việt: "ngày 21 tháng 4 năm 2026"
        vi = _DATE_VI_RE.search(query or "")
        if vi:
            d, mo = vi.group(1), vi.group(2)
            y = vi.group(3) or ""
            hints["day"] = d.zfill(2) if len(d) < 2 else d
            hints["month"] = mo.zfill(2) if len(mo) < 2 else mo
            if y:
                hints["year"] = y
                hints["file_date"] = f"ngay-{int(d)}-{int(mo)}-{y}"
            else:
                hints["file_date"] = f"ngay-{int(d)}-{int(mo)}"

    thu = re.search(r"thứ\s*(\d)|thu\s*(\d)", q)
    if thu:
        hints["thu"] = thu.group(1) or thu.group(2)
    if any(m in q for m in ("sáng", "sang", "buổi sáng")):
        hints["session"] = "sang"
    elif any(m in q for m in ("chiều", "chieu", "buổi chiều")):
        hints["session"] = "chieu"
    return hints


def _normalize_row_date(ngay: str) -> tuple[str, str, str] | None:
    """dd/mm/yyyy từ ô Ngày thi."""
    m = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", ngay or "")
    if not m:
        return None
    d, mo, y = m.group(1), m.group(2), m.group(3)
    if len(y) == 2:
        y = "20" + y
    return d.zfill(2), mo.zfill(2), y


def row_matches_date_hint(row: ExamListRow, hints: dict[str, str]) -> bool:
    """Lọc dòng theo ngày trong câu hỏi (vd. 22/04/2026)."""
    want_d = hints.get("day")
    want_m = hints.get("month")
    want_y = hints.get("year")
    if not want_d and not want_m:
        return True
    parsed = _normalize_row_date(row.ngay_thi)
    if not parsed:
        return True
    d, mo, y = parsed
    if want_d and int(d) != int(want_d):
        return False
    if want_m and int(mo) != int(want_m):
        return False
    if want_y and y != want_y:
        return False
    return True


def score_exam_list_source(source: str, hints: dict[str, str]) -> float:
    src = (source or "").lower()
    score = 0.0
    if "danh-sach-thi" in src or "danh_sach_thi" in src:
        score += 0.5
    fd = hints.get("file_date", "")
    if fd:
        if fd in src:
            score += 12.0
        else:
            other = re.search(r"ngay-(\d+)-(\d+)-(\d{4})", src)
            if other:
                qd, qm = hints.get("day"), hints.get("month")
                if qd and (
                    int(other.group(1)) != int(qd)
                    or (qm and int(other.group(2)) != int(qm))
                ):
                    score -= 10.0
    thu = hints.get("thu")
    if thu:
        if f"thu-{thu}" in src:
            score += 4.0
        elif re.search(r"thu-\d", src):
            score -= 3.0
    sess = hints.get("session")
    if sess and sess in src:
        score += 1.5
    y = hints.get("year")
    if y and y in src:
        score += 1.0
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
        "stt": _col_index(headers, "stt", "tt") or 0,
        "sbd": _col_index(headers, "sbd", "số báo danh", "so bao danh"),
        "mssv": _col_index(headers, "mã hssv", "ma hssv", "mã sv", "mssv", "mã hvsv"),
        "ho": _col_index(headers, "họ đệm", "ho dem", "họ"),
        "ten": _col_index(headers, "tên", "ten"),
        "ngay": _col_index(headers, "ngày thi", "ngay thi"),
        "ca": _col_index(headers, "ca thi", "ca"),
        "phong": _col_index(headers, "phòng", "phong"),
        "ghi_chu": _col_index(headers, "ghi chú", "ghi chu"),
        "tp1": _col_index(headers, "tp1"),
        "tp2": _col_index(headers, "tp2"),
        "dqt": _col_index(headers, "đqt", "dqt"),
    }


def _cell(cells: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(cells):
        return ""
    return cells[idx].strip()


def _parse_meta_from_text(text: str) -> ExamListMeta:
    meta = ExamListMeta()
    raw = text or ""
    for line in raw.splitlines():
        low = line.lower().strip()
        if low.startswith("môn thi") or low.startswith("mon thi"):
            parts = re.split(r":", line, maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                meta.mon_thi = parts[1].strip()
        if ("hình thức" in low or "hinh thuc" in low) and ":" in line:
            parts = re.split(r":", line, maxsplit=1)
            if len(parts) > 1:
                meta.hinh_thuc = parts[1].strip()
    flat = " ".join(raw.split())
    if not meta.mon_thi:
        m = _MON_HEADER_RE.search(flat)
        if m:
            meta.mon_thi = m.group(1).strip()
    if not meta.hinh_thuc:
        m2 = _HINH_THUC_HEADER_RE.search(flat)
        if m2:
            meta.hinh_thuc = m2.group(1).strip()
    m3 = re.search(r"tổng\s*số\s*thí\s*sinh\s*:\s*(\d+)", flat, re.I)
    if m3:
        meta.tong_thi_sinh = m3.group(1)
    m4 = re.search(r"thời\s*gian\s*làm\s*bài\s*:\s*(\d+)", flat, re.I)
    if m4:
        meta.thoi_gian_lam_bai = m4.group(1)
    return meta


def _merge_meta(base: ExamListMeta, extra: ExamListMeta) -> ExamListMeta:
    return ExamListMeta(
        mon_thi=base.mon_thi or extra.mon_thi,
        hinh_thuc=base.hinh_thuc or extra.hinh_thuc,
        thoi_gian_lam_bai=base.thoi_gian_lam_bai or extra.thoi_gian_lam_bai,
        tong_thi_sinh=base.tong_thi_sinh or extra.tong_thi_sinh,
    )


def extract_exam_chunks_from_docs(docs: list[dict]) -> list[ExamListChunk]:
    """Mỗi chunk bảng → meta + các dòng SV."""
    ordered = sorted(
        docs,
        key=lambda d: (d.get("source", ""), d.get("page", 0), d.get("child_index", 0)),
    )
    chunks_out: list[ExamListChunk] = []

    for doc in ordered:
        text = doc.get("text") or ""
        meta = _parse_meta_from_text(text)
        headers = parse_table_headers(doc.get("table_headers"))
        if not headers:
            continue
        cols = _header_map(headers)
        rows: list[ExamListRow] = []

        for line in text.splitlines():
            if not line.strip().startswith("|") or _MD_ROW_RE.match(line.strip()):
                continue
            cells = _parse_md_cells(line)
            if len(cells) < 3 or cells == headers:
                continue

            mssv = _cell(cells, cols["mssv"])
            if not mssv:
                for c in cells:
                    m = _MSSV_CELL_RE.search(c)
                    if m:
                        mssv = m.group(0).upper()
                        break

            ho = _cell(cells, cols["ho"])
            ten = _cell(cells, cols["ten"])
            ho_ten = f"{ho} {ten}".strip() if ten else ho

            rows.append(ExamListRow(
                stt=_cell(cells, cols["stt"]),
                sbd=_cell(cells, cols["sbd"]),
                mssv=mssv.upper() if mssv else "",
                ho_ten=ho_ten,
                ngay_thi=_cell(cells, cols["ngay"]),
                ca_thi=_cell(cells, cols["ca"]),
                phong=_cell(cells, cols["phong"]),
                ghi_chu=_cell(cells, cols["ghi_chu"]),
                tp1=_cell(cells, cols["tp1"]),
                tp2=_cell(cells, cols["tp2"]),
                dqt=_cell(cells, cols["dqt"]),
            ))

        if rows:
            chunks_out.append(ExamListChunk(
                meta=meta,
                rows=rows,
                source=doc.get("source", ""),
                page=int(doc.get("page", 0)),
            ))

    return chunks_out


def _find_rows_by_room(
    chunks: list[ExamListChunk],
    *,
    room: str,
    date_hints: dict[str, str] | None = None,
) -> list[tuple[ExamListMeta, ExamListRow, str]]:
    """Tìm tất cả thí sinh trong phòng thi chỉ định."""
    hits: list[tuple[ExamListMeta, ExamListRow, str]] = []
    room_norm = re.sub(r"\s+", "", room.lower())
    dh = date_hints or {}
    for ch in chunks:
        for row in ch.rows:
            row_room = re.sub(r"\s+", "", row.phong.lower())
            if not row_room:
                continue
            if room_norm not in row_room and row_room not in room_norm:
                continue
            if dh and not row_matches_date_hint(row, dh):
                continue
            hits.append((ch.meta, row, ch.source))
    return hits


def _find_rows(
    chunks: list[ExamListChunk],
    *,
    mssv: str | None = None,
    sbd: str | None = None,
    date_hints: dict[str, str] | None = None,
) -> list[tuple[ExamListMeta, ExamListRow, str]]:
    hits: list[tuple[ExamListMeta, ExamListRow, str]] = []
    mssv_u = (mssv or "").upper()
    sbd_s = (sbd or "").strip()
    dh = date_hints or {}

    for ch in chunks:
        for row in ch.rows:
            if mssv_u and row.mssv != mssv_u:
                continue
            if sbd_s and row.sbd != sbd_s:
                continue
            if dh and not row_matches_date_hint(row, dh):
                continue
            if mssv_u or sbd_s:
                hits.append((ch.meta, row, ch.source))

    return hits


def _format_multi_exam_answer(
    hits: list[tuple[ExamListMeta, ExamListRow, str]],
    mssv: str,
    date_hints: dict[str, str],
) -> str:
    """Một MSSV có thể thi nhiều môn — liệt kê đủ SBD/ca/phòng từng môn."""
    name = hits[0][1].ho_ten or ""
    date_s = ""
    if date_hints.get("day") and date_hints.get("month"):
        y = date_hints.get("year", "")
        date_s = f" ngày {date_hints['day']}/{date_hints['month']}" + (f"/{y}" if y else "")

    lines = [
        f"Sinh viên **{mssv}**{(' — ' + name) if name else ''}{date_s} "
        f"có **{len(hits)}** môn thi trong danh sách:",
        "",
    ]
    for i, (meta, row, src) in enumerate(hits, 1):
        mon = meta.mon_thi or "(xem file)"
        lines.append(f"**{i}. {mon}** (`{src}`)")
        lines.append(f"   - SBD: **{row.sbd or '—'}** | Ca: {row.ca_thi or '—'} | Phòng: {row.phong or '—'}")
        if row.ngay_thi:
            lines.append(f"   - Ngày thi: {row.ngay_thi}")
        if meta.hinh_thuc:
            lines.append(f"   - Hình thức: {meta.hinh_thuc}")
        if row.ghi_chu:
            lines.append(f"   - Ghi chú: {row.ghi_chu}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_room_answer(
    room: str,
    hits: list[tuple[ExamListMeta, ExamListRow, str]],
    date_hints: dict[str, str],
    source: str,
) -> str:
    """Liệt kê thí sinh trong phòng thi."""
    date_s = ""
    if date_hints.get("day") and date_hints.get("month"):
        y = date_hints.get("year", "")
        date_s = f" ngày {date_hints['day']}/{date_hints['month']}" + (f"/{y}" if y else "")
    lines = [f"Phòng **{room}**{date_s} — **{len(hits)}** thí sinh:\n"]
    for i, (meta, row, src) in enumerate(hits[:60], 1):
        lines.append(
            f"{i}. {row.ho_ten or '—'} — MSSV **{row.mssv or '—'}**, "
            f"SBD {row.sbd or '—'}, ca {row.ca_thi or '—'}"
        )
    if len(hits) > 60:
        lines.append(f"\n*(Còn {len(hits) - 60} thí sinh khác...)*")
    if hits:
        meta0 = hits[0][0]
        if meta0.mon_thi:
            lines.append(f"\n*Môn thi: {meta0.mon_thi}*")
        if meta0.hinh_thuc:
            lines.append(f"*Hình thức: {meta0.hinh_thuc}*")
    return "\n".join(lines)


def _format_multi_mssv_combined(
    results: list[tuple[str, list[tuple[ExamListMeta, ExamListRow, str]]]],
    date_hints: dict[str, str],
) -> str:
    """Kết quả tra nhiều MSSV cùng lúc."""
    parts = []
    for mssv, hits in results:
        parts.append(_format_multi_exam_answer(hits, mssv, date_hints))
    return "\n\n---\n\n".join(parts)


def _format_student_answer(
    meta: ExamListMeta,
    row: ExamListRow,
    source: str,
    question: str,
) -> str:
    mon = meta.mon_thi or "(môn ghi trong file)"
    lines = [
        f"Thông tin dự thi trong **{source}**:",
        "",
        f"- **Môn thi:** {mon}",
    ]
    if meta.hinh_thuc:
        lines.append(f"- **Hình thức:** {meta.hinh_thuc}")
    if meta.thoi_gian_lam_bai:
        lines.append(f"- **Thời gian làm bài:** {meta.thoi_gian_lam_bai} phút")
    lines.extend([
        f"- **Họ tên:** {row.ho_ten or '(trong bảng)'}",
        f"- **Mã SV:** {row.mssv or '—'}",
        f"- **SBD:** {row.sbd or '—'}",
        f"- **Ngày thi:** {row.ngay_thi or '—'}",
        f"- **Ca thi:** {row.ca_thi or '—'}",
        f"- **Phòng:** {row.phong or '—'}",
    ])
    if row.ghi_chu:
        lines.append(f"- **Ghi chú:** {row.ghi_chu}")
    if not row.sbd and not row.ca_thi and row.ghi_chu:
        lines.append(
            "\n*(Sinh viên có ghi chú cấm thi / nợ HP — thường không có SBD, ca, phòng.)*"
        )
    return "\n".join(lines)


def _scroll_source_chunks(
    retriever: "QdrantRetriever",
    agent_id: str,
    source: str,
) -> list[dict]:
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    from config import COLLECTION_NAME

    flt = Filter(must=[
        FieldCondition(key="agent_id", match=MatchValue(value=agent_id)),
        FieldCondition(key="source", match=MatchValue(value=source)),
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
                if "môn thi" not in text.lower() and "sbd" not in text.lower():
                    continue
            key = (p.payload.get("source"), p.payload.get("page"), text[:80])
            if key in seen:
                continue
            seen.add(key)
            found.append(_payload_to_doc(p, score=0.92))
        if offset is None:
            break
    return found


def _pick_sources_for_mssv(
    by_src: dict[str, list[dict]],
    hints: dict[str, str],
) -> list[str]:
    """Ưu tiên file đúng ngày/thứ trong câu hỏi, không chọn file có nhiều chunk nhất."""
    if not by_src:
        return []
    scored = [
        (src, score_exam_list_source(src, hints) + 0.01 * len(chunks))
        for src, chunks in by_src.items()
    ]
    scored.sort(key=lambda x: -x[1])
    best_score = scored[0][1]
    if hints.get("file_date") or hints.get("thu"):
        picked = [s for s, sc in scored if sc >= best_score - 1.0 and sc >= 2.0]
        if picked:
            return picked
    return [scored[0][0]]


def fetch_exam_list_docs(
    retriever: "QdrantRetriever",
    query: str,
    agent_id: str = "danh_sach_thi",
) -> tuple[list[dict], str, float]:
    import time

    t0 = time.perf_counter()
    hints = parse_date_hints(query)
    # Lấy tất cả MSSV trong câu hỏi; dùng MSSV đầu tiên để tìm file nguồn
    all_mssv = extract_all_mssv(query)
    mssv = all_mssv[0] if all_mssv else extract_mssv(query)

    if mssv:
        docs = retriever._lookup_mssv_chunks(mssv, agent_id, limit=200)
        if docs:
            by_src: dict[str, list[dict]] = {}
            for d in docs:
                by_src.setdefault(d.get("source", ""), []).append(d)
            sources = _pick_sources_for_mssv(by_src, hints)
            merged: list[dict] = []
            seen_keys: set[tuple] = set()
            for src in sources:
                full = _scroll_source_chunks(retriever, agent_id, src)
                for d in full:
                    k = (d.get("source"), d.get("page"), (d.get("text") or "")[:80])
                    if k not in seen_keys:
                        seen_keys.add(k)
                        merged.append(d)
                for d in by_src.get(src, []):
                    k = (d.get("source"), d.get("page"), (d.get("text") or "")[:80])
                    if k not in seen_keys:
                        seen_keys.add(k)
                        merged.append(d)
            primary = sources[0]
            t_ret = round(time.perf_counter() - t0, 3)
            log.info(
                "[exam_list] MSSV %s → %s file(s) %s, %s chunk(s)",
                mssv, len(sources), sources, len(merged),
            )
            return merged, primary, t_ret

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
        key=lambda s: score_exam_list_source(s, hints)
        + max(float(c.get("_rank_score", c.get("score", 0))) for c in by_src[s]),
    )

    found = _scroll_source_chunks(retriever, agent_id, best_src)

    t_ret = round(time.perf_counter() - t0, 3)
    log.info("[exam_list] scroll %s → %s chunk(s) in %.2fs", best_src, len(found), t_ret)
    return found, best_src, t_ret


def build_exam_list_answer(
    question: str,
    docs: list[dict],
    source: str,
) -> str | None:
    all_mssv = extract_all_mssv(question)
    mssv = all_mssv[0] if all_mssv else None
    sbd = parse_sbd(question)
    date_hints = parse_date_hints(question)
    room = _parse_room_from_query(question)
    chunks = extract_exam_chunks_from_docs(docs)

    if not chunks and not docs:
        return None

    # --- Nhiều MSSV (≥ 2 trong câu hỏi) ---
    if len(all_mssv) >= 2:
        multi_results: list[tuple[str, list[tuple[ExamListMeta, ExamListRow, str]]]] = []
        not_found: list[str] = []
        for m in all_mssv:
            hits = _find_rows(chunks, mssv=m, date_hints=date_hints)
            if not hits and (date_hints.get("day") or date_hints.get("file_date")):
                hits = _find_rows(chunks, mssv=m, date_hints={})
            if hits:
                multi_results.append((m, hits))
            else:
                not_found.append(m)
        if multi_results:
            ans = _format_multi_mssv_combined(multi_results, date_hints)
            if not_found:
                ans += f"\n\n*Không tìm thấy trong danh sách: **{', '.join(not_found)}**.*"
            return ans
        # Tất cả đều không tìm thấy → báo lỗi cho từng MSSV
        date_note = ""
        if date_hints.get("file_date"):
            date_note = f" ngày {date_hints.get('day')}/{date_hints.get('month')}/{date_hints.get('year', '')}"
        return (
            f"Không tìm thấy các MSSV **{', '.join(all_mssv)}** trong danh sách thi{date_note}. "
            f"File đã tra: `{source or '—'}`. Kiểm tra đúng ngày hoặc ingest `danh_sach_thi`."
        )

    # --- Một MSSV hoặc SBD ---
    if mssv or sbd:
        hits = _find_rows(chunks, mssv=mssv, sbd=sbd, date_hints=date_hints)
        if not hits and (date_hints.get("day") or date_hints.get("file_date")):
            hits = _find_rows(chunks, mssv=mssv, sbd=sbd, date_hints={})
        if not hits and mssv:
            date_note = ""
            if date_hints.get("file_date"):
                date_note = f" (đã lọc theo ngày {date_hints.get('day')}/{date_hints.get('month')}/{date_hints.get('year', '')})"
            return (
                f"Không tìm thấy MSSV **{mssv}** trong danh sách thi{date_note}. "
                f"File đã tra: `{source or '—'}`. Kiểm tra đúng ngày (vd. file *ngay-22-4-2026*) hoặc ingest `danh_sach_thi`."
            )
        if not hits and sbd:
            return (
                f"Không tìm thấy SBD **{sbd}** trong `{source or 'tài liệu đã tra'}`. "
                "Thử kèm MSSV hoặc ngày thi (vd. 22/04/2026) trong câu hỏi."
            )
        if len(hits) >= 1 and mssv:
            return _format_multi_exam_answer(hits, mssv, date_hints)
        if len(hits) == 1:
            meta, row, src = hits[0]
            return _format_student_answer(meta, row, src, question)
        lines = [f"Tìm thấy **{len(hits)}** dòng phù hợp:\n"]
        for i, (meta, row, src) in enumerate(hits[:20], 1):
            lines.append(
                f"{i}. **{meta.mon_thi or 'Môn'}** — SBD **{row.sbd or '—'}**, "
                f"ca {row.ca_thi or '—'}, phòng {row.phong or '—'}, "
                f"ngày {row.ngay_thi or '—'} ({row.mssv} | {src})"
            )
        return "\n".join(lines)

    # --- Tra theo phòng thi cụ thể ---
    if room:
        room_hits = _find_rows_by_room(chunks, room=room, date_hints=date_hints)
        if not room_hits and date_hints:
            room_hits = _find_rows_by_room(chunks, room=room, date_hints={})
        if room_hits:
            return _format_room_answer(room, room_hits, date_hints, source)
        return (
            f"Không tìm thấy danh sách thí sinh cho phòng **{room}** "
            f"trong `{source or 'tài liệu đã tra'}`. "
            "Thử kèm ngày thi (vd. 22/04/2026) hoặc kiểm tra tên phòng chính xác."
        )

    # --- Tổng hợp chung (không có ID cụ thể) ---
    merged_meta = ExamListMeta()
    total_rows = 0
    for ch in chunks:
        merged_meta = _merge_meta(merged_meta, ch.meta)
        total_rows += len(ch.rows)

    if total_rows < 3:
        return None

    sample = chunks[0]
    title = merged_meta.mon_thi or sample.meta.mon_thi or source
    lines = [
        f"**{title}** (`{source}`)",
        "",
    ]
    if merged_meta.hinh_thuc:
        lines.append(f"- Hình thức: {merged_meta.hinh_thuc}")
    if merged_meta.tong_thi_sinh:
        lines.append(f"- Tổng số thí sinh: {merged_meta.tong_thi_sinh}")
    lines.append(f"- Số dòng trong bảng đã đọc: {total_rows}")
    lines.append(
        "\nĐể tra **SBD / ca / phòng** của một sinh viên, hãy gửi **MSSV** (vd. CT100101) "
        "hoặc **số báo danh** kèm ngày thi nếu biết."
    )
    if sample.rows:
        lines.append("\n*Ví dụ dòng đầu:*")
        lines.append(
            f"  {sample.rows[0].ho_ten} — SBD {sample.rows[0].sbd}, "
            f"ca {sample.rows[0].ca_thi}, phòng {sample.rows[0].phong}"
        )
    return "\n".join(lines)
