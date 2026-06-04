"""
Tính Qc cục bộ (không LLM): Qc = w1·E + w2·R + w3·L + w4·S
Theo thực nghiệm report_final: w1=0.150, w2=0.376, w3=0.089, w4=0.386
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from functools import lru_cache

from config import (
    QC_FALLBACK,
    QC_WEIGHT_E,
    QC_WEIGHT_L,
    QC_WEIGHT_R,
    QC_WEIGHT_S,
)
from agents.routing_intel import (
    ComplexityAssessment,
    INTENT_COMPARE,
    INTENT_FACTUAL,
    INTENT_GRADE_LOOKUP,
    INTENT_LIST,
    INTENT_MULTI_HOP,
    INTENT_PROCEDURAL,
)

log = logging.getLogger(__name__)

# ── KMA entity hints (bổ sung spaCy NER) ─────────────────────────────────────
_KMA_ENTITY_TERMS = (
    "kma", "học viện", "hoc vien", "mssv", "at20", "ctđt", "ctdt",
    "tuyển sinh", "khảo thí", "khao thi", "quy chế", "ma trận",
    "biểu mẫu", "bảng điểm", "phúc khảo", "bảo lưu", "attt", "cntt", "dtvt",
    "phòng đào tạo", "phòng khảo thí", "học kỳ", "đợt thi",
)

_RELATION_KEYWORDS = (
    " hoặc ", " hoặc là ", " nếu ", " thì ", " khi ", " so sánh ",
    " khác nhau ", " giống ", " hơn ", " ít hơn ", " bằng ", " hay ",
    " đồng thời ", " cùng lúc ", " nhưng ", " tuy ", " vì ",
    " quy trình ", " các bước ", " thủ tục ", " điều kiện ",
)

_RELATION_DEPS = frozenset({"conj", "advcl", "ccomp", "xcomp", "relcl"})

_GRADE_MARKERS = ("điểm", "diem", "bảng điểm", "bang diem", "mssv", "at20", "học kỳ", "hoc ky")
_COMPLEX_MARKERS = (
    " so sánh ", " khác nhau ", " đồng thời ", " tại sao ", " giải thích ",
    " liệt kê ", " các bước ", " quy trình đầy đủ ", " tổng hợp ", " phân tích ",
)

_ADMISSION_QC_MARKERS = ("điểm chuẩn", "diem chuan", "ngưỡng", "trúng tuyển", "chỉ tiêu")

_TOKEN_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)
_MSSV_RE = re.compile(r"\b(?:AT|CT|DT)\d{6}\b", re.IGNORECASE)


def _normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFC", s)
    return f" {s} "


def _cap01(value: float, cap: float = 1.0) -> float:
    return max(0.0, min(cap, float(value)))


def _component_e(question: str, nlp=None) -> float:
    """Entities: spaCy NER + KMA keywords, cap 3 → 1.0"""
    q = question.strip()
    if not q:
        return 0.0

    entities: set[str] = set()
    low = _normalize_text(q)

    for term in _KMA_ENTITY_TERMS:
        if term in low:
            entities.add(term)

    m = _MSSV_RE.search(q)
    if m:
        entities.add(m.group(0).upper())

    if nlp is not None:
        try:
            doc = nlp(q[:2000])
            for ent in doc.ents:
                if ent.label_ in ("PERSON", "ORG", "GPE", "LOC", "FAC", "PRODUCT", "EVENT"):
                    entities.add(ent.text.lower()[:80])
            for tok in doc:
                if tok.pos_ in ("PROPN",) and len(tok.text) > 1:
                    entities.add(tok.text.lower())
        except Exception as e:
            log.debug("[qc] NER skip: %s", e)

    count = len(entities)
    return _cap01(count / 3.0)


def _component_r(question: str, nlp=None) -> float:
    """Relations: từ khóa logic + dependency tags, cap 3 → 1.0"""
    low = _normalize_text(question)
    hits: set[str] = set()

    for kw in _RELATION_KEYWORDS:
        if kw in low:
            hits.add(kw.strip())

    if nlp is not None:
        try:
            doc = nlp(question[:2000])
            for tok in doc:
                if tok.dep_ in _RELATION_DEPS:
                    hits.add(tok.dep_)
            for ch in doc.noun_chunks:
                if any(t.dep_ in _RELATION_DEPS for t in ch):
                    hits.add("chunk_rel")
        except Exception as e:
            log.debug("[qc] deps skip: %s", e)

    return _cap01(len(hits) / 3.0)


def _component_l(question: str) -> float:
    """Length: token (không dấu câu) / 30"""
    tokens = _TOKEN_RE.findall(question)
    return _cap01(len(tokens) / 30.0)


def _softmax(values: list[float]) -> list[float]:
    if not values:
        return []
    m = max(values)
    exps = [math.exp(v - m) for v in values]
    s = sum(exps) or 1.0
    return [e / s for e in exps]


def _shannon_entropy(probs: list[float]) -> float:
    h = 0.0
    for p in probs:
        if p > 1e-12:
            h -= p * math.log(p)
    return h


def _component_s(similarity_scores: list[float] | None) -> float:
    """
    Ambiguity: softmax(similarities) → Shannon entropy, chuẩn hóa [0,1].
    Entropy tối đa khi phân phối đều (log n).
    """
    if not similarity_scores:
        return 0.0
    scores = [float(s) for s in similarity_scores[:20]]
    if len(scores) < 2:
        return 0.0
    probs = _softmax(scores)
    n = len(probs)
    h = _shannon_entropy(probs)
    h_max = math.log(n) if n > 1 else 1.0
    return _cap01(h / h_max) if h_max > 0 else 0.0


@lru_cache(maxsize=1)
def _load_spacy():
    try:
        import spacy
    except ImportError:
        log.warning("[qc] spacy not installed — E/R use keywords only")
        return None
    for model in ("vi_core_news_lg", "vi_core_news_sm", "en_core_web_sm"):
        try:
            nlp = spacy.load(model)
            log.info("[qc] spaCy model loaded: %s", model)
            return nlp
        except OSError:
            continue
    log.warning("[qc] no spaCy model found — pip install spacy && python -m spacy download en_core_web_sm")
    return None


def compute_qc_components(
    question: str,
    similarity_scores: list[float] | None = None,
) -> tuple[float, dict[str, float]]:
    """
    Trả (Qc, breakdown dict E/R/L/S).
    """
    nlp = _load_spacy()
    e = _component_e(question, nlp)
    r = _component_r(question, nlp)
    l = _component_l(question)
    s = _component_s(similarity_scores)

    qc = (
        QC_WEIGHT_E * e
        + QC_WEIGHT_R * r
        + QC_WEIGHT_L * l
        + QC_WEIGHT_S * s
    )
    qc = round(_cap01(qc), 3)
    return qc, {"E": round(e, 3), "R": round(r, 3), "L": round(l, 3), "S": round(s, 3)}


def _infer_intent(question: str, qc: float) -> tuple[str, bool, str]:
    q = question.strip()
    low = _normalize_text(q)
    words = len(q.split())
    n_q = q.count("?")

    if any(m in low for m in _ADMISSION_QC_MARKERS):
        intent = INTENT_FACTUAL
        multi = False
    elif any(m in low for m in _GRADE_MARKERS) or _MSSV_RE.search(q):
        intent = INTENT_GRADE_LOOKUP
        multi = True
    elif any(m in low for m in _COMPLEX_MARKERS):
        if " so sánh " in low or " khác nhau " in low:
            intent = INTENT_COMPARE
        elif " các bước " in low or " quy trình " in low:
            intent = INTENT_PROCEDURAL
        elif " liệt kê " in low:
            intent = INTENT_LIST
        else:
            intent = INTENT_MULTI_HOP
        multi = True
    elif words <= 14 and n_q <= 1:
        intent = INTENT_FACTUAL
        multi = False
    elif " liệt kê " in low or " những " in low:
        intent = INTENT_LIST
        multi = True
    else:
        intent = INTENT_FACTUAL if qc < 0.45 else INTENT_MULTI_HOP
        multi = qc >= 0.5

    score_0_10 = max(0, min(10, int(round(qc * 10))))
    reason = (
        f"Qc cục bộ={qc:.3f} (E/R/L/S); intent={intent}."
    )
    return intent, multi, reason, score_0_10


def calculate_qc(
    question: str,
    similarity_scores: list[float] | None = None,
) -> float:
    """API đơn giản — chỉ trả Qc; lỗi → QC_FALLBACK."""
    try:
        qc, _ = compute_qc_components(question, similarity_scores)
        return qc
    except Exception as e:
        log.warning("[qc] calculate_qc failed: %s", e)
        return QC_FALLBACK


def assess_complexity_local(
    question: str,
    similarity_scores: list[float] | None = None,
) -> ComplexityAssessment:
    """Thay thế LLM estimator khi USE_LOCAL_QC=1."""
    question = (question or "").strip()
    if not question:
        return ComplexityAssessment(0.0, 0, INTENT_FACTUAL, False, "Câu rỗng.")

    try:
        qc, breakdown = compute_qc_components(question, similarity_scores)
        intent, multi, reason, score = _infer_intent(question, qc)
        reason = f"{reason} [{breakdown}]"
        log.info("[qc:local] qc=%s breakdown=%s intent=%s", qc, breakdown, intent)
        return ComplexityAssessment(
            qc=qc,
            score_0_10=score,
            intent=intent,
            needs_multi_doc=multi,
            reason=reason,
        )
    except Exception as e:
        log.warning("[qc:local] fallback %.2f: %s", QC_FALLBACK, e)
        fb = QC_FALLBACK
        return ComplexityAssessment(
            qc=fb,
            score_0_10=int(round(fb * 10)),
            intent=INTENT_FACTUAL,
            needs_multi_doc=False,
            reason=f"Fallback an toàn ({QC_FALLBACK}): {e}",
        )
