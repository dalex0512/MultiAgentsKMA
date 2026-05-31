import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY  = os.environ["OPENAI_API_KEY"]
QDRANT_URL      = os.environ["QDRANT_URL"]
QDRANT_API_KEY  = os.environ["QDRANT_API_KEY"]

# Chat/LLM: OPENAI_API_KEY + OPENAI_BASE_URL (9router). Embedding: trực tiếp OpenAI.
OPENAI_EMBED_API_KEY = os.environ.get("OPENAI_EMBED_API_KEY") or OPENAI_API_KEY
OPENAI_EMBED_BASE_URL = os.environ.get(
    "OPENAI_EMBED_BASE_URL", "https://api.openai.com/v1"
).rstrip("/")

COLLECTION_NAME = "kma_docs"
EMBED_MODEL     = "text-embedding-3-small"
LLM_MODEL       = os.environ.get("LLM_MODEL", "gpt-4o-mini")


def embed_client():
    """Client embedding — luôn gọi OpenAI trực tiếp, không qua OPENAI_BASE_URL (9router)."""
    from openai import OpenAI

    return OpenAI(api_key=OPENAI_EMBED_API_KEY, base_url=OPENAI_EMBED_BASE_URL)

# Chế độ nhanh (mặc định TẮT). Bật khi cần demo nhanh: KMA_FAST_MODE=1
FAST_MODE = os.environ.get("KMA_FAST_MODE", "0").strip().lower() in ("1", "true", "yes")

# Ưu tiên độ chính xác tối đa cho MỌI agent (mặc định BẬT). Tắt: KMA_ACCURACY_MODE=0
# Tự tắt khi FAST_MODE=1
_acc_raw = os.environ.get("KMA_ACCURACY_MODE", "1").strip().lower()
ACCURACY_MODE = (not FAST_MODE) and _acc_raw in ("1", "true", "yes")

# Supervisor fast-path (mặc định TẮT khi ACCURACY_MODE). Bật: KMA_SUPERVISOR_FAST_PATH=1
_sup_fast_raw = os.environ.get("KMA_SUPERVISOR_FAST_PATH", "").strip().lower()
if _sup_fast_raw in ("1", "true", "yes"):
    SUPERVISOR_FAST_PATH = True
elif _sup_fast_raw in ("0", "false", "no"):
    SUPERVISOR_FAST_PATH = False
else:
    SUPERVISOR_FAST_PATH = not ACCURACY_MODE

SUPERVISOR_LOW_CONFIDENCE = float(os.environ.get("KMA_SUPERVISOR_LOW_CONF", "0.75"))

# Retrieve — accuracy: nhiều chunk hơn; Router vẫn chọn pipeline theo Qc
TOP_K           = 5 if FAST_MODE else (12 if ACCURACY_MODE else 8)
MAX_ROUNDS      = 2 if FAST_MODE else 4
# Ingest flat (diem_thi, bieu_mau): CHUNK_SIZE = số TỪ (không phải ký tự)
CHUNK_SIZE      = 500
CHUNK_OVERLAP   = 50

# ── Parent–Child chunking (ý tưởng 5) ─────────────────────────────────────────
USE_PARENT_CHILD_INGEST = os.environ.get("KMA_PARENT_CHILD_INGEST", "1").strip().lower() in (
    "1", "true", "yes",
)
PARENT_CHILD_AGENTS: frozenset[str] = frozenset({
    aid.strip()
    for aid in os.environ.get(
        "KMA_PARENT_CHILD_AGENTS",
        "tuyen_sinh,khao_thi,ma_tran",
    ).split(",")
    if aid.strip()
})
PARENT_CHUNK_CHARS = int(os.environ.get("KMA_PARENT_CHUNK_CHARS", "1500"))
PARENT_CHUNK_OVERLAP_CHARS = int(os.environ.get("KMA_PARENT_CHUNK_OVERLAP_CHARS", "120"))
CHILD_CHUNK_CHARS = int(os.environ.get("KMA_CHILD_CHUNK_CHARS", "200"))
CHILD_CHUNK_OVERLAP_CHARS = int(os.environ.get("KMA_CHILD_CHUNK_OVERLAP_CHARS", "40"))
# Retrieve: tìm nhiều child, gom tối đa N parent cho prompt
PARENT_SEARCH_POOL_MULTIPLIER = max(2, int(os.environ.get("KMA_PARENT_SEARCH_POOL", "4")))
PARENT_RETRIEVE_MAX = int(os.environ.get("KMA_PARENT_RETRIEVE_MAX", "6"))

# ── Metadata-rich table ingest (ý tưởng 7) ────────────────────────────────────
USE_TABLE_METADATA_INGEST = os.environ.get("KMA_TABLE_METADATA_INGEST", "1").strip().lower() in (
    "1", "true", "yes",
)
TABLE_INGEST_AGENTS: frozenset[str] = frozenset({
    aid.strip()
    for aid in os.environ.get(
        "KMA_TABLE_METADATA_AGENTS",
        "diem_thi,ma_tran,danh_sach_thi,lich_thi",
    ).split(",")
    if aid.strip()
})
TABLE_MAX_ROWS_PER_CHUNK = int(os.environ.get("KMA_TABLE_MAX_ROWS", "35"))

# Lịch thi / danh sách thi — PDF dạng bảng KTHP: bỏ grader nhiều vòng + agentic (nhanh hơn)
USE_SCHEDULE_TABLE_FAST_PATH = os.environ.get(
    "KMA_SCHEDULE_TABLE_FAST_PATH", "1",
).strip().lower() in ("1", "true", "yes")
SCHEDULE_FAST_PATH_AGENTS: frozenset[str] = frozenset({
    aid.strip()
    for aid in os.environ.get(
        "KMA_SCHEDULE_FAST_PATH_AGENTS", "lich_thi,danh_sach_thi",
    ).split(",")
    if aid.strip()
})
SCHEDULE_TABLE_TOP_K = int(os.environ.get("KMA_SCHEDULE_TABLE_TOP_K", "40"))

# ── Document Relevance Grader (ý tưởng 6 — Corrective RAG) ────────────────────
USE_RELEVANCE_GRADER = os.environ.get("KMA_RELEVANCE_GRADER", "1").strip().lower() in (
    "1", "true", "yes",
)
GRADER_MAX_REQUERY = int(
    os.environ.get("KMA_GRADER_MAX_REQUERY", "2" if ACCURACY_MODE else "1"),
)
GRADER_MAX_CHUNKS = int(os.environ.get("KMA_GRADER_MAX_CHUNKS", "5"))
GRADER_CHUNK_EXCERPT_CHARS = int(os.environ.get("KMA_GRADER_EXCERPT_CHARS", "480"))
GRADER_LLM_MAX_TOKENS = int(os.environ.get("KMA_GRADER_MAX_TOKENS", "80"))

# Tra cứu điểm theo MSSV — gom nhiều chunk bảng điểm, liệt kê đủ môn trong kỳ
GRADE_LOOKUP_CHUNK_LIMIT   = 100
GRADE_LOOKUP_MAX_CONTEXT   = 14_000
GRADE_LOOKUP_MAX_TOKENS    = 1536

# ── Qc cục bộ (utils/qc_calculator) — báo cáo report_final ───────────────────
USE_LOCAL_QC = os.environ.get("KMA_USE_LOCAL_QC", "1").strip().lower() in ("1", "true", "yes")
# Hybrid: Qc cục bộ + LLM khi câu nhiều ý / vùng ngưỡng / intent phức tạp (mặc định bật khi accuracy)
_qc_hybrid_raw = os.environ.get("KMA_QC_HYBRID", "").strip().lower()
if _qc_hybrid_raw in ("1", "true", "yes"):
    USE_QC_HYBRID = True
elif _qc_hybrid_raw in ("0", "false", "no"):
    USE_QC_HYBRID = False
else:
    USE_QC_HYBRID = ACCURACY_MODE and USE_LOCAL_QC
_load_router_default = "0" if ACCURACY_MODE else "1"
USE_LOAD_ROUTER = os.environ.get(
    "KMA_LOAD_ROUTER", _load_router_default,
).strip().lower() in ("1", "true", "yes")
USE_KMA_TEXT_NORM = os.environ.get("KMA_TEXT_NORM", "1").strip().lower() in ("1", "true", "yes")

QC_WEIGHT_E = 0.150
QC_WEIGHT_R = 0.376
QC_WEIGHT_L = 0.089
QC_WEIGHT_S = 0.386
QC_FALLBACK = 0.55
QC_PREFETCH_TOP_K = int(os.environ.get("KMA_QC_PREFETCH_TOP_K", "5"))

# Router: ngưỡng báo cáo khi Qc cục bộ; ngưỡng cũ khi LLM Qc hoặc FAST_MODE
if USE_LOCAL_QC and not FAST_MODE:
    ROUTER_T1 = 0.50
    ROUTER_T2 = 0.70
else:
    ROUTER_T1 = 0.45 if FAST_MODE else 0.40
    ROUTER_T2 = 0.72 if FAST_MODE else 0.65

THRESHOLD1 = ROUTER_T1   # alias tương thích
THRESHOLD2 = ROUTER_T2

LOAD_ROUTER_MAX_CONNECTIONS = int(os.environ.get("KMA_MAX_ACTIVE_CHATS", "500"))

# ── Session nóng–lạnh ─────────────────────────────────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "").strip()
SESSION_BACKEND = os.environ.get("KMA_SESSION_BACKEND", "redis" if REDIS_URL else "memory").strip().lower()
SESSION_HOT_TTL_SEC = int(os.environ.get("KMA_SESSION_HOT_TTL_SEC", str(2 * 3600)))
SESSION_COLD_IDLE_SEC = int(os.environ.get("KMA_SESSION_COLD_IDLE_SEC", str(3600)))
HISTORY_HOT_MAX_MESSAGES = int(os.environ.get("KMA_HISTORY_HOT_MAX", "6"))

# Retrieve yếu → specialist leo Agentic (bổ sung cho hybrid, không thay Router)
MIN_RETRIEVAL_SCORE = 0.0 if (FAST_MODE or not ACCURACY_MODE) else 0.40

LLM_MAX_TOKENS  = 768 if FAST_MODE else (1536 if ACCURACY_MODE else 1024)
AGG_MAX_TOKENS  = 900 if FAST_MODE else (1400 if ACCURACY_MODE else 1200)

# ── Conversation memory ───────────────────────────────────────────────────────
HISTORY_MAX_MESSAGES     = max(12, HISTORY_HOT_MAX_MESSAGES)  # client gửi lên
HISTORY_FOR_REWRITE      = 8    # số message đưa vào query rewriter
HISTORY_FOR_SUPERVISOR   = 6    # số message đưa vào supervisor
HISTORY_FOR_GENERATE     = 10   # số message đưa vào RAG generate
SESSION_SUMMARY_EVERY    = 3    # cập nhật tóm tắt sau mỗi N lượt (turn)
SESSION_SUMMARY_MAX_CHARS = 1200
SESSION_MAX_STORED       = 800  # giới hạn session trong RAM

# ── Question planner (Phase 3) ────────────────────────────────────────────────
PLANNER_MAX_SUB_QUESTIONS = 3
PLANNER_MIN_WORDS         = 28 if FAST_MODE else 22   # từ — heuristic bật planner LLM

# ── Multi-Agent: specialist agents ↔ docs/ subfolders ─────────────────────────
DOCS_ROOT = os.path.join(os.path.dirname(__file__), "docs")

AGENTS: dict[str, dict] = {
    "tuyen_sinh": {
        "name": "Trợ lý Tuyển sinh & CTĐT",
        "folder": "tuyen_sinh_va_chuong_trinh_dao_tao",
        "description": (
            "Tuyển sinh đại học/thạc sĩ, đề án tuyển sinh, điểm chuẩn, ngành học, "
            "chương trình đào tạo các ngành, thông tin nhập học."
        ),
        "keywords": [
            "tuyển sinh", "nhập học", "đề án", "ngành", "chương trình đào tạo",
            "thạc sĩ", "trúng tuyển", "ctđt", "cntt", "dtvt", "attt",
            "điểm chuẩn", "ngưỡng", "chỉ tiêu",
        ],
    },
    "khao_thi": {
        "name": "Trợ lý Khảo thí & Quy chế",
        "folder": "khao_thi_quy_che",
        "description": (
            "Quy chế đào tạo, chuẩn đầu ra ngoại ngữ, quy định thi, thi tốt nghiệp, "
            "sát hạch, quy trình khảo thí."
        ),
        "keywords": [
            "quy chế", "chuẩn đầu ra", "ngoại ngữ", "thi tốt nghiệp", "sát hạch",
            "khảo thí", "quy định", "đầu ra",
        ],
    },
    "ma_tran": {
        "name": "Trợ lý Ma trận đề thi",
        "folder": "ma_tran_de_thi",
        "description": (
            "Ma trận đề thi, cấu trúc đề, môn học cụ thể (tin học, CSDL, toán, "
            "an toàn thông tin, kiểm thử, quản trị an toàn)."
        ),
        "keywords": [
            "ma trận", "đề thi", "cấu trúc đề", "môn thi", "tin học đại cương",
            "csdl", "kiểm thử", "toán cao cấp",
        ],
    },
    "diem_thi": {
        "name": "Trợ lý Kết quả học tập & Thi",
        "folder": "diem_thi",
        "description": (
            "Kết quả thi, điểm học kỳ, bảng điểm công bố theo MSSV (trong file PDF điểm), "
            "tốt nghiệp CT4, thi Anh văn, danh sách chứng chỉ."
        ),
        "keywords": [
            "bảng điểm", "bang diem", "kết quả thi", "ket qua thi",
            "học kỳ", "hoc ky", "mssv", "tốt nghiệp", "tot nghiep",
            "chứng chỉ", "chung chi", "xem điểm", "công bố điểm",
            "đợt thi", "dot thi", "ct4", "anh văn ct4",
        ],
    },
    "bieu_mau": {
        "name": "Trợ lý Biểu mẫu & Thủ tục",
        "folder": "bieu_mau",
        "description": (
            "Đơn từ, biểu mẫu, thủ tục hành chính sinh viên: nghỉ học, phúc khảo, "
            "cấp thẻ, BHYT, thực tập, ra trường, tài khoản MBank."
        ),
        "keywords": [
            "biểu mẫu", "đơn", "mẫu đơn", "tải về", "thủ tục", "phúc khảo",
            "nghỉ học", "bảo lưu", "thẻ sinh viên", "bhyt", "thực tập",
            "nhập học", "phí nhập", "lệ phí", "số tiền", "nộp tiền",
        ],
    },
    "danh_sach_thi": {
        "name": "Trợ lý Danh sách thi",
        "folder": "danh_sach_thi",
        "description": (
            "Danh sách sinh viên dự thi theo ngày, ca (sáng/chiều), phòng thi, "
            "môn thi; tra cứu MSSV trong bảng danh sách thi công bố."
        ),
        "keywords": [
            "danh sách thi", "danh sach thi", "phòng thi", "phong thi",
            "ca thi", "ca sáng", "ca chieu", "buổi sáng", "buoi sang",
            "buổi chiều", "buoi chieu", "số báo danh", "so bao danh",
            "danh sách dự thi", "thi ngày", "phòng",
        ],
    },
    "lich_thi": {
        "name": "Trợ lý Lịch thi",
        "folder": "lich_thi",
        "description": (
            "Lịch thi KTHP (kỳ thi học phần): học kỳ, năm học, đợt thi, "
            "ngày giờ thi từng môn; kthp_lan2_* là lịch thi lại (học lại, thi lần 2)."
        ),
        "keywords": [
            "lịch thi", "lich thi", "kthp", "kỳ thi học phần", "ky thi hoc phan",
            "lịch kthp", "lich kthp", "đợt thi", "dot thi", "học kỳ", "hoc ky",
            "thi học phần", "lịch thi hk", "lich thi hk",
            "thi lại", "thi lai", "lần 2", "lan 2", "học lại", "hoc lai",
        ],
    },
}

AGENT_IDS: list[str] = list(AGENTS.keys())

FOLDER_TO_AGENT: dict[str, str] = {
    cfg["folder"]: aid for aid, cfg in AGENTS.items()
}
