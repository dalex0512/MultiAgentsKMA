"""
Specialist Runner — Router (Qc) + Native / Hybrid / Agentic + grade_lookup.
"""

import logging
import time
from config import (
    AGENTS, FAST_MODE, ACCURACY_MODE, MIN_RETRIEVAL_SCORE,
    USE_LOCAL_QC, QC_PREFETCH_TOP_K, ROUTER_T1, ROUTER_T2,
    USE_SCHEDULE_TABLE_FAST_PATH, SCHEDULE_FAST_PATH_AGENTS, SCHEDULE_TABLE_TOP_K,
)
from agents.complexity_estimator import assess_complexity
from agents.router import route_pipeline
from agents.catalog_service import search_forms, format_catalog_context
from agents.conversation_context import history_for_generate
from pipelines.rag_pipeline import NativeRAGPipeline, _sources_from_docs
from pipelines.agentic_pipeline import AgenticRAGPipeline
from pipelines.grade_lookup import (
    GradeLookupPipeline,
    build_grade_lookup_system,
    wants_grade_lookup,
)
from pipelines.retrieval import extract_mssv
from agents.routing_intel import INTENT_GRADE_LOOKUP
from pipelines.rag_prompts import PERSONA_ACCURACY_SUFFIX, _AGENT_ANSWER_RULES
from utils.rag.table_context import persona_suffix_for_agent
from pipelines.retrieval import top_retrieval_confidence
from utils.rag.document_grader import GradingTrace

log = logging.getLogger(__name__)

NOT_FOUND_MARKERS = ("không tìm thấy", "khong tim thay")


def _rag_call_kwargs(common: dict) -> dict:
    """Bỏ key nội bộ (vd. _assessment) trước khi gọi native/agentic/grade."""
    return {k: v for k, v in common.items() if not str(k).startswith("_")}


_SCHEDULE_QUERY_MARKERS = (
    "lịch thi", "lich thi", "kthp", "môn thi", "mon thi", "học kỳ", "hoc ky",
    "kì 1", "kì 2", "ki 1", "ki 2", "hk1", "hk2",
    "đợt thi", "dot thi", "đợt 1", "dot 1", "đợt 2", "dot 2",
    "đợt1", "đợt2", "dot1", "dot2",
    "danh sách", "danh sach", "liệt kê", "liet ke", "những môn", "các môn",
    "ngày thi", "phòng thi", "phong thi", "ca thi", "hình thức thi",
    "thời gian thi", "thoi gian thi", "bắt đầu thi", "bat dau thi",
    "thời gian bắt đầu", "thoi gian bat dau", "khi nào thi", "khi nao thi",
    "địa điểm thi", "dia diem thi", "địa điểm", "dia diem", "thi môn", "thi mon",
    "thi kết thúc học phần", "thi ket thuc hoc phan",
    "thi lại", "thi lai", "lan2", "lần 2",
    "môn nào", "mon nao", "đào tạo", "dao tao", "khoá", "khóa",
)


def _schedule_table_fast_path(
    agent_id: str,
    question: str,
    retrieval_query: str | None = None,
) -> bool:
    """PDF lịch/danh sách thi dạng bảng — retrieve + generate một lần, không grader/agentic."""
    if not USE_SCHEDULE_TABLE_FAST_PATH or agent_id not in SCHEDULE_FAST_PATH_AGENTS:
        return False
    blob = f"{question} {retrieval_query or ''}".lower()
    return any(m in blob for m in _SCHEDULE_QUERY_MARKERS)


def _user_progress_message(agent_id: str, question: str) -> str:
    """Thông báo chờ — không lộ Qc/router nội bộ."""
    from utils.rag.exam_list_lookup import wants_exam_list_query
    from utils.rag.schedule_lookup import wants_schedule_table_query

    if agent_id == "danh_sach_thi" and wants_exam_list_query(question):
        return "Đang tra cứu danh sách thi, vui lòng đợi trong giây lát..."
    if agent_id == "lich_thi" and wants_schedule_table_query(question):
        return "Đang tra cứu lịch thi, vui lòng đợi trong giây lát..."
    if agent_id == "diem_thi":
        return "Đang tra cứu bảng điểm, vui lòng đợi trong giây lát..."
    return "Đang tra cứu tài liệu, vui lòng đợi trong giây lát..."


def _apply_schedule_fast_router(
    pip,
    agent_id: str,
    question: str,
    retrieval_query: str,
):
    """Ép native_rag thay vì hybrid/agentic (tiết kiệm 3–8 phút LLM grader/agentic)."""
    from agents.routing_intel import PipelineDecision

    if not _schedule_table_fast_path(agent_id, question, retrieval_query):
        return pip
    if pip.pipeline in ("agentic_rag", "hybrid_rag"):
        note = "; lịch/danh sách bảng → native_rag (fast path, bỏ grader/agentic)"
        return PipelineDecision(
            pipeline="native_rag",
            qc=pip.qc,
            router_reason=(pip.router_reason or "") + note,
            intent=pip.intent,
        )
    return pip


def _should_grade_lookup(
    agent_id: str,
    question: str,
    retrieval_query: str,
    assessment,
) -> bool:
    """MSSV + tra điểm → luôn grade_lookup (không agentic), bất kể Qc."""
    if agent_id != "diem_thi":
        return False
    blob = f"{question} {retrieval_query or ''}"
    if not extract_mssv(blob):
        return False
    if wants_grade_lookup(agent_id, question, retrieval_query):
        return True
    return (getattr(assessment, "intent", None) or "") == INTENT_GRADE_LOOKUP


def _persona_system(agent_id: str, session_summary: str = "") -> str:
    cfg = AGENTS[agent_id]
    base = (
        f"Bạn là {cfg['name']} trong hệ thống trợ lý ảo đa tác tử KMA.\n"
        f"Chuyên môn: {cfg['description']}\n"
        "Chỉ trả lời dựa trên tài liệu và catalog được cung cấp. "
        "Nếu câu hỏi ngoài phạm vi chuyên môn, nói rõ và gợi ý sinh viên hỏi đúng mảng."
    )
    if agent_id == "bieu_mau":
        base += (
            "\nKhi sinh viên chọn biểu mẫu, có thể gợi ý gõ «điền giúp tôi» "
            "để hệ thống hỏi từng mục và tạo file Word đã điền (bản sao, không sửa file gốc)."
        )
    if agent_id == "diem_thi":
        base += (
            "\nKhi tra cứu điểm cá nhân, gửi MSSV dạng ATxxxxxx hoặc CTxxxxxx (vd. CT060310), "
            "họ tên và học kỳ/đợt (nếu có) để liệt kê đủ các môn trong bảng điểm."
        )
        base += persona_suffix_for_agent(agent_id)
    if agent_id == "ma_tran":
        base += persona_suffix_for_agent(agent_id)
    rule = _AGENT_ANSWER_RULES.get(agent_id)
    if rule:
        base += rule
    if ACCURACY_MODE:
        base += PERSONA_ACCURACY_SUFFIX
    if session_summary.strip():
        base += f"\n\nTóm tắt phiên chat trước:\n{session_summary.strip()}"
    return base


def _extra_context(agent_id: str, question: str, retrieval_query: str) -> str | None:
    if agent_id != "bieu_mau":
        return None
    forms = search_forms(retrieval_query or question, limit=6)
    return format_catalog_context(forms) or None


def _is_not_found(answer: str) -> bool:
    low = answer.lower()
    return any(m in low for m in NOT_FOUND_MARKERS)


def _should_use_grader(
    qc: float,
    agent_id: str,
    question: str = "",
    retrieval_query: str = "",
) -> bool:
    """Selective grader: chỉ grade trong hybrid zone (0.35 ≤ Qc < 0.65)."""
    if _schedule_table_fast_path(agent_id, question, retrieval_query):
        return False
    if 0.35 <= qc < 0.65:
        return True
    return False


def _attach_grader_meta(result: dict, trace: GradingTrace | None) -> dict:
    if not trace:
        return result
    result["grader_sufficient"] = trace.sufficient
    result["grader_reason"] = trace.reason
    result["grader_requery_count"] = trace.requery_count
    result["grader_catalog_fallback"] = trace.catalog_fallback
    return result


def _merge_extra_context(base: str | None, trace: GradingTrace | None) -> str | None:
    if not trace or not trace.extra_context_append:
        return base
    block = trace.extra_context_append.strip()
    if base and base.strip():
        return base.strip() + "\n\n" + block
    return block or base


def _should_escalate_agentic(
    result: dict | None = None,
    *,
    docs: list[dict] | None = None,
    confidence: float | None = None,
    grader_trace: GradingTrace | None = None,
    agent_id: str | None = None,
) -> bool:
    """Leo agentic khi thiếu tài liệu, grader NO, hoặc retrieve yếu (accuracy mode)."""
    if (
        USE_SCHEDULE_TABLE_FAST_PATH
        and agent_id in SCHEDULE_FAST_PATH_AGENTS
        and docs is not None
        and docs
    ):
        return False
    if grader_trace is not None and not grader_trace.sufficient:
        if docs and agent_id in ("lich_thi", "danh_sach_thi"):
            has_table = any(
                (d.get("document_type") or "") in ("table", "matrix") for d in docs
            )
            if has_table and top_retrieval_confidence(docs) >= 0.35:
                return False
        return True
    if result and _is_not_found(result.get("answer", "")):
        return True
    if not docs and not result:
        return False
    conf = confidence
    if conf is None and docs:
        conf = top_retrieval_confidence(docs)
    if conf is None and result:
        conf = result.get("retrieval_confidence")
    if conf is not None and MIN_RETRIEVAL_SCORE > 0 and conf < MIN_RETRIEVAL_SCORE:
        return True
    if not docs and result and MIN_RETRIEVAL_SCORE > 0:
        conf = result.get("retrieval_confidence")
        if conf is not None and conf < MIN_RETRIEVAL_SCORE:
            return True
    return False


class SpecialistRunner:
    def _assess_complexity(
        self,
        retrieval_query: str,
        complexity_query: str | None = None,
    ):
        """
        Qc trên complexity_query (đủ các ý con); prefetch S trên retrieval_query (sắp retrieve).
        """
        rq = (retrieval_query or "").strip()
        cq = (complexity_query or rq).strip()
        scores = None
        if USE_LOCAL_QC and not FAST_MODE:
            try:
                docs, _ = self.native.retrieve(
                    rq,
                    agent_id=self.agent_id,
                    top_k=QC_PREFETCH_TOP_K,
                )
                scores = [float(d.get("score", 0.0)) for d in docs]
            except Exception as e:
                log.warning(f"[specialist:{self.agent_id}] Qc prefetch failed: {e}")
        from utils.rag.schedule_lookup import wants_schedule_table_query
        from utils.rag.exam_list_lookup import wants_exam_list_query
        if self.agent_id == "danh_sach_thi" and wants_exam_list_query(cq):
            from utils.qc_calculator import assess_complexity_local
            return assess_complexity_local(cq, None)
        if _schedule_table_fast_path(self.agent_id, cq, rq):
            from utils.qc_calculator import assess_complexity_local
            if wants_schedule_table_query(cq):
                return assess_complexity_local(cq, None)
            return assess_complexity_local(cq, scores)
        return assess_complexity(cq, similarity_scores=scores)

    def _try_exam_list_direct(
        self,
        question: str,
        retrieval_query: str,
    ) -> dict | None:
        """Tra danh sách dự thi: MSSV / SBD → ca, phòng, môn — không LLM."""
        if self.agent_id != "danh_sach_thi":
            return None
        from utils.rag.exam_list_lookup import (
            wants_exam_list_query,
            fetch_exam_list_docs,
            build_exam_list_answer,
        )

        rq = (retrieval_query or question).strip()
        if not wants_exam_list_query(question):
            return None

        docs, source, t_ret = fetch_exam_list_docs(
            self.native.retriever, rq, self.agent_id,
        )
        if not docs and not source:
            return None
        answer = build_exam_list_answer(question, docs, source)
        if not answer:
            return None
        return {
            "answer": answer,
            "sources": _sources_from_docs(docs, limit=3) if docs else [],
            "t_retrieval": t_ret,
            "t_llm": 0.0,
            "n_rounds": 0,
            "retrieval_confidence": top_retrieval_confidence(docs) if docs else 0.9,
        }

    def _try_schedule_direct(
        self,
        question: str,
        retrieval_query: str,
    ) -> dict | None:
        """Liệt kê môn từ bảng KTHP — parse chunk, không LLM."""
        from utils.rag.schedule_lookup import (
            wants_schedule_table_query,
            fetch_schedule_table_docs,
            build_schedule_answer,
        )

        rq = (retrieval_query or question).strip()
        if not _schedule_table_fast_path(self.agent_id, question, rq):
            return None
        if not wants_schedule_table_query(question):
            return None

        docs, source, t_ret = fetch_schedule_table_docs(
            self.native.retriever, rq, self.agent_id,
        )
        if not docs:
            return None
        answer = build_schedule_answer(question, docs, source)
        if not answer:
            return None
        # Có answer (kể cả báo không có khóa) — không fallback LLM (tránh treo)
        return {
            "answer": answer,
            "sources": _sources_from_docs(docs, limit=3),
            "t_retrieval": t_ret,
            "t_llm": 0.0,
            "n_rounds": 0,
            "retrieval_confidence": top_retrieval_confidence(docs),
        }

    def __init__(self, agent_id: str):
        if agent_id not in AGENTS:
            raise ValueError(f"Unknown agent_id: {agent_id}")
        self.agent_id = agent_id
        self.native   = NativeRAGPipeline()
        self.agentic  = AgenticRAGPipeline()
        self.grade    = GradeLookupPipeline() if agent_id == "diem_thi" else None

    def _run_routed(
        self,
        question: str,
        pipeline: str,
        common: dict,
    ) -> tuple[dict, str]:
        """Chạy đúng pipeline Router chọn; có thể leo lên agentic_rag."""
        rq = common.get("retrieval_query") or question

        exam_direct = self._try_exam_list_direct(question, rq)
        if exam_direct is not None:
            log.info(f"[specialist:{self.agent_id}] exam_list_extract (không LLM)")
            return exam_direct, "exam_list_extract"

        from utils.rag.exam_list_lookup import wants_exam_list_query
        if self.agent_id == "danh_sach_thi" and wants_exam_list_query(question):
            return {
                "answer": (
                    "Không trích được danh sách thi từ Qdrant. "
                    "Gửi **MSSV** (vd. CT100101) hoặc **SBD** kèm **ngày thi** (vd. 22/04/2026). "
                    "Kiểm tra đã ingest thư mục `danh_sach_thi`."
                ),
                "sources": [],
                "t_retrieval": 0,
                "t_llm": 0,
                "n_rounds": 0,
            }, "exam_list_extract"

        direct = self._try_schedule_direct(question, rq)
        if direct is not None:
            log.info(f"[specialist:{self.agent_id}] schedule_extract (không LLM)")
            return direct, "schedule_extract"

        from utils.rag.schedule_lookup import wants_schedule_table_query, parse_cohort_from_query
        if _schedule_table_fast_path(self.agent_id, question, rq) and wants_schedule_table_query(question):
            log.warning(
                f"[specialist:{self.agent_id}] schedule_extract failed — "
                "không leo LLM native (tránh treo); trả thông báo ngắn",
            )
            cohort = parse_cohort_from_query(question)
            return {
                "answer": (
                    "Không trích được danh sách môn từ bảng lịch thi "
                    f"(học kỳ/đợt/khóa {cohort or ''}). "
                    "Vui lòng kiểm tra đã ingest `lich_thi` và tên file khớp HK/đợt/năm."
                ),
                "sources": [],
                "t_retrieval": 0,
                "t_llm": 0,
                "n_rounds": 0,
            }, "schedule_extract"

        if pipeline == "agentic_rag":
            return self.agentic.run(question, **_rag_call_kwargs(common)), "agentic_rag"

        if pipeline == "hybrid_rag":
            gtrace = None
            if ACCURACY_MODE or not FAST_MODE:
                assessment = self._assess_complexity(rq)
                qc = assessment.qc
                if _should_use_grader(qc, self.agent_id, question, rq):
                    log.info(f"[specialist:{self.agent_id}] using grader (qc={qc:.2f})")
                    docs, t_ret, gtrace = self.native.retrieve_graded(
                        question, rq, agent_id=self.agent_id,
                    )
                    common["extra_context"] = _merge_extra_context(
                        common.get("extra_context"), gtrace,
                    )
                    if _should_escalate_agentic(
                        docs=docs, grader_trace=gtrace, agent_id=self.agent_id,
                    ):
                        log.info(f"[specialist:{self.agent_id}] hybrid → agentic (grader/retrieve yếu)")
                        return self.agentic.run(question, **_rag_call_kwargs(common)), "agentic_rag"
                    result = _attach_grader_meta(
                        self.native.run(
                            question,
                            **_rag_call_kwargs(common),
                            prefetched_docs=docs,
                            prefetched_t_retrieval=t_ret,
                        ),
                        gtrace,
                    )
                else:
                    log.info(f"[specialist:{self.agent_id}] skipping grader (qc={qc:.2f})")
                    result = self.native.run(question, **_rag_call_kwargs(common))
            else:
                result = self.native.run(question, **_rag_call_kwargs(common))
            if _should_escalate_agentic(
                result, grader_trace=gtrace, agent_id=self.agent_id,
            ):
                log.info(f"[specialist:{self.agent_id}] hybrid → agentic (không đủ context)")
                return self.agentic.run(question, **_rag_call_kwargs(common)), "agentic_rag"
            return result, "hybrid_rag"

        # native_rag
        gtrace = None
        if ACCURACY_MODE:
            docs, t_ret, gtrace = self.native.retrieve_graded(
                question, rq, agent_id=self.agent_id,
            )
            common["extra_context"] = _merge_extra_context(
                common.get("extra_context"), gtrace,
            )
            if _should_escalate_agentic(
                docs=docs, grader_trace=gtrace, agent_id=self.agent_id,
            ):
                log.info(f"[specialist:{self.agent_id}] native → agentic (grader/retrieve yếu)")
                return self.agentic.run(question, **_rag_call_kwargs(common)), "agentic_rag"
            result = _attach_grader_meta(
                self.native.run(
                    question,
                    **_rag_call_kwargs(common),
                    prefetched_docs=docs,
                    prefetched_t_retrieval=t_ret,
                ),
                gtrace,
            )
        else:
            result = self.native.run(question, **_rag_call_kwargs(common))
        if _should_escalate_agentic(result, agent_id=self.agent_id):
            log.info(f"[specialist:{self.agent_id}] native → agentic (không đủ context)")
            return self.agentic.run(question, **_rag_call_kwargs(common)), "agentic_rag"
        return result, "native_rag"

    def _stream_routed(
        self,
        question: str,
        pipeline: str,
        common: dict,
    ):
        """
        Stream theo pipeline Router chọn.
        Trả về generator; pipeline thực tế có thể đổi thành agentic_rag khi leo thang.
        """
        rq = common.get("retrieval_query") or question

        exam_direct = self._try_exam_list_direct(question, rq)
        if exam_direct is not None:
            log.info(f"[specialist:{self.agent_id}] stream exam_list_extract (không LLM)")
            t0 = time.perf_counter()
            yield {"type": "progress", "message": "Đang tra cứu danh sách thi..."}
            yield {
                "type": "info",
                "t_retrieval": exam_direct["t_retrieval"],
                "sources": exam_direct.get("sources", []),
            }
            yield {"type": "delta", "content": exam_direct["answer"]}
            yield {
                "type": "done",
                "t_total": round(time.perf_counter() - t0, 3),
                "t_retrieval": exam_direct["t_retrieval"],
                "t_llm": 0.0,
                "n_rounds": 0,
                "pipeline": "exam_list_extract",
            }
            return

        from utils.rag.exam_list_lookup import wants_exam_list_query
        if self.agent_id == "danh_sach_thi" and wants_exam_list_query(question):
            msg = (
                "Không trích được danh sách thi. Gửi **MSSV** hoặc **SBD** kèm ngày thi "
                "(vd. 22/04/2026). Kiểm tra ingest `danh_sach_thi`."
            )
            yield {"type": "progress", "message": "Đang tra cứu danh sách thi..."}
            yield {"type": "info", "t_retrieval": 0, "sources": []}
            yield {"type": "delta", "content": msg}
            yield {"type": "done", "t_total": 0, "t_retrieval": 0, "t_llm": 0, "n_rounds": 0, "pipeline": "exam_list_extract"}
            return

        direct = self._try_schedule_direct(question, rq)
        if direct is not None:
            log.info(f"[specialist:{self.agent_id}] stream schedule_extract (không LLM)")
            t0 = time.perf_counter()
            yield {"type": "progress", "message": "Đang liệt kê môn thi từ bảng lịch..."}
            yield {
                "type": "info",
                "t_retrieval": direct["t_retrieval"],
                "sources": direct["sources"],
            }
            yield {"type": "delta", "content": direct["answer"]}
            yield {
                "type": "done",
                "t_total": round(time.perf_counter() - t0, 3),
                "t_retrieval": direct["t_retrieval"],
                "t_llm": 0.0,
                "n_rounds": 0,
                "pipeline": "schedule_extract",
            }
            return

        from utils.rag.schedule_lookup import wants_schedule_table_query, parse_cohort_from_query
        if _schedule_table_fast_path(self.agent_id, question, rq) and wants_schedule_table_query(question):
            cohort = parse_cohort_from_query(question)
            msg = (
                "Không trích được danh sách môn từ bảng lịch thi "
                f"(học kỳ/đợt/khóa {cohort or ''}). "
                "Vui lòng kiểm tra đã ingest `lich_thi` và tên file khớp HK/đợt/năm."
            )
            yield {"type": "progress", "message": "Đang tra cứu lịch thi..."}
            yield {"type": "info", "t_retrieval": 0, "sources": []}
            yield {"type": "delta", "content": msg}
            yield {"type": "done", "t_total": 0, "t_retrieval": 0, "t_llm": 0, "n_rounds": 0, "pipeline": "schedule_extract"}
            return

        if pipeline == "agentic_rag":
            yield from self._wrap_stream(self.agentic.run_stream(question, **_rag_call_kwargs(common)), "agentic_rag")
            return

        if pipeline == "hybrid_rag" and (ACCURACY_MODE or not FAST_MODE):
            assessment = common.get("_assessment")
            if assessment is None:
                assessment = self._assess_complexity(rq)
            qc = assessment.qc
            if _should_use_grader(qc, self.agent_id, question, rq):
                log.info(f"[specialist:{self.agent_id}] stream using grader (qc={qc:.2f})")
                yield {
                    "type": "progress",
                    "message": "Đang tìm tài liệu và kiểm tra độ liên quan...",
                }
                docs, t_ret, gtrace = self.native.retrieve_graded(
                    question, rq, agent_id=self.agent_id,
                )
            else:
                log.info(f"[specialist:{self.agent_id}] stream skipping grader (qc={qc:.2f})")
                docs, t_ret = self.native.retrieve(rq, agent_id=self.agent_id)
                gtrace = None
            common["extra_context"] = _merge_extra_context(
                common.get("extra_context"), gtrace,
            )
            if _should_escalate_agentic(
                docs=docs, grader_trace=gtrace, agent_id=self.agent_id,
            ):
                log.info(f"[specialist:{self.agent_id}] hybrid stream → agentic (grader/retrieve yếu)")
                yield from self._wrap_stream(
                    self.agentic.run_stream(question, **_rag_call_kwargs(common)), "agentic_rag",
                )
                return
            yield from self._wrap_stream(
                self.native.run_stream(
                    question,
                    **_rag_call_kwargs(common),
                    prefetched_docs=docs,
                    prefetched_t_retrieval=t_ret,
                ),
                "hybrid_rag",
            )
            return

        if pipeline == "native_rag" and ACCURACY_MODE:
            docs, t_ret, gtrace = self.native.retrieve_graded(
                question, rq, agent_id=self.agent_id,
            )
            common["extra_context"] = _merge_extra_context(
                common.get("extra_context"), gtrace,
            )
            if _should_escalate_agentic(
                docs=docs, grader_trace=gtrace, agent_id=self.agent_id,
            ):
                log.info(f"[specialist:{self.agent_id}] native stream → agentic (grader/retrieve yếu)")
                yield from self._wrap_stream(
                    self.agentic.run_stream(question, **_rag_call_kwargs(common)), "agentic_rag",
                )
                return
            yield from self._wrap_stream(
                self.native.run_stream(
                    question,
                    **_rag_call_kwargs(common),
                    prefetched_docs=docs,
                    prefetched_t_retrieval=t_ret,
                ),
                "native_rag",
            )
            return

        label = "native_rag" if pipeline == "native_rag" else pipeline
        yield from self._wrap_stream(self.native.run_stream(question, **_rag_call_kwargs(common)), label)

    @staticmethod
    def _wrap_stream(gen, pipeline_label: str):
        for event in gen:
            if event.get("type") == "done":
                event["pipeline"] = pipeline_label
            yield event

    @staticmethod
    def _qc_debug_fields(assessment) -> dict:
        """Breakdown Qc khi gần ngưỡng Router — hỗ trợ debug độ chính xác."""
        qc = assessment.qc
        margin = 0.06
        if not (ROUTER_T1 - margin <= qc <= ROUTER_T1 + margin
                or ROUTER_T2 - margin <= qc <= ROUTER_T2 + margin):
            return {}
        reason = assessment.reason or ""
        if "[" in reason and "]" in reason:
            return {"qc_breakdown": reason.split("[", 1)[-1].rstrip("]")}
        return {"qc_near_threshold": True, "qc": qc}

    def _run_pipeline(
        self,
        question: str,
        history: list[dict] | None,
        *,
        retrieval_query: str | None = None,
        complexity_query: str | None = None,
        session_summary: str = "",
        supervisor_intent: str = "",
        supervisor_confidence: float = 1.0,
        planner_used: bool = False,
    ) -> dict:
        rq       = (retrieval_query or question).strip()
        gen_hist = history_for_generate(history or [])
        assessment = self._assess_complexity(rq, complexity_query)
        pip        = route_pipeline(
            assessment,
            supervisor_intent=supervisor_intent,
            supervisor_confidence=supervisor_confidence,
            planner_used=planner_used,
        )
        pip        = _apply_schedule_fast_router(pip, self.agent_id, question, rq)
        qc         = pip.qc
        pipeline   = pip.pipeline
        system   = _persona_system(self.agent_id, session_summary)
        extra    = _extra_context(self.agent_id, question, rq)

        if self.grade and _should_grade_lookup(self.agent_id, question, rq, assessment):
            log.info(f"[specialist:{self.agent_id}] grade_lookup (qc={qc})")
            result = self.grade.run(
                question,
                history=gen_hist,
                retrieval_query=rq,
                system_prompt=build_grade_lookup_system(session_summary),
            )
            result["pipeline"]          = "grade_lookup"
            result["qc"]              = qc
            result["router_reason"]     = f"grade_lookup (MSSV/điểm): {assessment.reason}"
            result["complexity_intent"] = assessment.intent
            result["agent_id"]        = self.agent_id
            result["agent_name"]      = AGENTS[self.agent_id]["name"]
            return result

        log.info(f"[specialist:{self.agent_id}] {pip.router_reason}")

        common = dict(
            history=gen_hist,
            agent_id=self.agent_id,
            retrieval_query=rq,
            system_prompt=system,
            extra_context=extra,
        )

        result, pipeline_used = self._run_routed(question, pipeline, common)
        result["pipeline"]         = pipeline_used
        result["qc"]               = qc
        result["router_reason"]    = pip.router_reason
        result["complexity_intent"] = assessment.intent
        result["agent_id"]         = self.agent_id
        result["agent_name"]       = AGENTS[self.agent_id]["name"]
        result.update(self._qc_debug_fields(assessment))
        return result

    def run(
        self,
        question: str,
        history: list[dict] | None = None,
        *,
        retrieval_query: str | None = None,
        complexity_query: str | None = None,
        session_summary: str = "",
        supervisor_intent: str = "",
        supervisor_confidence: float = 1.0,
        planner_used: bool = False,
    ) -> dict:
        return self._run_pipeline(
            question, history,
            retrieval_query=retrieval_query,
            complexity_query=complexity_query,
            session_summary=session_summary,
            supervisor_intent=supervisor_intent,
            supervisor_confidence=supervisor_confidence,
            planner_used=planner_used,
        )

    def run_stream(
        self,
        question: str,
        history: list[dict] | None = None,
        *,
        retrieval_query: str | None = None,
        complexity_query: str | None = None,
        session_summary: str = "",
        supervisor_intent: str = "",
        supervisor_confidence: float = 1.0,
        planner_used: bool = False,
    ):
        rq       = (retrieval_query or question).strip()
        gen_hist = history_for_generate(history or [])
        yield {"type": "progress", "message": _user_progress_message(self.agent_id, question)}
        assessment = self._assess_complexity(rq, complexity_query)
        pip        = route_pipeline(
            assessment,
            supervisor_intent=supervisor_intent,
            supervisor_confidence=supervisor_confidence,
            planner_used=planner_used,
        )
        pip        = _apply_schedule_fast_router(pip, self.agent_id, question, rq)
        qc         = pip.qc
        pipeline   = pip.pipeline
        system   = _persona_system(self.agent_id, session_summary)
        extra    = _extra_context(self.agent_id, question, rq)

        use_grade = self.grade and _should_grade_lookup(
            self.agent_id, question, rq, assessment,
        )
        if use_grade:
            pipeline = "grade_lookup"
            pip_router_reason = f"grade_lookup (MSSV/điểm): {assessment.reason}"
        else:
            pip_router_reason = pip.router_reason

        yield {
            "type":              "agent_start",
            "agent_id":          self.agent_id,
            "agent_name":        AGENTS[self.agent_id]["name"],
            "pipeline":          pipeline,
            "qc":                qc,
            "router_reason":     pip_router_reason,
            "complexity_intent": assessment.intent,
        }

        common = dict(
            history=gen_hist,
            agent_id=self.agent_id,
            retrieval_query=rq,
            system_prompt=system,
            extra_context=extra,
            _assessment=assessment,
        )

        if use_grade:
            pipeline_used = "grade_lookup"
            log.info(f"[specialist:{self.agent_id}] grade_lookup stream (qc={qc})")
            for event in self.grade.run_stream(
                question,
                history=gen_hist,
                retrieval_query=rq,
                system_prompt=build_grade_lookup_system(session_summary),
            ):
                if event["type"] == "done":
                    event["pipeline"]          = pipeline_used
                    event["qc"]                = qc
                    event["agent_id"]            = self.agent_id
                    event["router_reason"]     = f"grade_lookup (MSSV/điểm): {assessment.reason}"
                    event["complexity_intent"] = assessment.intent
                yield event
            return

        log.info(f"[specialist:{self.agent_id}] stream {pip.router_reason}")

        for event in self._stream_routed(question, pipeline, common):
            if event["type"] == "done":
                event["qc"]                = qc
                event["agent_id"]            = self.agent_id
                event["router_reason"]     = pip.router_reason
                event["complexity_intent"] = assessment.intent
            yield event
