"""
Router thích ứng theo tải — bảo vệ SSE / OpenAI rate limit khi quá nhiều kết nối.
"""

from __future__ import annotations

import logging

from config import (
    LOAD_ROUTER_MAX_CONNECTIONS,
    ROUTER_T1,
    ROUTER_T2,
    USE_LOAD_ROUTER,
)
from agents.routing_intel import ComplexityAssessment, PipelineDecision

log = logging.getLogger(__name__)


def get_adaptive_pipeline_decision(
    qc: float,
    active_connections: int,
) -> dict:
    """
    Quyết định pipeline theo Qc và tải hệ thống.

    Returns:
        pipeline: native_rag | hybrid_rag | agentic_rag
        is_degraded: bool
        reason: str
        qc: float (echo)
    """
    qc = float(qc)
    active = int(active_connections)

    if active > LOAD_ROUTER_MAX_CONNECTIONS:
        return {
            "pipeline": "native_rag",
            "is_degraded": True,
            "reason": (
                f"Hệ thống quá tải ({active}>{LOAD_ROUTER_MAX_CONNECTIONS} kết nối): "
                "ép native_rag để giải phóng hàng đợi."
            ),
            "qc": qc,
            "active_connections": active,
        }

    if qc < ROUTER_T1:
        pipeline = "native_rag"
    elif qc < ROUTER_T2:
        pipeline = "hybrid_rag"
    else:
        pipeline = "agentic_rag"

    return {
        "pipeline": pipeline,
        "is_degraded": False,
        "reason": (
            f"Qc={qc:.2f} → {pipeline} "
            f"(ngưỡng native<{ROUTER_T1}, hybrid<{ROUTER_T2}, "
            f"active={active})."
        ),
        "qc": qc,
        "active_connections": active,
    }


def apply_load_adaptive_decision(
    assessment: ComplexityAssessment,
    base: PipelineDecision,
    active_connections: int,
) -> PipelineDecision:
    """
    Áp dụng load router lên quyết định từ route_pipeline (intent tweaks).
    Khi degraded: override pipeline; giữ qc/intent từ assessment.
    """
    if not USE_LOAD_ROUTER:
        return base

    dec = get_adaptive_pipeline_decision(assessment.qc, active_connections)
    pipeline = dec["pipeline"]
    notes = [dec["reason"]]

    if not dec["is_degraded"]:
        # Không degraded: vẫn tôn trọng intent nâng từ router.py (base.pipeline)
        pipeline = base.pipeline
        notes = [base.router_reason, dec["reason"]]
    else:
        log.warning("[load_router] %s", dec["reason"])

    router_reason = "Load-adaptive: " + "; ".join(notes)
    return PipelineDecision(
        pipeline=pipeline,
        qc=assessment.qc,
        router_reason=router_reason,
        intent=assessment.intent,
    )
