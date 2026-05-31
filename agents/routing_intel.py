"""
Metadata điều phối — intent + lý do routing (Supervisor / Router).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ComplexityAssessment:
    qc: float
    score_0_10: int
    intent: str
    needs_multi_doc: bool
    reason: str


@dataclass
class PipelineDecision:
    pipeline: str
    qc: float
    router_reason: str
    intent: str = ""


# Intent Router / Complexity (tiếng Việt, slug ASCII)
INTENT_FACTUAL = "fact_lookup"       # một fact: tên, số, ngày
INTENT_LIST = "list_enumerate"       # liệt kê, có bao nhiêu
INTENT_COMPARE = "compare"          # so sánh, khác nhau
INTENT_MULTI_HOP = "multi_hop"       # nhiều bước / nhiều nguồn
INTENT_PROCEDURAL = "procedural"    # quy trình, thủ tục, các bước
INTENT_GRADE_LOOKUP = "grade_lookup"  # điểm, MSSV, bảng điểm

VALID_COMPLEXITY_INTENTS = {
    INTENT_FACTUAL, INTENT_LIST, INTENT_COMPARE,
    INTENT_MULTI_HOP, INTENT_PROCEDURAL, INTENT_GRADE_LOOKUP,
}

# Intent Supervisor
SUP_INTENT_SINGLE = "single_domain"
SUP_INTENT_MULTI = "multi_domain"
SUP_INTENT_FORM = "form_procedure"
SUP_INTENT_GRADE = "grade_result"
