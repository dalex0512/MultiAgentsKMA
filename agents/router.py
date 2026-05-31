"""
Router Agent — chọn pipeline RAG theo Qc + intent (Complexity Assessment).

  Qc < THRESHOLD1  → native_rag
  Qc < THRESHOLD2  → hybrid_rag
  Qc >= THRESHOLD2 → agentic_rag

Leo thang khi thiếu context: specialist_runner.py
"""

from __future__ import annotations

from config import ROUTER_T1, ROUTER_T2, USE_LOAD_ROUTER, ACCURACY_MODE
from agents.routing_intel import INTENT_LIST
from api.connection_tracker import get_active_chat_connections
from config import SUPERVISOR_LOW_CONFIDENCE
from agents.routing_intel import (
    ComplexityAssessment,
    PipelineDecision,
    INTENT_COMPARE,
    INTENT_GRADE_LOOKUP,
    INTENT_MULTI_HOP,
    INTENT_PROCEDURAL,
    SUP_INTENT_FORM,
    SUP_INTENT_GRADE,
    SUP_INTENT_MULTI,
)


def apply_supervisor_pipeline_hint(
    decision: PipelineDecision,
    *,
    supervisor_intent: str = "",
    supervisor_confidence: float = 1.0,
) -> PipelineDecision:
    """Nâng pipeline tối thiểu theo intent Supervisor (ưu tiên chính xác)."""
    if not supervisor_intent and supervisor_confidence >= SUPERVISOR_LOW_CONFIDENCE:
        return decision

    pipeline = decision.pipeline
    notes: list[str] = []

    if supervisor_intent == SUP_INTENT_GRADE and pipeline == "native_rag":
        pipeline = "hybrid_rag"
        notes.append("supervisor grade_result → hybrid_rag")
    elif supervisor_intent == SUP_INTENT_FORM and pipeline == "native_rag":
        pipeline = "hybrid_rag"
        notes.append("supervisor form_procedure → hybrid_rag")
    elif supervisor_intent == SUP_INTENT_MULTI:
        if pipeline == "native_rag":
            pipeline = "hybrid_rag"
            notes.append("supervisor multi_domain → hybrid_rag")
        elif pipeline == "hybrid_rag":
            pipeline = "agentic_rag"
            notes.append("supervisor multi_domain → agentic_rag")

    if supervisor_confidence < SUPERVISOR_LOW_CONFIDENCE and pipeline == "native_rag":
        pipeline = "hybrid_rag"
        notes.append(f"supervisor conf<{SUPERVISOR_LOW_CONFIDENCE} → hybrid_rag")

    if not notes:
        return decision

    return PipelineDecision(
        pipeline=pipeline,
        qc=decision.qc,
        router_reason=decision.router_reason + "; " + "; ".join(notes),
        intent=decision.intent,
    )


def route(qc: float) -> str:
    """Chỉ theo ngưỡng Qc (tương thích cũ)."""
    if qc < ROUTER_T1:
        return "native_rag"
    if qc < ROUTER_T2:
        return "hybrid_rag"
    return "agentic_rag"


def apply_accuracy_answer_policy(
    decision: PipelineDecision,
    assessment: ComplexityAssessment,
    *,
    planner_used: bool = False,
) -> PipelineDecision:
    """
    Sàn pipeline khi ACCURACY_MODE — ưu tiên câu trả lời đúng, không tiết kiệm native.
    """
    if not ACCURACY_MODE:
        return decision

    pipeline = decision.pipeline
    intent = assessment.intent
    notes: list[str] = []

    if planner_used:
        if pipeline in ("native_rag", "hybrid_rag"):
            pipeline = "agentic_rag"
            notes.append("accuracy: planner nhiều ý → agentic_rag")
    elif assessment.needs_multi_doc and pipeline == "native_rag":
        pipeline = "hybrid_rag"
        notes.append("accuracy: cần nhiều tài liệu → hybrid_rag")
    elif intent == INTENT_MULTI_HOP and pipeline != "agentic_rag":
        pipeline = "agentic_rag"
        notes.append("accuracy: multi_hop → agentic_rag")
    elif intent in (INTENT_COMPARE, INTENT_PROCEDURAL, INTENT_LIST) and pipeline == "native_rag":
        pipeline = "hybrid_rag"
        notes.append(f"accuracy: intent {intent} → hybrid_rag")
    elif intent in (INTENT_COMPARE, INTENT_LIST) and pipeline == "hybrid_rag":
        pipeline = "agentic_rag"
        notes.append(f"accuracy: intent {intent} → agentic_rag")

    if not notes:
        return decision

    return PipelineDecision(
        pipeline=pipeline,
        qc=decision.qc,
        router_reason=decision.router_reason + "; " + "; ".join(notes),
        intent=decision.intent,
    )


def route_pipeline(
    assessment: ComplexityAssessment,
    *,
    supervisor_intent: str = "",
    supervisor_confidence: float = 1.0,
    planner_used: bool = False,
) -> PipelineDecision:
    """
    Chọn pipeline + lý do giải thích (ăn điểm đồ án — routing có căn cứ).
    Có thể điều chỉnh nhẹ theo intent nhưng vẫn tôn trọng ngưỡng Qc.
    """
    qc = assessment.qc
    intent = assessment.intent
    base = route(qc)
    pipeline = base
    notes: list[str] = [
        f"Qc={qc:.2f} (điểm LLM {assessment.score_0_10}/10)",
        f"intent={intent}",
        f"ngưỡng native<{ROUTER_T1}, hybrid<{ROUTER_T2}",
    ]

    # Điều chỉnh có kiểm soát — không phá 3 vùng ngưỡng
    if intent == INTENT_MULTI_HOP and pipeline == "hybrid_rag":
        pipeline = "agentic_rag"
        notes.append("intent multi_hop → nâng lên agentic_rag")
    elif intent in (INTENT_COMPARE, INTENT_PROCEDURAL) and pipeline == "native_rag" and qc >= 0.32:
        pipeline = "hybrid_rag"
        notes.append(f"intent {intent} → nâng native thành hybrid_rag")
    elif intent == INTENT_GRADE_LOOKUP and pipeline == "native_rag" and assessment.needs_multi_doc:
        pipeline = "hybrid_rag"
        notes.append("grade_lookup nhiều tài liệu → hybrid_rag")

    reason = assessment.reason
    router_reason = (
        f"Router chọn {pipeline}: " + "; ".join(notes)
        + (f". {reason}" if reason else "")
    )
    decision = PipelineDecision(
        pipeline=pipeline,
        qc=qc,
        router_reason=router_reason,
        intent=intent,
    )

    decision = apply_supervisor_pipeline_hint(
        decision,
        supervisor_intent=supervisor_intent,
        supervisor_confidence=supervisor_confidence,
    )

    decision = apply_accuracy_answer_policy(
        decision,
        assessment,
        planner_used=planner_used,
    )

    if USE_LOAD_ROUTER:
        from utils.load_adaptive_router import apply_load_adaptive_decision
        decision = apply_load_adaptive_decision(
            assessment,
            decision,
            get_active_chat_connections(),
        )

    return decision


def route_label(qc: float) -> str:
    return f"{route(qc)} (qc={qc:.3f}, t1={ROUTER_T1}, t2={ROUTER_T2})"
