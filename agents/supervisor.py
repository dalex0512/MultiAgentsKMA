"""
Supervisor Agent — điều phối Multi-Agent: chọn specialist agent(s) theo intent.
Có memory: history hội thoại + tóm tắt phiên.
"""

import hashlib
import json
import logging
import re
import time as time_mod
from dataclasses import dataclass

from openai import OpenAI
from config import (
    LLM_MODEL,
    OPENAI_API_KEY,
    AGENTS,
    AGENT_IDS,
    ACCURACY_MODE,
    SUPERVISOR_FAST_PATH,
    SUPERVISOR_LOW_CONFIDENCE,
)
from admin_auth.services.agent_availability import active_agent_ids, filter_enabled_agents
from agents.conversation_context import format_history_text, history_for_supervisor
from agents.routing_intel import (
    SUP_INTENT_FORM,
    SUP_INTENT_GRADE,
    SUP_INTENT_MULTI,
)

log = logging.getLogger(__name__)

openai_client = OpenAI(api_key=OPENAI_API_KEY)

_MSSV_RE = re.compile(r"\b(?:AT|CT)\d{6}\b", re.IGNORECASE)
_SBD_RE = re.compile(r"(?:\bsbd\b|số báo danh|so bao danh)\s*[:#]?\s*(\d{1,5})", re.IGNORECASE)

# Điểm chuẩn / tuyển sinh — không fast-path sang diem_thi
_ADMISSION_MARKERS = (
    "điểm chuẩn",
    "diem chuan",
    "ngưỡng",
    "nguong",
    "trúng tuyển",
    "trung tuyen",
    "chỉ tiêu",
    "chi tieu",
    "tuyển sinh",
    "tuyen sinh",
    "nhập học",
    "nhap hoc",
    "ctđt",
    "ctdt",
    "đề án tuyển",
)

# Fast-path biểu mẫu (cần marker mạnh, không chỉ "đơn")
_FORM_STRONG_MARKERS = (
    "biểu mẫu",
    "bieu mau",
    "mẫu đơn",
    "mau don",
    "tải đơn",
    "tai don",
    "phúc khảo",
    "phuc khao",
    "nghỉ học",
    "nghi hoc",
    "bảo lưu",
    "bao luu",
    "thực tập",
    "thuc tap",
)

_MA_TRAN_STRONG = (
    "ma trận",
    "ma tran",
    "cấu trúc đề",
    "cau truc de",
)

_DANH_SACH_THI_MARKERS = (
    "danh sách thi",
    "danh sach thi",
    "danh sach",
    "phòng thi",
    "phong thi",
    "ca thi",
    "ca sáng",
    "ca sang",
    "ca chiều",
    "ca chieu",
    "buổi sáng",
    "buoi sang",
    "buổi chiều",
    "buoi chieu",
    "số báo danh",
    "so bao danh",
    "danh sách dự thi",
    "danh sach du thi",
)

_LICH_THI_MARKERS = (
    "lịch thi",
    "lich thi",
    "kthp",
    "kỳ thi học phần",
    "ky thi hoc phan",
    "thi kết thúc học phần",
    "thi ket thuc hoc phan",
    "lịch kthp",
    "lich kthp",
    "thi học phần",
    "thi hoc phan",
    "địa điểm thi",
    "dia diem thi",
    "địa điểm",
    "dia diem",
    "kì 1",
    "kì 2",
    "ki 1",
    "ki 2",
    "hk1",
    "hk2",
    "đợt1",
    "đợt2",
    "dot1",
    "dot2",
    "thi lại",
    "thi lai",
    "lịch thi lại",
    "lich thi lai",
    "lần 2",
    "lan 2",
    "học lại",
    "hoc lai",
    "thi lần 2",
)

_FEE_MARKERS = (
    "phí nhập", "phi nhap", "số tiền phải nộp", "so tien phai nop",
    "tổng số tiền", "tong so tien", "tổng tiền", "tong tien",
    "thủ tục nhập học", "thu tuc nhap hoc", "hướng dẫn nhập học", "huong dan nhap hoc",
    "lệ phí", "le phi", "học phí", "hoc phi", "tiền mặt", "tien mat",
    "10896940", "10.896",
)

_GRADE_CONTEXT_MARKERS = (
    "điểm", "diem", "bảng điểm", "bang diem", "kết quả", "ket qua",
    "học kỳ", "hoc ky", "đạt", "dat", "không đạt", "khong dat",
    "phân loại", "phan loai", "tiếng anh", "tieng anh", "chứng chỉ", "chung chi",
)

_SCHEDULE_SUBJECT_MARKERS = (
    "môn", "mon", "học kỳ", "hoc ky", "kì", "ki ", "đợt", "dot",
    "thi kết thúc học phần", "thi ket thuc hoc phan",
    "địa điểm thi", "dia diem thi", "giờ thi", "gio thi",
    "thời gian thi", "thoi gian thi", "thời gian bắt đầu", "thoi gian bat dau",
    "bắt đầu thi", "bat dau thi", "khi nào thi", "khi nao thi",
)

_AGENT_LIST_TEXT = "\n".join(
    f'- "{aid}": {cfg["name"]} — {cfg["description"]}'
    for aid, cfg in AGENTS.items()
)

SUPERVISOR_PROMPT = """\
Bạn là Supervisor — lớp điều phối đa tác tử (Multi-Agent Orchestrator) của chatbot Học viện KMA.
Nhiệm vụ: phân loại ý định sinh viên và chọn agent chuyên môn (không trả lời câu hỏi).

## Các agent (corpus Qdrant riêng)
{agent_list}

## Intent nghiệp vụ (chọn một)
- single_domain: một mảng (tuyển sinh HOẶC khảo thí HOẶC ma trận HOẶC điểm HOẶC biểu mẫu HOẶC danh sách thi HOẶC lịch thi).
- multi_domain: hai mảng trở lên (vd. tuyển sinh + biểu mẫu nhập học).
- form_procedure: đơn từ, mẫu đơn, tải biểu mẫu, điền đơn, thủ tục hành chính.
- grade_result: điểm, bảng điểm, kết quả thi, MSSV, học kỳ, chứng chỉ công bố.

## Quy tắc chọn agent
- form_procedure → agents phải có "bieu_mau" (primary thường là bieu_mau).
- grade_result / tra điểm theo MSSV (ATxxxxxx, CTxxxxxx) → chỉ "diem_thi" (không gọi khao_thi trừ khi hỏi rõ quy chế/thang điểm chung).
- Tuyển sinh, CTĐT, đề án, điểm chuẩn, ngưỡng trúng tuyển → "tuyen_sinh" (KHÔNG dùng diem_thi cho điểm chuẩn).
- Quy chế, chuẩn đầu ra, thi tốt nghiệp, TOEIC/VSTEP → "khao_thi".
- Ma trận đề, cấu trúc đề thi, môn thi → "ma_tran".
- Danh sách thi theo ngày/ca/phòng, sinh viên trong bảng danh sách dự thi → "danh_sach_thi" (KHÔNG dùng diem_thi trừ khi hỏi điểm/kết quả).
- Lịch thi KTHP, học kỳ, đợt, ngày giờ thi môn học phần → "lich_thi" (KHÔNG nhầm với quy chế khao_thi).
- Câu follow-up (đại từ "đó", "bạn ấy"): đọc HỘI THOẠI để giữ đúng agent/mảng.
- Tối đa 3 agent; primary = agent trả lời chính.

## Ví dụ
Q: "Điểm chuẩn CNTT 2024 và mẫu đơn nhập học?"
→ intent multi_domain, agents ["tuyen_sinh","bieu_mau"], primary "tuyen_sinh"

Q: "Sinh viên AT200201 đạt TA đầu vào chưa?"
→ intent grade_result, agents ["diem_thi"], primary "diem_thi"

Q: "CT060310 điểm học kỳ 2 2024-2025 đợt 1"
→ intent grade_result, agents ["diem_thi"], primary "diem_thi" (CT060310 là MSSV, không phải mã học phần)

Q: "MSSV AT200201 thi phòng nào ngày 21/4/2026 buổi sáng?"
→ intent single_domain, agents ["danh_sach_thi"], primary "danh_sach_thi"

Q: "Lịch KTHP học kỳ 1 năm 2025-2026 đợt 2 môn CSDL thi ngày nào?"
→ intent single_domain, agents ["lich_thi"], primary "lich_thi"

Q: "Lịch thi lại học kỳ 2 năm 2024-2025 môn Toán cao cấp?"
→ intent single_domain, agents ["lich_thi"], primary "lich_thi" (thi lại = file kthp_lan2_*)

Tóm tắt phiên:
{session_summary}

Hội thoại gần đây:
{history_text}

Câu hỏi (đã rewrite nếu cần):
{question}

Trả lời ĐÚNG MỘT JSON (không markdown):
{{"intent": "<single_domain|multi_domain|form_procedure|grade_result>",
  "agents": ["agent_id"],
  "primary": "agent_id",
  "confidence": 0.0-1.0,
  "reason": "1-2 câu tiếng Việt: vì sao chọn agent này"}}"""


@dataclass
class RoutingDecision:
    agents:     list[str]
    primary:    str
    reason:     str
    intent:     str = ""
    confidence: float = 0.0


class SupervisorIntentCache:
    """Cache supervisor routing decisions per query."""

    def __init__(self, ttl_seconds: int = 300):
        self.cache: dict[str, tuple[RoutingDecision, float]] = {}
        self.ttl = ttl_seconds

    def _get_cache_key(self, question: str) -> str:
        q_normalized = " ".join(question.lower().strip().split())
        return hashlib.md5(q_normalized.encode()).hexdigest()

    def get(self, question: str) -> RoutingDecision | None:
        key = self._get_cache_key(question)
        if key not in self.cache:
            return None
        decision, timestamp = self.cache[key]
        if time_mod.time() - timestamp > self.ttl:
            del self.cache[key]
            log.debug("[supervisor_cache] expired: %s", question[:40])
            return None
        log.info("[supervisor_cache] hit: %s", question[:50])
        return decision

    def set(self, question: str, decision: RoutingDecision):
        key = self._get_cache_key(question)
        self.cache[key] = (decision, time_mod.time())
        log.debug("[supervisor_cache] set: %s", question[:50])

    def clear(self):
        self.cache.clear()

    def size(self) -> int:
        return len(self.cache)


_supervisor_cache = SupervisorIntentCache(ttl_seconds=300)


def _normalize_q(question: str) -> str:
    return f" {question.lower()} "


def _apply_domain_keyword_rules(question: str, scores: dict[str, int]) -> None:
    """Điều chỉnh điểm keyword — ưu tiên chính xác nghiệp vụ."""
    low = _normalize_q(question)

    if any(m in low for m in _ADMISSION_MARKERS):
        if "tuyen_sinh" in scores:
            scores["tuyen_sinh"] += 6
        if "diem_thi" in scores:
            scores["diem_thi"] = max(0, scores["diem_thi"] - 5)

    if _MSSV_RE.search(question):
        if "diem_thi" in scores:
            scores["diem_thi"] += 8
        for aid in ("tuyen_sinh", "khao_thi"):
            if aid in scores:
                scores[aid] = max(0, scores[aid] - 2)

    if any(m in low for m in _FORM_STRONG_MARKERS):
        if "bieu_mau" in scores:
            scores["bieu_mau"] += 4

    if any(m in low for m in _FEE_MARKERS):
        if "bieu_mau" in scores:
            scores["bieu_mau"] += 7
        if "tuyen_sinh" in scores:
            scores["tuyen_sinh"] = max(0, scores["tuyen_sinh"] - 2)

    if any(m in low for m in _MA_TRAN_STRONG):
        if "ma_tran" in scores:
            scores["ma_tran"] += 5

    if any(m in low for m in _DANH_SACH_THI_MARKERS):
        if "danh_sach_thi" in scores:
            scores["danh_sach_thi"] += 6
        if "diem_thi" in scores and not any(
            m in low for m in ("điểm", "diem", "bảng điểm", "bang diem", "kết quả", "ket qua")
        ):
            scores["diem_thi"] = max(0, scores["diem_thi"] - 4)

    if any(m in low for m in _LICH_THI_MARKERS):
        if "lich_thi" in scores:
            scores["lich_thi"] += 6
        if "khao_thi" in scores and not any(m in low for m in ("quy chế", "quy che", "chuẩn đầu ra")):
            scores["khao_thi"] = max(0, scores["khao_thi"] - 3)


def _keyword_scores(question: str) -> dict[str, int]:
    q = question.lower()
    enabled = active_agent_ids()
    scores: dict[str, int] = {aid: 0 for aid in enabled}
    for aid in enabled:
        cfg = AGENTS[aid]
        for kw in cfg.get("keywords", []):
            if kw.lower() in q:
                scores[aid] += 2
    _apply_domain_keyword_rules(question, scores)
    return scores


def _keyword_fallback(question: str) -> RoutingDecision:
    ranked = sorted(_keyword_scores(question).items(), key=lambda x: -x[1])
    top = [aid for aid, s in ranked if s > 0]
    enabled = active_agent_ids()
    if not top:
        top = [enabled[0]] if enabled else ["tuyen_sinh"]
    agents = filter_enabled_agents(top[:2]) or top[:2]
    primary = agents[0]
    agents, primary = _ensure_fee_agent(question, agents, primary)

    low = _normalize_q(question)
    if _MSSV_RE.search(question):
        intent = SUP_INTENT_GRADE
    elif any(m in low for m in _FORM_STRONG_MARKERS[:4]):
        intent = SUP_INTENT_FORM
    elif len(agents) > 1:
        intent = SUP_INTENT_MULTI
    else:
        intent = "single_domain"

    return RoutingDecision(
        agents=agents,
        primary=primary,
        reason="Phân loại theo từ khóa (fallback có điều chỉnh domain).",
        intent=intent,
        confidence=0.72,
    )


def _keyword_confident(question: str) -> RoutingDecision | None:
    """
    Fast-path chỉ khi SUPERVISOR_FAST_PATH bật (mặc định tắt khi ACCURACY_MODE).
    Chỉ các trường hợp không mơ hồ: MSSV, điểm chuẩn, biểu mẫu rõ, ma trận rõ.
    """
    if not SUPERVISOR_FAST_PATH:
        return None

    low = _normalize_q(question)

    if _MSSV_RE.search(question) and not any(m in low for m in ("điểm chuẩn", "diem chuan")):
        dec = RoutingDecision(
            agents=filter_enabled_agents(["diem_thi"]) or ["diem_thi"],
            primary="diem_thi",
            reason="Fast-path: MSSV — tra kết quả học tập.",
            intent=SUP_INTENT_GRADE,
            confidence=0.93,
        )
        log.info(f"[supervisor:fast] agents={dec.agents} primary={dec.primary}")
        return dec

    if any(m in low for m in ("điểm chuẩn", "diem chuan", "ngưỡng tuyển", "nguong tuyen")):
        agents = filter_enabled_agents(["tuyen_sinh"]) or ["tuyen_sinh"]
        dec = RoutingDecision(
            agents=agents,
            primary=agents[0],
            reason="Fast-path: điểm chuẩn / tuyển sinh.",
            intent="single_domain",
            confidence=0.91,
        )
        log.info(f"[supervisor:fast] agents={dec.agents} primary={dec.primary}")
        return dec

    form_hits = sum(1 for m in _FORM_STRONG_MARKERS if m in low)
    if form_hits >= 2 or (
        ("biểu mẫu" in low or "bieu mau" in low) and ("đơn" in low or "don " in low)
    ):
        agents = filter_enabled_agents(["bieu_mau"]) or ["bieu_mau"]
        dec = RoutingDecision(
            agents=agents,
            primary=agents[0],
            reason="Fast-path: biểu mẫu / thủ tục.",
            intent=SUP_INTENT_FORM,
            confidence=0.90,
        )
        log.info(f"[supervisor:fast] agents={dec.agents} primary={dec.primary}")
        return dec

    if any(m in low for m in _MA_TRAN_STRONG):
        agents = filter_enabled_agents(["ma_tran"]) or ["ma_tran"]
        dec = RoutingDecision(
            agents=agents,
            primary=agents[0],
            reason="Fast-path: ma trận đề thi.",
            intent="single_domain",
            confidence=0.90,
        )
        log.info(f"[supervisor:fast] agents={dec.agents} primary={dec.primary}")
        return dec

    return None


def _schedule_subject_list_route(question: str) -> RoutingDecision | None:
    """Liệt kê môn thi KTHP — luôn lich_thi, không LLM Supervisor."""
    low = _normalize_q(question)
    if any(m in low for m in ("điểm", "diem", "điểm số", "diem so")) and _MSSV_RE.search(question):
        return None
    list_q = any(
        m in low
        for m in (
            "những môn",
            "cac mon",
            "các môn",
            "danh sách môn",
            "danh sach mon",
            "liệt kê môn",
            "liet ke mon",
            "môn nào",
            "mon nao",
            "thi những môn",
            "thi nhung mon",
        )
    )
    mon_thi_q = ("môn thi" in low or "mon thi" in low) and any(
        m in low for m in ("là gì", "la gi", "nào", "nao", "gồm", "gom", "những", "cac", "các")
    )
    mon_nao_q = ("môn nào" in low or "mon nao" in low) and any(
        m in low for m in ("thi", "kthp", "đợt", "dot", "học kỳ", "hoc ky", "kì", "ki ")
    )
    if not list_q and not mon_thi_q and not mon_nao_q:
        return None
    period_ok = any(
        m in low
        for m in _LICH_THI_MARKERS
        + ("học kỳ", "hoc ky", "học kì", "hoc ki", "đợt", "dot", "kì 1", "ki 1", "2023", "2024")
    )
    if not period_ok:
        return None
    agents = filter_enabled_agents(["lich_thi"]) or ["lich_thi"]
    dec = RoutingDecision(
        agents=agents,
        primary=agents[0],
        reason="Liệt kê môn thi KTHP — agent lich_thi (fast route).",
        intent="single_domain",
        confidence=0.94,
    )
    log.info(f"[supervisor:schedule_list] agents={dec.agents} primary={dec.primary}")
    return dec


def _mssv_exam_list_route(question: str) -> RoutingDecision | None:
    """MSSV + danh sách/phòng/ca thi → danh_sach_thi (không tra điểm)."""
    if not _MSSV_RE.search(question):
        return None
    low = _normalize_q(question)
    if not any(m in low for m in _DANH_SACH_THI_MARKERS):
        return None
    if any(m in low for m in _GRADE_CONTEXT_MARKERS):
        return None
    agents = filter_enabled_agents(["danh_sach_thi"]) or ["danh_sach_thi"]
    dec = RoutingDecision(
        agents=agents,
        primary=agents[0],
        reason="MSSV + danh sách/phòng/ca thi — agent danh_sach_thi.",
        intent="single_domain",
        confidence=0.93,
    )
    log.info(f"[supervisor:exam_list] agents={dec.agents} primary={dec.primary}")
    return dec


def _sbd_exam_list_route(question: str) -> RoutingDecision | None:
    """SBD + ngữ cảnh danh sách/ca/phòng thi => danh_sach_thi."""
    if not _SBD_RE.search(question):
        return None
    low = _normalize_q(question)
    if not any(m in low for m in _DANH_SACH_THI_MARKERS):
        return None
    if any(m in low for m in _GRADE_CONTEXT_MARKERS):
        return None
    agents = filter_enabled_agents(["danh_sach_thi"]) or ["danh_sach_thi"]
    dec = RoutingDecision(
        agents=agents,
        primary=agents[0],
        reason="SBD + danh sách/phòng/ca thi — agent danh_sach_thi.",
        intent="single_domain",
        confidence=0.93,
    )
    log.info(f"[supervisor:exam_list_sbd] agents={dec.agents} primary={dec.primary}")
    return dec


def _mssv_grade_route(question: str) -> RoutingDecision | None:
    """MSSV + ngữ cảnh tra cứu → diem_thi (luôn bật, không phụ thuộc SUPERVISOR_FAST_PATH)."""
    if not _MSSV_RE.search(question):
        return None
    low = _normalize_q(question)
    if any(m in low for m in ("điểm chuẩn", "diem chuan", "ngưỡng tuyển", "nguong tuyen", "chỉ tiêu", "chi tieu")):
        return None
    if any(m in low for m in _DANH_SACH_THI_MARKERS) and not any(
        m in low for m in _GRADE_CONTEXT_MARKERS
    ):
        return None
    if not any(m in low for m in _GRADE_CONTEXT_MARKERS):
        return None
    agents = filter_enabled_agents(["diem_thi"]) or ["diem_thi"]
    dec = RoutingDecision(
        agents=agents,
        primary=agents[0],
        reason="MSSV + tra cứu kết quả — agent diem_thi.",
        intent=SUP_INTENT_GRADE,
        confidence=0.94,
    )
    log.info(f"[supervisor:mssv] agents={dec.agents} primary={dec.primary}")
    return dec


def _subject_schedule_route(question: str) -> RoutingDecision | None:
    """Hỏi lịch/địa điểm thi theo môn + kỳ/đợt => lich_thi (không mssv)."""
    if _MSSV_RE.search(question):
        return None
    low = _normalize_q(question)
    if any(
        m in low
        for m in (
            "ma trận", "ma tran", "cấu trúc đề", "cau truc de",
            "bao nhiêu câu", "bao nhieu cau", "bao nhiêu phút", "bao nhieu phut",
        )
    ):
        return None
    has_subject = (" môn " in low) or (" mon " in low)
    has_period = any(
        m in low
        for m in (
            "học kỳ", "hoc ky", "học kì", "hoc ki", "kì ", "ki ", "hk1", "hk2",
            "đợt", "dot", "dot1", "dot2", "đợt1", "đợt2", "kthp",
        )
    )
    has_calendar_cue = any(
        m in low
        for m in (
            "thời gian", "thoi gian", "giờ", "gio", "ngày", "ngay",
            "bắt đầu", "bat dau", "khi nào", "khi nao",
        )
    )
    has_schedule_intent = any(m in low for m in _SCHEDULE_SUBJECT_MARKERS)
    if not (has_subject and has_schedule_intent and (has_period or has_calendar_cue)):
        return None
    agents = filter_enabled_agents(["lich_thi"]) or ["lich_thi"]
    dec = RoutingDecision(
        agents=agents,
        primary=agents[0],
        reason="Môn + học kỳ/đợt + địa điểm/giờ thi — agent lich_thi.",
        intent="single_domain",
        confidence=0.95,
    )
    log.info(f"[supervisor:schedule_subject] agents={dec.agents} primary={dec.primary}")
    return dec


def _multi_domain_heuristic(question: str) -> RoutingDecision | None:
    """Hai mảng rõ (tuyển sinh + phí/biểu mẫu, …) — không cần LLM."""
    low = _normalize_q(question)
    has_admission = any(m in low for m in _ADMISSION_MARKERS)
    has_fee = any(m in low for m in _FEE_MARKERS)
    has_form = any(m in low for m in _FORM_STRONG_MARKERS)
    has_exam = any(m in low for m in ("quy chế", "quy che", "chuẩn đầu ra", "chuẩn ngoại ngữ", "toeic", "vstep"))

    agent_ids: list[str] = []
    if has_admission:
        agent_ids.append("tuyen_sinh")
    if has_fee or has_form:
        agent_ids.append("bieu_mau")
    if has_exam and "khao_thi" not in agent_ids:
        agent_ids.append("khao_thi")

    if len(agent_ids) < 2:
        return None

    agents = filter_enabled_agents(agent_ids) or agent_ids[:2]
    primary = "tuyen_sinh" if "tuyen_sinh" in agents else agents[0]
    return RoutingDecision(
        agents=agents[:3],
        primary=primary,
        reason="Heuristic multi-domain: nhiều mảng trong cùng câu hỏi.",
        intent=SUP_INTENT_MULTI,
        confidence=0.88,
    )


def _ensure_fee_agent(question: str, agents: list[str], primary: str) -> tuple[list[str], str]:
    """Câu hỏi phí/thủ tục nhập học phải có bieu_mau."""
    low = _normalize_q(question)
    if not any(m in low for m in _FEE_MARKERS):
        return agents, primary
    if "bieu_mau" in agents:
        return agents, primary
    merged = filter_enabled_agents(["bieu_mau"] + agents) or (["bieu_mau"] + agents)
    return merged[:3], primary


def _parse_json(raw: str) -> dict | None:
    raw = raw.strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def route(
    question: str,
    *,
    history: list[dict] | None = None,
    session_summary: str = "",
) -> RoutingDecision:
    question = question.strip()
    cached = _supervisor_cache.get(question)
    if cached:
        return cached

    decision = _route_impl(
        question,
        history=history,
        session_summary=session_summary,
    )
    _supervisor_cache.set(question, decision)
    return decision


def _route_impl(
    question: str,
    *,
    history: list[dict] | None = None,
    session_summary: str = "",
) -> RoutingDecision:
    hist = history_for_supervisor(history or [])
    summary = (session_summary or "").strip()

    exam_list_dec = _mssv_exam_list_route(question)
    if exam_list_dec is not None:
        return exam_list_dec

    sbd_exam_list_dec = _sbd_exam_list_route(question)
    if sbd_exam_list_dec is not None:
        return sbd_exam_list_dec

    schedule_list_dec = _schedule_subject_list_route(question)
    if schedule_list_dec is not None:
        return schedule_list_dec

    mssv_dec = _mssv_grade_route(question)
    if mssv_dec is not None:
        return mssv_dec

    subject_schedule_dec = _subject_schedule_route(question)
    if subject_schedule_dec is not None:
        return subject_schedule_dec

    multi_dec = _multi_domain_heuristic(question)
    if multi_dec is not None:
        return multi_dec

    fast = _keyword_confident(question)
    if fast is not None:
        return fast

    try:
        resp = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{
                "role": "user",
                "content": SUPERVISOR_PROMPT.format(
                    agent_list=_AGENT_LIST_TEXT,
                    session_summary=summary or "(Chưa có.)",
                    history_text=format_history_text(hist),
                    question=question,
                ),
            }],
            max_tokens=200,
            temperature=0.0,
        )
        raw  = resp.choices[0].message.content.strip()
        data = _parse_json(raw)
        if not data:
            raise ValueError(f"Invalid JSON: {raw[:120]}")

        agents = filter_enabled_agents([a for a in data.get("agents", []) if a in AGENT_IDS])
        if not agents:
            enabled = active_agent_ids()
            if not enabled:
                raise ValueError("All agents disabled")
            agents = [enabled[0]]

        primary = data.get("primary", agents[0])
        if primary not in agents:
            primary = agents[0]

        reason = str(data.get("reason", "")).strip() or "Phân loại bởi Supervisor."
        intent = str(data.get("intent", "single_domain")).strip() or "single_domain"
        try:
            confidence = float(data.get("confidence", 0.85))
        except (TypeError, ValueError):
            confidence = 0.85
        confidence = max(0.0, min(1.0, confidence))

        # Điểm chuẩn + diem_thi: sửa nếu LLM nhầm
        low = _normalize_q(question)
        if any(m in low for m in ("điểm chuẩn", "diem chuan")) and "diem_thi" in agents:
            agents = [a for a in agents if a != "diem_thi"]
            if "tuyen_sinh" not in agents:
                agents = filter_enabled_agents(["tuyen_sinh"] + agents) or agents
            if not agents:
                agents = filter_enabled_agents(["tuyen_sinh"]) or ["tuyen_sinh"]
            primary = "tuyen_sinh" if "tuyen_sinh" in agents else primary
            reason += " (điều chỉnh: điểm chuẩn → tuyển sinh)."

        agents, primary = _ensure_fee_agent(question, agents, primary)

        if confidence < SUPERVISOR_LOW_CONFIDENCE and ACCURACY_MODE:
            kw = _keyword_fallback(question)
            if kw.agents != agents or kw.primary != primary:
                log.info(
                    f"[supervisor] conf={confidence:.2f} thấp — blend keyword "
                    f"{kw.agents}/{kw.primary}"
                )
                merged = list(dict.fromkeys(agents + kw.agents))[:3]
                agents = filter_enabled_agents(merged) or agents
                if kw.confidence >= confidence and kw.primary in agents:
                    primary = kw.primary
                reason = f"{reason} | Kiểm chứng từ khóa: {kw.reason}"

        log.info(f"[supervisor] intent={intent} agents={agents} primary={primary} conf={confidence}")
        return RoutingDecision(
            agents=agents[:3],
            primary=primary,
            reason=reason,
            intent=intent,
            confidence=confidence,
        )

    except Exception as e:
        log.warning(f"[supervisor] LLM failed: {e}, using keyword fallback")
        return _keyword_fallback(question)
