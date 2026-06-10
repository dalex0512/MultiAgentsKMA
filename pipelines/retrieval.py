"""
Shared Qdrant retrieval — hỗ trợ lọc theo agent_id cho Multi-Agent RAG.
Bảng điểm PDF: bổ sung tra cứu theo MSSV (embedding thường không khớp dòng bảng).
"""

import re
import time
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter, FieldCondition, MatchValue, MatchText,
    TextIndexParams, TokenizerType,
)

from config import (
    QDRANT_URL, QDRANT_API_KEY,
    COLLECTION_NAME, EMBED_MODEL, TOP_K, ACCURACY_MODE,
    PARENT_SEARCH_POOL_MULTIPLIER, PARENT_RETRIEVE_MAX,
    embed_client,
)
from utils.chunking.retrieval_expand import (
    collapse_child_hits_to_parents,
    uses_parent_child_retrieval,
)

log = logging.getLogger(__name__)

# Gợi ý tên file / môn khi câu hỏi nhắc môn cụ thể (tránh lẫn ma trận cùng folder)
_SUBJECT_HINTS: list[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = [
    (("tin học", "tin hoc", "đại cương", "dai cuong"), ("tin_hoc", "tin-hoc", "dai_cuong"), ("toan", "cao_cap", "a3")),
    (("toán", "toan", "cao cấp", "cao cap", "a3"), ("toan", "cao_cap", "a3"), ("tin_hoc", "csdl", "kiem_thu")),
    (("cơ sở dữ liệu", "csdl", "lý thuyết"), ("csdl", "co_so_du_lieu"), ("tin_hoc", "toan", "kiem_thu")),
    (("kiểm thử", "kiem thu", "athttt"), ("kiem_thu", "kiem-thu"), ("tin_hoc", "toan", "csdl")),
    (("quản trị", "an toàn", "qtanht"), ("qtanht", "quan_tri"), ("tin_hoc", "toan")),
    (("an toàn thương mại", "thuong mai", "attm"), ("attm", "an_toan"), ("tin_hoc", "toan")),
]

# Ưu tiên đúng file hk1/hk2, dot1/dot2, năm (20242025) khi hỏi điểm
_DIEM_FILE_HINTS: list[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = [
    (("đợt 1", "dot 1", "đợt một", "dot1"), ("dot1",), ("dot2",)),
    (("đợt 2", "dot 2", "đợt hai", "dot2"), ("dot2",), ("dot1",)),
    (("học kỳ 2", "hoc ky 2", "hk2", "học kỳ ii"), ("hk2",), ("hk1",)),
    (("học kỳ 1", "hoc ky 1", "hk1", "học kỳ i"), ("hk1",), ("hk2",)),
    (("2024-2025", "2024 2025", "20242025", "24-25"), ("20242025", "hk2_2024"), ("20222023", "hk1_2022")),
    (("2022-2023", "2022 2023", "20222023"), ("20222023", "hk1_2022"), ("20242025",)),
]

# File điểm đặc biệt: phân loại TA, CT4, chứng chỉ — không lẫn bảng điểm HK
_DIEM_SPECIAL_FILE_HINTS: list[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = [
    (
        ("phân loại", "phan loai", "tiếng anh", "tieng anh", "đầu vào", "dau vao",
         "anh văn", "anh van", "kiểm tra tiếng anh", "kiem tra tieng anh"),
        ("08_ket_qua_thi_anh_van", "ket_qua_thi_anh"),
        ("hk1", "hk2", "dot1", "dot2"),
    ),
    (
        ("ct4", "tốt nghiệp", "tot nghiep"),
        ("04_ket_qua_tot_nghiep_ct4", "ket_qua_tot_nghiep"),
        ("hk1", "hk2"),
    ),
    (
        ("chứng chỉ", "chung chi", "nhan chung", "nhận chứng"),
        ("12_ds_nhan_chung_chi_ta", "nhan_chung_chi"),
        ("hk1", "hk2"),
    ),
]

_ENGLISH_CLASSIFICATION_MARKERS = (
    "phân loại", "phan loai", "tiếng anh", "tieng anh", "đầu vào", "dau vao",
    "anh văn", "anh van", "kiểm tra tiếng anh", "kiem tra tieng anh",
)

# KMA: ATxxxxxx, CTxxxxxx, DTxxxxxx, … (2 chữ + 6 số)
_MSSV_RE = re.compile(r"\b(?:AT|CT|DT)\d{6}\b", re.IGNORECASE)
# Biến thể có dấu gạch hoặc khoảng trắng: AT-170514, AT 170514
_MSSV_SEP_RE = re.compile(r"\b(AT|CT|DT)[\s\-](\d{6})\b", re.IGNORECASE)
_TEXT_INDEX_READY = False


def extract_mssv(query: str) -> str | None:
    q = query or ""
    m = _MSSV_RE.search(q)
    if m:
        return m.group(0).upper()
    # Thử normalize dấu gạch / khoảng trắng giữa prefix và số
    m2 = _MSSV_SEP_RE.search(q)
    if m2:
        return (m2.group(1) + m2.group(2)).upper()
    return None


def extract_all_mssv(query: str) -> list[str]:
    """Tìm tất cả MSSV (AT/CT/DT) trong câu hỏi, bảo toàn thứ tự, không trùng."""
    q = query or ""
    found: list[str] = []
    for m in _MSSV_RE.finditer(q):
        u = m.group(0).upper()
        if u not in found:
            found.append(u)
    for m in _MSSV_SEP_RE.finditer(q):
        u = (m.group(1) + m.group(2)).upper()
        if u not in found:
            found.append(u)
    return found


def _is_english_classification_query(query: str) -> bool:
    low = (query or "").lower()
    return any(m in low for m in _ENGLISH_CLASSIFICATION_MARKERS)


def _parse_diem_period_hints(query: str) -> dict[str, str | None]:
    """Tách hk / đợt / năm từ câu hỏi để khớp tên file (vd. hk2_20242025_dot1.pdf).
    Trả về multi_dot=True khi hỏi cả đợt 1 và đợt 2 → không lọc theo đợt.
    """
    q = (query or "").lower()
    hints: dict[str, str | None] = {"hk": None, "dot": None, "year_key": None}
    if any(p in q for p in ("học kỳ 2", "hoc ky 2", "hk2", "học kỳ ii", "ky 2")):
        hints["hk"] = "hk2"
    elif any(p in q for p in ("học kỳ 1", "hoc ky 1", "hk1", "học kỳ i", "ky 1")):
        hints["hk"] = "hk1"

    has_dot1 = any(p in q for p in ("đợt 1", "dot 1", "đợt một", "dot1"))
    has_dot2 = any(p in q for p in ("đợt 2", "dot 2", "đợt hai", "dot2"))
    if has_dot1 and has_dot2:
        # Hỏi cả 2 đợt (so sánh / cải thiện) → không lọc đợt
        hints["dot"] = None
    elif has_dot1:
        hints["dot"] = "dot1"
    elif has_dot2:
        hints["dot"] = "dot2"

    ym = re.search(r"20(\d{2})\s*[-–]?\s*20(\d{2})", q)
    if ym:
        hints["year_key"] = f"20{ym.group(1)}20{ym.group(2)}"
    else:
        ym2 = re.search(r"\b(20\d{6})\b", q)
        if ym2:
            hints["year_key"] = ym2.group(1)
    return hints


def _source_matches_diem_hints(source: str, hints: dict[str, str | None]) -> bool:
    src = (source or "").lower().replace(".pdf", "").replace("-", "_")
    if hints.get("hk") and hints["hk"] not in src:
        return False
    if hints.get("dot") and hints["dot"] not in src:
        return False
    yk = hints.get("year_key")
    if yk and yk not in src.replace("_", ""):
        return False
    return True


def filter_docs_by_diem_period(query: str, docs: list[dict]) -> list[dict]:
    """Chỉ giữ chunk từ file đúng kỳ/đợt/năm khi câu hỏi nêu rõ."""
    hints = _parse_diem_period_hints(query)
    if not any(hints.values()):
        return docs
    matched = [d for d in docs if _source_matches_diem_hints(d.get("source", ""), hints)]
    if matched:
        files = {d.get("source") for d in matched}
        log.info("[retrieval] lọc kỳ/đợt %s → %s chunk, file=%s", hints, len(matched), files)
        return matched
    log.warning(
        "[retrieval] lọc kỳ/đợt %s: không khớp tên file — giữ %s chunk MSSV",
        hints, len(docs),
    )
    return docs


_NAME_LABEL_RE = re.compile(
    r"(?:tên|ten)(?:\s+là|\s*:)?\s*([^,?.!\n]+?)(?=\s+với|\s*,\s*mã|\s+mssv|\s+(?:at|ct)\d|\s*$)",
    re.IGNORECASE,
)
# "của Nguyễn Văn A có mã sinh viên ..."
_NAME_OF_RE = re.compile(
    r"(?:của|của)\s+"
    r"((?![^,?.!\n]*(?:mã\s+sinh|ma\s+sinh|học\s+kỳ|hoc\s+ky|đợt|dot\s))[^,?.!\n]{4,80}?)"
    r"(?=\s+(?:có\s+mã|co\s+ma|mssv|ma\s+sinh|\(|\s+(?:at|ct)\d{6}|\s*$))",
    re.IGNORECASE,
)
# Chỉ khi không có "có mã" ngay sau — tránh "... sinh viên CÓ MÃ SINH VIÊN LÀ CT..."
_NAME_SV_RE = re.compile(
    r"sinh\s*vi[eê]n\s+"
    r"(?!có\s+mã|co\s+ma|mã\s+sinh|ma\s+sinh)"
    r"([^,?.!\n]+?)(?=\s+với|\s*,\s*mã|\s+mssv|\s+(?:at|ct)\d|\s*$)",
    re.IGNORECASE,
)
_NAME_PROPER_RE = re.compile(
    r"\b((?:[A-ZÀ-ỸĂÂĐÊÔƠƯ][\wà-ỹăâđêôơưáàảãạấầẩẫậắằẳẵặếềểễệốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]+"
    r"(?:\s+)){1,3}[A-ZÀ-ỸĂÂĐÊÔƠƯ][\wà-ỹăâđêôơưáàảãạấầẩẫậắằẳẵặếềểễệốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]+)\b"
)


def _normalize_name_key(text: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _is_plausible_student_name(name: str) -> bool:
    """Loại cụm bị regex bắt nhầm (vd. 'CÓ MÃ SINH VIÊN LÀ')."""
    n = (name or "").strip(" \"'")
    if len(n) < 4 or extract_mssv(n):
        return False
    low = _normalize_name_key(n)
    bad = (
        "ma sinh vien", "mã sinh viên", "mssv", "hoc ky", "học kỳ", "dot ", "đợt",
        "co ma", "có mã", "la ct", "là ct", "sinh vien", "sinh viên", "thi hoc",
        "điểm thi", "diem thi", "của sinh", "cua sinh", "co ma sinh", "có ma sinh",
    )
    if any(b in low for b in bad):
        return False
    words = n.split()
    if len(words) >= 2 and sum(1 for w in words if w.isupper() and len(w) > 1) >= len(words) - 1:
        return False
    return True


def extract_student_name(query: str) -> str | None:
    """Tách họ tên từ câu hỏi (tùy chọn, dùng lọc chunk bảng điểm)."""
    q = (query or "").strip()
    if not q:
        return None
    for pat in (_NAME_OF_RE, _NAME_LABEL_RE, _NAME_SV_RE):
        m = pat.search(q)
        if m:
            name = m.group(1).strip(" \"'")
            if _is_plausible_student_name(name):
                return name
    for m in _NAME_PROPER_RE.finditer(q):
        cand = m.group(1).strip()
        if not _is_plausible_student_name(cand):
            continue
        low = _normalize_name_key(cand)
        skip = ("hoc ky", "dot ", "diem", "bang diem", "file ", "pdf", "kma", "ma sinh")
        if any(s in low for s in skip):
            continue
        return cand
    return None


def name_matches_text(name: str, text: str) -> bool:
    parts = [p for p in _normalize_name_key(name).split() if len(p) >= 2]
    if len(parts) < 2:
        return True
    blob = _normalize_name_key(text)
    return all(p in blob for p in parts)


def _keyword_adjust(query: str, doc: dict, agent_id: str | None = None) -> float:
    """Điều chỉnh điểm theo tên file / MSSV / môn — bổ sung cho embedding."""
    q   = query.lower()
    src = doc.get("source", "").lower()
    txt = doc.get("text", "")
    blob = f"{src} {txt.lower()[:400]}"
    delta = 0.0
    for phrases, prefer, avoid in _SUBJECT_HINTS:
        if any(p in q for p in phrases):
            if any(p in blob for p in prefer):
                delta += 0.18
            if any(a in src for a in avoid):
                delta -= 0.22
            break
    if agent_id == "diem_thi":
        for phrases, prefer, avoid in _DIEM_FILE_HINTS:
            if any(p in q for p in phrases):
                if any(p in src for p in prefer):
                    delta += 0.22
                if any(a in src for a in avoid):
                    delta -= 0.28
        for phrases, prefer, avoid in _DIEM_SPECIAL_FILE_HINTS:
            if any(p in q for p in phrases):
                if any(p in src for p in prefer):
                    delta += 0.38
                if any(a in src for a in avoid):
                    delta -= 0.32
        mssv = extract_mssv(query)
        if mssv and mssv in txt.upper():
            delta += 0.55
        if _is_english_classification_query(query):
            if "08_ket_qua_thi_anh_van" in src or "ket_qua_thi_anh" in src:
                delta += 0.45
            if src.startswith("hk") or "_hk" in src or "hk1" in src or "hk2" in src:
                delta -= 0.35
    if agent_id == "tuyen_sinh":
        if any(m in q for m in ("điểm chuẩn", "diem chuan", "trúng tuyển", "trung tuyen", "chỉ tiêu")):
            if "02_de_an_tuyen_sinh_2024" in src and "2024" in q:
                delta += 0.35
            if "01_de_an_tuyen_sinh_2025" in src:
                delta += 0.12
            if "23_chuong_trinh_dao_tao_cntt" in src and any(m in q for m in ("cdio", "kmc", "chương trình")):
                delta += 0.30
    if agent_id == "bieu_mau" and "thu_tuc_nhap_hoc" in src:
        if any(m in q for m in ("nhập học", "nhap hoc", "thủ tục", "giấy tờ", "phí", "tiền")):
            delta += 0.35
    if agent_id == "khao_thi":
        if "25_quy_che_dao_tao" in src and "120" in q:
            delta += 0.30
        if "03_quy_dinh_chuan_ngoai_ngu" in src and any(m in q for m in ("toeic", "tiếng anh", "ngoại ngữ")):
            delta += 0.25
    if agent_id == "ma_tran" and "13_ma_tran_de_thi_tin_hoc" in src:
        if any(m in q for m in ("tin học", "tin hoc", "thời gian", "bao nhiêu câu")):
            delta += 0.35
    if agent_id == "danh_sach_thi":
        if any(m in q for m in ("danh sách", "danh sach", "phòng", "phong", "ca thi", "buổi")):
            if "danh-sach-thi" in src or "danh_sach_thi" in src:
                delta += 0.25
        mssv = extract_mssv(query)
        if mssv and mssv in txt.upper():
            delta += 0.50
    if agent_id == "lich_thi":
        if any(m in q for m in ("học kỳ 1", "hoc ky 1", "hk1", "ki1")) and "ki1" in src:
            delta += 0.28
        if any(m in q for m in ("học kỳ 2", "hoc ky 2", "hk2", "ki2")) and "ki2" in src:
            delta += 0.28
        if any(m in q for m in ("thi lại", "thi lai", "lần 2", "lan 2", "lan2", "học lại", "hoc lai", "thi lần 2")):
            if "lan2" in src:
                delta += 0.45
            else:
                delta -= 0.20
        if "đợt 1" in q or "dot 1" in q:
            if "dot1" in src or "_dot1" in src:
                delta += 0.22
            if ("đợt 2" in q or "dot 2" in q) and ("dot2" in src or "_dot2" in src):
                delta -= 0.35
        if "đợt 2" in q or "dot 2" in q:
            if "dot2" in src or "_dot2" in src:
                delta += 0.55
            elif "dot1" in src or "_dot1" in src:
                delta -= 0.30
        if any(m in q for m in ("học kỳ 1", "hoc ky 1", "hk1")) and "ki1" in src:
            delta += 0.25
        if "2023" in q and "2024" in q and "20232024" in src:
            delta += 0.35
        if "2025" in q and "20252026" in src:
            delta += 0.18
        if "2024" in q and "20242025" in src:
            delta += 0.18
    return delta


def _text_search_terms(query: str, agent_id: str) -> list[str]:
    """Từ khóa tra cứu text index Qdrant — bổ sung embedding khi hỏi số liệu/bảng."""
    q = query.lower()
    terms: list[str] = []
    if agent_id == "tuyen_sinh":
        if any(m in q for m in ("điểm chuẩn", "diem chuan", "trúng tuyển", "trung tuyen", "chủ tiêu", "so sánh", "so sanh")):
            terms.append("02_de_an_tuyen_sinh_2024")
            terms.append("01_de_an_tuyen_sinh_2025")
            if "2024" in q:
                if "công nghệ thông tin" in q or "cntt" in q:
                    terms.extend(["26.20", "26.60"])
                if "an toàn" in q or "attt" in q:
                    terms.extend(["25.90", "25.60"])
                if "điện tử" in q or "dtvt" in q:
                    terms.extend(["25.0", "25.35"])
            if "an toàn" in q or "attt" in q:
                terms.append("An toàn thông tin")
            if "công nghệ thông tin" in q or "cntt" in q:
                terms.append("Công nghệ thông tin")
            if "điện tử" in q or "dtvt" in q:
                terms.append("7520207")
        if any(m in q for m in ("cdio", "kmc", "mã chương trình", "chuong trinh cntt")):
            terms.extend(["KMC.1.1.1", "CDIO", "23_chuong_trinh_dao_tao_cntt"])
    elif agent_id == "bieu_mau":
        if any(m in q for m in (
            "nghỉ học", "nghi hoc", "đơn nghỉ", "don nghi", "xin nghỉ",
            "dưới 7", "duoi 7", "trên 7", "tren 7", "7 ngày", "7 ngay",
            "khác nhau", "khac nhau", "so sánh", "so sanh",
        )):
            terms.extend([
                "08-Don_nghi_hoc_duoi_7", "09-Don_nghi_hoc_tren_7",
                "08-Don", "09-Don", "nghỉ học tạm thời",
            ])
        if any(m in q for m in ("nhập học", "nhap hoc", "thủ tục", "giấy tờ", "giay to", "phí", "tiền", "catalog", "biểu mẫu", "bhy")):
            terms.extend(["Thu_tuc_nhap_hoc_2024", "10.896", "896.940", "Giấy báo trúng tuyển", "học bạ", "CCCD"])
            if "bhy" in q:
                terms.extend(["24-Mau_khai_BHYT", "25-Huong_dan_khai_BHYT"])
    elif agent_id == "khao_thi":
        if "120" in q or ("tín chỉ" in q and any(m in q for m in ("tối thiểu", "cử nhân", "quy chế"))):
            terms.append("120 tín")
        if any(m in q for m in ("toeic", "tiếng anh", "ta1", "ta2", "ta3", "đồ án", "do an", "de tai do an", "vstep")):
            terms.extend(["TOEIC", "450", "350", "300", "03_quy_dinh_chuan_ngoai_ngu"])
        if "không áp dụng" in q or ("ngoại ngữ" in q and "đối tượng" in q):
            terms.extend(["tài năng", "chất lượng cao"])
    elif agent_id == "diem_thi":
        if _is_english_classification_query(q):
            terms.extend(["08_ket_qua_thi_anh_van", "PHÂN LOẠI", "ĐẠT", "KHÔNG ĐẠT"])
        if any(m in q for m in ("ct4", "tốt nghiệp", "tot nghiep")):
            terms.append("04_ket_qua_tot_nghiep_ct4")
        if any(m in q for m in ("chứng chỉ", "chung chi", "nhan chung", "nhận chứng")):
            terms.append("12_ds_nhan_chung_chi_ta")
        for mssv in extract_all_mssv(query):
            terms.append(mssv)
    elif agent_id == "ma_tran":
        if any(m in q for m in ("tin học", "tin hoc", "thời gian", "bao nhiêu câu", "ma trận")):
            terms.extend(["13_ma_tran_de_thi_tin_hoc", "60 phút", "50 câu", "Thời gian làm bài"])
    elif agent_id == "danh_sach_thi":
        if any(m in q for m in ("danh sách", "danh sach", "phòng", "phong", "ca thi")):
            terms.extend(["danh-sach-thi", "phòng thi", "ca thi"])
        mssv = extract_mssv(query)
        if mssv:
            terms.append(mssv.upper())
    elif agent_id == "lich_thi":
        if any(m in q for m in ("lịch thi", "lich thi", "kthp", "học kỳ", "hoc ky")):
            terms.extend(["kthp", "lịch thi"])
        if any(m in q for m in ("thi lại", "thi lai", "lần 2", "lan 2", "lan2", "học lại", "hoc lai", "thi lần 2")):
            terms.append("lan2")
        if "đợt 1" in q or "dot 1" in q:
            terms.append("dot1")
        if "đợt 2" in q or "dot 2" in q:
            terms.append("dot2")
            if any(m in q for m in ("học kỳ 1", "hoc ky 1", "hk1", "ki1")):
                terms.append("kthp_ki1_20232024_dot2")
        if "2025" in q and "2026" in q:
            terms.append("20252026")
        if "2024" in q and "2025" in q:
            terms.append("20242025")
    out: list[str] = []
    for t in terms:
        if t not in out:
            out.append(t)
    return out[:8]


def top_retrieval_confidence(docs: list[dict]) -> float:
    if not docs:
        return 0.0
    return max(float(d.get("_rank_score", d.get("score", 0.0))) for d in docs)


def rerank_documents(query: str, docs: list[dict], agent_id: str | None = None) -> list[dict]:
    if not docs:
        return docs
    for d in docs:
        d["_rank_score"] = d["score"] + _keyword_adjust(query, d, agent_id)
    ranked = sorted(docs, key=lambda x: x["_rank_score"], reverse=True)
    if not ranked:
        return ranked

    best = ranked[0]["_rank_score"]
    # Loại chunk lệch môn khi điểm hạ quá xa chunk tốt nhất
    filtered = [d for d in ranked if d["_rank_score"] >= best - 0.28]

    # Lịch thi / danh sách thi: luôn giữ mọi chunk thuộc cùng file tốt nhất
    if agent_id in ("lich_thi", "danh_sach_thi"):
        top_src = (ranked[0].get("source") or "").strip()
        if top_src:
            extra = [d for d in ranked if (d.get("source") or "").strip() == top_src]
            # Gộp, bỏ trùng (page + đoạn text đầu)
            seen: set[tuple] = set()
            merged: list[dict] = []
            for d in filtered + extra:
                key = (d.get("source"), d.get("page"), (d.get("text") or "")[:80])
                if key in seen:
                    continue
                seen.add(key)
                merged.append(d)
            return merged

    return filtered


def top_sources_for_display(docs: list[dict], limit: int = 3) -> list[dict]:
    """Tối đa `limit` file PDF/distinct source cho UI tải về."""
    best_per_source: dict[str, dict] = {}
    for d in docs:
        src = d.get("source", "")
        if not src:
            continue
        prev = best_per_source.get(src)
        score = d.get("_rank_score", d.get("score", 0))
        if not prev or score > prev.get("_rank_score", prev.get("score", 0)):
            best_per_source[src] = d
    ordered = sorted(
        best_per_source.values(),
        key=lambda x: x.get("_rank_score", x.get("score", 0)),
        reverse=True,
    )
    return ordered[:limit]


def _payload_to_doc(hit, score: float | None = None) -> dict:
    p = hit.payload
    sc = score if score is not None else getattr(hit, "score", 0.0) or 0.0
    role = (p.get("chunk_role") or "flat").strip().lower()
    parent_text = (p.get("parent_text") or "").strip()
    child_text = (p.get("text") or "").strip()
    return {
        "text":            child_text or parent_text,
        "child_text":      child_text,
        "parent_text":     parent_text,
        "parent_id":       p.get("parent_id") or "",
        "child_index":     int(p.get("child_index", -1)),
        "chunk_role":      role,
        "source":          p.get("source", ""),
        "page":            p.get("page", 0),
        "score":           round(float(sc), 4),
        "agent_id":        p.get("agent_id", ""),
        "display_name":    p.get("display_name", ""),
        "download_url":    p.get("download_url", ""),
        "category":        p.get("category", ""),
        "document_type":   p.get("document_type") or "prose",
        "section":         p.get("section") or "",
        "table_headers":   p.get("table_headers") or "[]",
        "row_count":       int(p.get("row_count") or 0),
        "table_index":     int(p.get("table_index", -1)),
    }


def _doc_key(d: dict) -> tuple:
    pid = (d.get("parent_id") or "").strip()
    if pid:
        return ("parent", pid)
    return (d.get("source"), d.get("page"), (d.get("text") or "")[:120])


def _merge_docs(primary: list[dict], extra: list[dict]) -> list[dict]:
    seen = {_doc_key(d) for d in primary}
    out = list(primary)
    for d in extra:
        k = _doc_key(d)
        if k not in seen:
            seen.add(k)
            out.append(d)
    return out


def ensure_text_index(client: QdrantClient) -> None:
    global _TEXT_INDEX_READY
    if _TEXT_INDEX_READY:
        return
    try:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="text",
            field_schema=TextIndexParams(
                type="text",
                tokenizer=TokenizerType.WORD,
                min_token_len=2,
                max_token_len=30,
                lowercase=True,
            ),
        )
        log.info("[retrieval] text index on payload 'text' ready")
    except Exception as e:
        log.warning(f"[retrieval] text index: {e}")
    _TEXT_INDEX_READY = True


def build_agent_filter(agent_id: str | None) -> Filter | None:
    if not agent_id:
        return None
    return Filter(
        must=[FieldCondition(key="agent_id", match=MatchValue(value=agent_id))]
    )


class QdrantRetriever:
    def __init__(self):
        self._embed = embed_client()
        self.qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        ensure_text_index(self.qdrant)

    def _collect_mssv_points(
        self,
        mssv: str,
        *,
        scroll_filter: Filter | None,
        limit: int,
    ) -> list[dict]:
        mssv_u = mssv.upper()
        found: list[dict] = []
        seen: set[tuple] = set()
        offset = None
        batch = 120

        while len(found) < limit:
            pts, offset = self.qdrant.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=scroll_filter,
                limit=batch,
                offset=offset,
                with_payload=True,
            )
            for p in pts:
                text = p.payload.get("text") or ""
                if mssv_u not in text.upper():
                    continue
                key = (p.payload.get("source"), p.payload.get("page"), text[:100])
                if key in seen:
                    continue
                seen.add(key)
                found.append(_payload_to_doc(p, score=0.95))
                if len(found) >= limit:
                    break
            if offset is None or len(found) >= limit:
                break
        return found

    def _lookup_mssv_chunks(self, mssv: str, agent_id: str, limit: int = 10) -> list[dict]:
        """Tìm chunk chứa MSSV trong bảng điểm (không dựa embedding)."""
        mssv = mssv.upper()
        flt = Filter(must=[
            FieldCondition(key="agent_id", match=MatchValue(value=agent_id)),
            FieldCondition(key="text", match=MatchText(text=mssv)),
        ])
        try:
            docs = self._collect_mssv_points(mssv, scroll_filter=flt, limit=limit)
            if docs:
                log.info(f"[retrieval] MSSV {mssv} → {len(docs)} chunk(s) via text index")
                return docs
        except Exception as e:
            log.warning(f"[retrieval] MSSV text index: {e}, scroll fallback")

        base = build_agent_filter(agent_id)
        docs = self._collect_mssv_points(mssv, scroll_filter=base, limit=limit)
        if docs:
            log.info(f"[retrieval] MSSV {mssv} → {len(docs)} chunk(s) scroll")
        return docs

    def lookup_mssv_grade_docs(
        self,
        query: str,
        *,
        agent_id: str = "diem_thi",
        student_name: str | None = None,
        chunk_limit: int | None = None,
    ) -> list[dict]:
        """Gom mọi chunk bảng điểm có MSSV; ưu tiên đúng file học kỳ (gợi ý trong câu hỏi)."""
        from config import GRADE_LOOKUP_CHUNK_LIMIT

        mssv_list = extract_all_mssv(query)
        if not mssv_list:
            return []
        cap = chunk_limit or GRADE_LOOKUP_CHUNK_LIMIT
        per_mssv_cap = max(8, cap // len(mssv_list))

        docs: list[dict] = []
        for mssv in mssv_list:
            mdocs = self._lookup_mssv_chunks(mssv, agent_id, limit=per_mssv_cap)
            docs = _merge_docs(docs, mdocs)

        text_hits = self._collect_text_search_docs(query, agent_id, limit=12)
        if text_hits:
            docs = _merge_docs(text_hits, docs)
            log.info(f"[retrieval] grade lookup text-index: +{len(text_hits)} chunk(s)")

        if not docs:
            return []

        if not _is_english_classification_query(query):
            docs = filter_docs_by_diem_period(query, docs)

        if student_name:
            filtered = [d for d in docs if name_matches_text(student_name, d.get("text", ""))]
            if filtered:
                docs = filtered
            else:
                log.warning(
                    f"[retrieval] MSSV {mssv_list}: không chunk nào khớp tên {student_name!r}, "
                    "dùng mọi chunk có MSSV"
                )

        if _is_english_classification_query(query):
            special = [
                d for d in docs
                if "08_ket_qua_thi_anh_van" in (d.get("source") or "").lower()
                or "ket_qua_thi_anh" in (d.get("source") or "").lower()
            ]
            if special:
                docs = special
                log.info(
                    "[retrieval] English classification query → %s chunk(s) from 08_ket_qua",
                    len(docs),
                )

        by_source: dict[str, list[dict]] = {}
        for d in docs:
            by_source.setdefault(d.get("source", ""), []).append(d)

        ranked: list[tuple[float, str, list[dict]]] = []
        for src, chunks in by_source.items():
            if not src:
                continue
            adj = max(_keyword_adjust(query, c, agent_id) for c in chunks)
            ranked.append((adj + 0.05 * len(chunks), src, chunks))
        ranked.sort(key=lambda x: -x[0])

        if not ranked:
            return docs[:cap]

        if len(ranked) == 1:
            _s, _src, chunks = ranked[0]
            chunks.sort(key=lambda c: (c.get("page", 0), c.get("text", "")[:60]))
            chosen = chunks if len(chunks) <= cap else rerank_documents(query, chunks, agent_id)
            log.info(
                f"[retrieval] grade lookup {mssv_list}: {len(chosen)} chunk(s) — single file {_src!r}"
            )
            return chosen[:cap]

        best_score = ranked[0][0]
        chosen: list[dict] = []
        for score, _src, chunks in ranked:
            if score < best_score - 0.15 and chosen:
                break
            chunks.sort(key=lambda c: (c.get("page", 0), c.get("text", "")[:60]))
            chosen.extend(chunks)

        chosen = rerank_documents(query, chosen, agent_id)
        log.info(
            f"[retrieval] grade lookup {mssv_list}: {len(chosen)} chunk(s) "
            f"from {len({d['source'] for d in chosen})} file(s)"
        )
        return chosen[:cap]

    def embed(self, text: str) -> list[float]:
        resp = self._embed.embeddings.create(input=text, model=EMBED_MODEL)
        return resp.data[0].embedding

    def _collect_text_search_docs(
        self,
        query: str,
        agent_id: str,
        limit: int = 10,
    ) -> list[dict]:
        terms = _text_search_terms(query, agent_id)
        if not terms:
            return []
        found: list[dict] = []
        seen: set[tuple] = set()
        for term in terms:
            flt = Filter(must=[
                FieldCondition(key="agent_id", match=MatchValue(value=agent_id)),
                FieldCondition(key="text", match=MatchText(text=term)),
            ])
            try:
                pts, _ = self.qdrant.scroll(
                    collection_name=COLLECTION_NAME,
                    scroll_filter=flt,
                    limit=4,
                    with_payload=True,
                )
                for p in pts:
                    key = (
                        p.payload.get("source"),
                        p.payload.get("page"),
                        (p.payload.get("text") or "")[:80],
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    found.append(_payload_to_doc(p, score=0.88))
                    if len(found) >= limit:
                        return found
            except Exception as e:
                log.debug(f"[retrieval] text search {term!r}: {e}")
        return found

    def retrieve(
        self,
        query: str,
        *,
        agent_id: str | None = None,
        top_k: int = TOP_K,
    ) -> tuple[list[dict], float]:
        t0 = time.perf_counter()
        mssv = extract_mssv(query)
        parent_child = uses_parent_child_retrieval(agent_id)
        if parent_child:
            k = min(top_k * PARENT_SEARCH_POOL_MULTIPLIER, 64)
        else:
            k = top_k + (8 if mssv and agent_id == "diem_thi" else 0)

        vec = self.embed(query)
        qfilter = build_agent_filter(agent_id)

        kwargs: dict = {
            "collection_name": COLLECTION_NAME,
            "query": vec,
            "limit": k,
            "with_payload": True,
        }
        if qfilter is not None:
            kwargs["query_filter"] = qfilter

        result = self.qdrant.query_points(**kwargs)
        docs = [_payload_to_doc(h) for h in result.points]

        if not docs and agent_id:
            log.warning(
                f"[retrieval] 0 hits for agent_id={agent_id!r}, "
                "fallback unfiltered (re-run ingest_all.py)"
            )
            result = self.qdrant.query_points(
                collection_name=COLLECTION_NAME,
                query=vec,
                limit=k,
                with_payload=True,
            )
            docs = [_payload_to_doc(h) for h in result.points]

        if mssv and agent_id == "diem_thi":
            extra = self._lookup_mssv_chunks(mssv, agent_id, limit=24)
            docs = _merge_docs(extra, docs)

        if agent_id:
            text_hits = self._collect_text_search_docs(query, agent_id, limit=12)
            if text_hits:
                docs = _merge_docs(text_hits, docs)
                log.info(f"[retrieval] text-index boost {agent_id}: +{len(text_hits)} chunk(s)")

        docs = rerank_documents(query, docs, agent_id)

        if parent_child:
            if ACCURACY_MODE and docs:
                best = top_retrieval_confidence(docs)
                docs = [
                    d for d in docs
                    if d.get("_rank_score", d.get("score", 0)) >= best - 0.22
                ]
            docs = collapse_child_hits_to_parents(
                docs,
                max_parents=min(top_k, PARENT_RETRIEVE_MAX),
            )
        elif ACCURACY_MODE and agent_id and len(docs) > top_k:
            best = top_retrieval_confidence(docs)
            docs = [
                d for d in docs
                if d.get("_rank_score", d.get("score", 0)) >= best - 0.22
            ]
            docs = docs[:top_k]
        else:
            docs = docs[:top_k]

        return docs, round(time.perf_counter() - t0, 3)
