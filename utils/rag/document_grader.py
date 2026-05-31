"""
Ý tưởng 6 — Document Relevance Grader (Corrective / Self-RAG).

Sau retrieve: LLM YES/NO → nếu NO thì requery (query expansion) → tối đa N lần.
Fallback catalog cho agent biểu mẫu.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    LLM_MODEL,
    TOP_K,
    FAST_MODE,
    USE_RELEVANCE_GRADER,
    GRADER_MAX_REQUERY,
    GRADER_MAX_CHUNKS,
    GRADER_CHUNK_EXCERPT_CHARS,
    GRADER_LLM_MAX_TOKENS,
)
from pipelines.retrieval import rerank_documents, top_retrieval_confidence
from utils.rag.table_context import GRADER_TABLE_NOTE, docs_contain_tables

log = logging.getLogger(__name__)

_openai = OpenAI(api_key=OPENAI_API_KEY)

GRADER_PROMPT = """\
Bạn là bộ kiểm định relevance cho RAG Học viện KMA.

Câu hỏi sinh viên:
{question}

Các đoạn tài liệu retrieve (có thể tương đồng từ khóa nhưng chưa chắc chứa đáp án):
{chunks}

Nhiệm vụ: Có ít nhất MỘT đoạn chứa thông tin TRỰC TIẾP để trả lời câu hỏi không?

Trả lời ĐÚNG format (2 dòng):
Dòng 1: YES hoặc NO
Dòng 2: Giải thích ngắn tiếng Việt (tối đa 25 từ)"""

REQUERY_PROMPT = """\
Câu hỏi: {question}

Các đoạn tài liệu hiện tại KHÔNG đủ để trả lời (similarity cao nhưng sai/ngắt đoạn).

{chunks}

Tạo MỘT truy vấn tìm kiếm mới (8-14 từ tiếng Việt, từ khóa cụ thể từ quy chế KMA).
Chỉ trả truy vấn, không giải thích:"""


@dataclass
class GradingTrace:
    sufficient: bool = True
    reason: str = ""
    requery_count: int = 0
    queries_used: list[str] = field(default_factory=list)
    grader_llm_sec: float = 0.0
    catalog_fallback: bool = False
    extra_context_append: str = ""


def should_use_relevance_grader(agent_id: str | None) -> bool:
    if not USE_RELEVANCE_GRADER or FAST_MODE:
        return False
    if not agent_id:
        return True
    from config import USE_SCHEDULE_TABLE_FAST_PATH, SCHEDULE_FAST_PATH_AGENTS
    if USE_SCHEDULE_TABLE_FAST_PATH and agent_id in SCHEDULE_FAST_PATH_AGENTS:
        return False
    return agent_id not in ("diem_thi",)


def _llm(prompt: str, max_tokens: int | None = None) -> tuple[str, float]:
    t0 = time.perf_counter()
    resp = _openai.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens or GRADER_LLM_MAX_TOKENS,
        temperature=0.0,
    )
    return resp.choices[0].message.content.strip(), round(time.perf_counter() - t0, 3)


def _parse_yes_no(raw: str) -> bool:
    first = (raw or "").strip().split("\n")[0].strip().upper()
    if first.startswith("YES") or first.startswith("Y"):
        return True
    if first.startswith("NO") or first.startswith("N"):
        return False
    if re.search(r"\bYES\b", first):
        return True
    if re.search(r"\bNO\b", first):
        return False
    # Mặc định thận trọng — coi là không đủ
    return False


def _excerpt(text: str, limit: int) -> str:
    t = (text or "").strip().replace("\n", " ")
    if len(t) <= limit:
        return t
    return t[: limit - 3] + "..."


def _grader_chunk_limit(agent_id: str | None) -> int:
    if agent_id in ("lich_thi", "danh_sach_thi", "diem_thi", "ma_tran"):
        return max(GRADER_MAX_CHUNKS, 8)
    return GRADER_MAX_CHUNKS


def format_chunks_for_grader(docs: list[dict], agent_id: str | None = None) -> str:
    if not docs:
        return "(Không có đoạn nào.)"
    # Ưu tiên chunk bảng khi grader (tránh chỉ thấy phần mở đầu văn bản)
    ordered = list(docs)
    if agent_id in ("lich_thi", "danh_sach_thi", "diem_thi", "ma_tran"):
        ordered = sorted(
            docs,
            key=lambda d: (
                0 if _is_table_like_chunk(d) else 1,
                -float(d.get("_rank_score", d.get("score", 0.0))),
            ),
        )
    limit = _grader_chunk_limit(agent_id)
    lines = []
    for i, d in enumerate(ordered[:limit], 1):
        body = d.get("text") or d.get("parent_text") or ""
        dtype = d.get("document_type", "prose")
        meta = f"type={dtype}"
        if d.get("section"):
            meta += f" section={d['section'][:60]}"
        lines.append(
            f"[{i}] {d.get('source', '?')} tr.{d.get('page', 0)} "
            f"({meta}, score={d.get('_rank_score', d.get('score', 0)):.2f})\n"
            f"{_excerpt(body, GRADER_CHUNK_EXCERPT_CHARS)}"
        )
    return "\n\n".join(lines)


def grade_document_relevance(
    question: str,
    docs: list[dict],
    *,
    agent_id: str | None = None,
) -> tuple[bool, str, float]:
    """
    Kiểm định YES/NO — các chunk có chứa câu trả lời không.
    Trả (sufficient, reason, llm_seconds).
    """
    if not docs:
        return False, "Không có chunk retrieve.", 0.0

    chunks = format_chunks_for_grader(docs, agent_id)
    extra = GRADER_TABLE_NOTE if docs_contain_tables(docs) else ""
    prompt = GRADER_PROMPT.format(
        question=question.strip(),
        chunks=chunks + (("\n" + extra) if extra else ""),
    )
    raw, t_llm = _llm(prompt, max_tokens=GRADER_LLM_MAX_TOKENS)
    sufficient = _parse_yes_no(raw)
    reason = raw.split("\n", 1)[-1].strip() if "\n" in raw else raw
    log.info("[grader] sufficient=%s reason=%s", sufficient, reason[:80])
    return sufficient, reason, t_llm


def expand_search_query(
    question: str,
    docs: list[dict],
    prior_query: str,
    *,
    agent_id: str | None = None,
) -> str:
    """Sinh truy vấn requery khi grader = NO."""
    prompt = REQUERY_PROMPT.format(
        question=question.strip(),
        chunks=format_chunks_for_grader(docs, agent_id),
    )
    raw, _ = _llm(prompt, max_tokens=48)
    q = raw.strip().strip('"').strip("'")
    if not q or len(q.split()) < 3:
        return prior_query
    return q[:200]


def _boost_schedule_docs(
    retriever,
    question: str,
    retrieval_query: str,
    agent_id: str | None,
    docs: list[dict],
    top_k: int,
) -> list[dict]:
    """Bổ sung chunk từ file lịch/danh sách thi đúng đợt khi câu hỏi nêu HK + năm + đợt."""
    if agent_id not in ("lich_thi", "danh_sach_thi"):
        return docs
    blob = f"{question} {retrieval_query}".lower()
    if not any(m in blob for m in ("đợt 2", "dot 2", "đợt 1", "dot 1")):
        return docs
    extra_terms: list[str] = []
    if any(m in blob for m in ("đợt 2", "dot 2")):
        extra_terms.append("kthp_ki1_20232024_dot2")
        extra_terms.append("dot2")
    if any(m in blob for m in ("học kỳ 1", "hoc ky 1", "hk1", "ki1")):
        extra_terms.append("ki1")
    if "2023" in blob and "2024" in blob:
        extra_terms.append("20232024")
    if not extra_terms:
        return docs
    merged = list(docs)
    for term in extra_terms[:3]:
        try:
            more, _ = retriever.retrieve(term, agent_id=agent_id, top_k=top_k)
            merged = _merge_doc_lists(merged, more)
        except Exception as e:
            log.warning("[grader] boost schedule retrieve failed: %s", e)
    return merged


def _merge_doc_lists(existing: list[dict], new_docs: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for d in existing + new_docs:
        pid = (d.get("parent_id") or "").strip()
        if pid:
            key = ("parent", pid)
        else:
            key = (d.get("source"), d.get("page"), (d.get("text") or "")[:100])
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def _catalog_fallback_context(agent_id: str | None, retrieval_query: str, question: str) -> str:
    if agent_id != "bieu_mau":
        return ""
    try:
        from agents.catalog_service import search_forms, format_catalog_context
        forms = search_forms(retrieval_query or question, limit=8)
        return format_catalog_context(forms) or ""
    except Exception as e:
        log.warning("[grader] catalog fallback failed: %s", e)
        return ""


def _is_table_like_chunk(doc: dict) -> bool:
    dtype = (doc.get("document_type") or "")
    if dtype in ("table", "matrix"):
        return True
    text = (doc.get("text") or "")
    low = text.lower()
    if "|" in text and any(m in low for m in ("môn thi", "mon thi", "hình thức", "hinh thuc")):
        return True
    src = (doc.get("source") or "").lower()
    if "kthp" in src and ("dot2" in src or "_dot2" in src):
        return True
    if "danh-sach-thi" in src or "danh_sach_thi" in src:
        return True
    return False


def finalize_after_grading(
    question: str,
    docs: list[dict],
    trace: GradingTrace,
    *,
    agent_id: str | None,
    retrieval_query: str,
) -> tuple[list[dict], GradingTrace]:
    """
    Nếu vẫn NO: bỏ chunk rác; bieu_mau có thể bổ sung catalog vào extra_context.
    """
    if trace.sufficient:
        return docs, trace

    # Lịch thi / danh sách thi: grader hay báo NO dù chunk bảng đủ — vẫn giữ bảng cho generate
    if agent_id in ("lich_thi", "danh_sach_thi"):
        table_docs = [d for d in docs if _is_table_like_chunk(d)]
        if table_docs:
            kept = sorted(
                table_docs,
                key=lambda x: x.get("_rank_score", x.get("score", 0.0)),
                reverse=True,
            )[:8]
            trace.reason = (trace.reason or "") + " | giữ chunk bảng (grader NO)."
            log.info(
                "[grader] %s: keep %s table chunks despite NO",
                agent_id, len(kept),
            )
            return kept, trace

    extra = _catalog_fallback_context(agent_id, retrieval_query, question)
    if extra:
        trace.catalog_fallback = True
        trace.extra_context_append = extra
        trace.reason = (trace.reason or "") + " | fallback catalog biểu mẫu."

    log.info(
        "[grader] insufficient after %s requery — docs cleared (catalog=%s)",
        trace.requery_count,
        trace.catalog_fallback,
    )
    return [], trace


def corrective_retrieve(
    retriever,
    question: str,
    retrieval_query: str,
    agent_id: str | None,
    *,
    top_k: int | None = None,
) -> tuple[list[dict], float, GradingTrace]:
    """
    Retrieve + grade + requery (Corrective RAG).
    """
    k = top_k or TOP_K
    rq = (retrieval_query or question).strip()
    trace = GradingTrace(queries_used=[rq])
    t_ret_total = 0.0
    t_grader = 0.0

    docs, t = retriever.retrieve(rq, agent_id=agent_id, top_k=k)
    t_ret_total += t
    docs = _boost_schedule_docs(retriever, question, rq, agent_id, docs, k)

    if not should_use_relevance_grader(agent_id):
        trace.sufficient = bool(docs)
        trace.reason = "Grader tắt (FAST_MODE hoặc KMA_RELEVANCE_GRADER=0)."
        return docs, t_ret_total, trace

    query = rq
    for attempt in range(GRADER_MAX_REQUERY + 1):
        sufficient, reason, t_g = grade_document_relevance(
            question, docs, agent_id=agent_id,
        )
        t_grader += t_g
        trace.sufficient = sufficient
        trace.reason = reason

        if sufficient or not docs:
            break
        if attempt >= GRADER_MAX_REQUERY:
            break

        new_query = expand_search_query(question, docs, query, agent_id=agent_id)
        if new_query == query:
            break
        trace.requery_count += 1
        trace.queries_used.append(new_query)
        query = new_query
        log.info("[grader] requery #%s: %s", attempt + 1, new_query[:100])

        more, t2 = retriever.retrieve(new_query, agent_id=agent_id, top_k=k)
        t_ret_total += t2
        docs = _merge_doc_lists(docs, more)
        docs = _boost_schedule_docs(retriever, question, rq, agent_id, docs, k)
        docs = rerank_documents(question, docs, agent_id)

    trace.grader_llm_sec = round(t_grader, 3)
    docs, trace = finalize_after_grading(
        question, docs, trace, agent_id=agent_id, retrieval_query=rq,
    )
    return docs, round(t_ret_total, 3), trace
