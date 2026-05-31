"""
Hybrid RAG System (legacy single-bot).

Đồ án dùng pipelines.multi_agent_system.MultiAgentSystem làm entry point.
File này giữ để tham chiếu / thử nghiệm pipeline Router Agent đơn lẻ.
"""

import time
import logging
from dataclasses import dataclass, field

from agents.complexity_estimator import estimate
from agents.router               import route
from pipelines.rag_pipeline      import NativeRAGPipeline
from pipelines.agentic_pipeline  import AgenticRAGPipeline

log = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    answer:      str
    pipeline:    str
    qc:          float
    t_total:     float
    t_retrieval: float
    t_llm:       float
    n_rounds:    int
    sources:     list = field(default_factory=list)


class HybridRAGSystem:
    def __init__(self):
        self.native  = NativeRAGPipeline()
        self.agentic = AgenticRAGPipeline()
        log.info("HybridRAGSystem ready")

    def chat_stream(self, question: str, history: list[dict] | None = None):
        qc       = estimate(question)
        pipeline = route(qc)
        t0       = time.perf_counter()
        history  = (history or [])[-6:]   # cap 6 lượt gần nhất

        yield {"type": "start", "pipeline": pipeline, "qc": qc}

        if pipeline in ("native_rag", "hybrid_rag"):
            gen = self.native.run_stream(question, history=history)
        else:
            gen = self.agentic.run_stream(question, history=history)

        for event in gen:
            if event["type"] == "done":
                event["pipeline"] = pipeline
                event["qc"]       = qc
                event["t_total"]  = round(time.perf_counter() - t0, 3)
            yield event

    def chat(self, question: str, history: list[dict] | None = None) -> ChatResponse:
        t0      = time.perf_counter()
        history = (history or [])[-6:]

        # Complexity + routing
        qc       = estimate(question)
        pipeline = route(qc)
        log.info(f"[hybrid] qc={qc} → {pipeline}")

        # Dispatch
        if pipeline == "native_rag":
            result = self.native.run(question, history=history)
        elif pipeline == "hybrid_rag":
            result = self.native.run(question, history=history)
            if "không tìm thấy" in result["answer"].lower():
                result   = self.agentic.run(question, history=history)
                pipeline = "agentic_rag"
        else:
            result = self.agentic.run(question, history=history)

        return ChatResponse(
            answer      = result["answer"],
            pipeline    = pipeline,
            qc          = qc,
            t_total     = round(time.perf_counter() - t0, 3),
            t_retrieval = result["t_retrieval"],
            t_llm       = result["t_llm"],
            n_rounds    = result["n_rounds"],
            sources     = result.get("sources", []),
        )
