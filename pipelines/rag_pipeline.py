"""
Native RAG Pipeline — retrieve (có filter agent_id) → generate
"""

import time
import logging
from openai import OpenAI
from config import OPENAI_API_KEY, LLM_MODEL, LLM_MAX_TOKENS
from pipelines.retrieval import QdrantRetriever, top_sources_for_display, top_retrieval_confidence
from utils.rag.document_grader import GradingTrace, corrective_retrieve, should_use_relevance_grader
from pipelines.rag_prompts import build_rag_user_prompt
from utils.rag.table_context import build_context_header, persona_suffix_for_docs

log = logging.getLogger(__name__)


def _sources_from_docs(docs: list[dict], limit: int = 3) -> list[dict]:
    picked = top_sources_for_display(docs, limit=limit)
    return [
        {
            "source":       d["source"],
            "page":         d["page"],
            "score":        round(d.get("_rank_score", d["score"]), 4),
            "display_name": d.get("display_name", ""),
            "download_url": d.get("download_url", ""),
            "agent_id":     d.get("agent_id", ""),
        }
        for d in picked
    ]


class NativeRAGPipeline:
    def __init__(self):
        self.openai    = OpenAI(api_key=OPENAI_API_KEY)
        self.retriever = QdrantRetriever()

    def retrieve(
        self,
        query: str,
        *,
        agent_id: str | None = None,
        top_k: int | None = None,
    ) -> tuple[list[dict], float]:
        from config import TOP_K
        k = top_k or TOP_K
        return self.retriever.retrieve(query, agent_id=agent_id, top_k=k)

    def retrieve_graded(
        self,
        question: str,
        query: str,
        *,
        agent_id: str | None = None,
        top_k: int | None = None,
    ) -> tuple[list[dict], float, GradingTrace | None]:
        """
        Retrieve + Document Relevance Grader (ý tưởng 6).
        Qc prefetch vẫn dùng retrieve() thuần để tránh thêm LLM.
        """
        if should_use_relevance_grader(agent_id):
            docs, t_ret, trace = corrective_retrieve(
                self.retriever,
                question,
                query,
                agent_id,
                top_k=top_k,
            )
            return docs, t_ret, trace
        docs, t_ret = self.retrieve(query, agent_id=agent_id, top_k=top_k)
        return docs, t_ret, None

    @staticmethod
    def _merge_extra(extra_context: str | None, trace: GradingTrace | None) -> str | None:
        if not trace or not trace.extra_context_append:
            return extra_context
        block = trace.extra_context_append.strip()
        if extra_context and extra_context.strip():
            return extra_context.strip() + "\n\n" + block
        return block or extra_context

    def generate(
        self,
        question: str,
        docs: list[dict],
        history: list[dict] | None = None,
        *,
        agent_id: str | None = None,
        system_prompt: str | None = None,
        extra_context: str | None = None,
    ) -> tuple[str, float]:
        ctx_header = build_context_header(docs)
        context = ctx_header + "\n\n".join(
            f"[{i+1}] (Nguồn: {d['source']} tr.{d['page']}"
            f"{'' if not d.get('document_type') else ' | ' + d['document_type']})\n{d['text']}"
            for i, d in enumerate(docs)
        )
        if extra_context:
            context = extra_context.strip() + "\n\n" + context
        table_suffix = persona_suffix_for_docs(docs, agent_id)
        if system_prompt and table_suffix and table_suffix not in system_prompt:
            system_prompt = system_prompt + table_suffix
        elif table_suffix and not system_prompt:
            system_prompt = table_suffix.strip()

        prompt = build_rag_user_prompt(context, question)
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history or [])
        messages.append({"role": "user", "content": prompt})

        t0 = time.perf_counter()
        resp = self.openai.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.0,
        )
        answer = resp.choices[0].message.content.strip()
        return answer, round(time.perf_counter() - t0, 3)

    def run_stream(
        self,
        question: str,
        history: list[dict] | None = None,
        *,
        agent_id: str | None = None,
        retrieval_query: str | None = None,
        system_prompt: str | None = None,
        extra_context: str | None = None,
        prefetched_docs: list[dict] | None = None,
        prefetched_t_retrieval: float | None = None,
    ):
        t0 = time.perf_counter()
        rq = (retrieval_query or question).strip()
        grading_trace = None
        if prefetched_docs is not None:
            docs, t_retrieval = prefetched_docs, (prefetched_t_retrieval or 0.0)
        else:
            docs, t_retrieval, grading_trace = self.retrieve_graded(
                question, rq, agent_id=agent_id,
            )
        extra_context = self._merge_extra(extra_context, grading_trace)
        sources = _sources_from_docs(docs)

        yield {"type": "info", "t_retrieval": t_retrieval, "sources": sources}

        ctx_header = build_context_header(docs)
        context = ctx_header + "\n\n".join(
            f"[{i+1}] (Nguồn: {d['source']} tr.{d['page']}"
            f"{'' if not d.get('document_type') else ' | ' + d['document_type']})\n{d['text']}"
            for i, d in enumerate(docs)
        )
        if extra_context:
            context = extra_context.strip() + "\n\n" + context
        table_suffix = persona_suffix_for_docs(docs, agent_id)
        if system_prompt and table_suffix and table_suffix not in system_prompt:
            system_prompt = system_prompt + table_suffix
        elif table_suffix and not system_prompt:
            system_prompt = table_suffix.strip()

        prompt = build_rag_user_prompt(context, question)
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history or [])
        messages.append({"role": "user", "content": prompt})

        t_llm_start = time.perf_counter()
        stream = self.openai.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.0,
            stream=True,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield {"type": "delta", "content": content}

        done_ev = {
            "type":        "done",
            "t_total":     round(time.perf_counter() - t0, 3),
            "t_retrieval": t_retrieval,
            "t_llm":       round(time.perf_counter() - t_llm_start, 3),
            "n_rounds":    1,
        }
        if grading_trace:
            done_ev["grader_sufficient"] = grading_trace.sufficient
            done_ev["grader_reason"] = grading_trace.reason
            done_ev["grader_requery_count"] = grading_trace.requery_count
        yield done_ev

    def run(
        self,
        question: str,
        history: list[dict] | None = None,
        *,
        agent_id: str | None = None,
        retrieval_query: str | None = None,
        system_prompt: str | None = None,
        extra_context: str | None = None,
        prefetched_docs: list[dict] | None = None,
        prefetched_t_retrieval: float | None = None,
    ) -> dict:
        t0 = time.perf_counter()
        rq = (retrieval_query or question).strip()
        grading_trace = None
        if prefetched_docs is not None:
            docs, t_retrieval = prefetched_docs, (prefetched_t_retrieval or 0.0)
        else:
            docs, t_retrieval, grading_trace = self.retrieve_graded(
                question, rq, agent_id=agent_id,
            )
        extra_context = self._merge_extra(extra_context, grading_trace)
        answer, t_llm = self.generate(
            question, docs, history=history,
            agent_id=agent_id,
            system_prompt=system_prompt,
            extra_context=extra_context,
        )
        out = {
            "answer":              answer,
            "t_total":             round(time.perf_counter() - t0, 3),
            "t_retrieval":         t_retrieval,
            "t_llm":               t_llm,
            "n_rounds":            1,
            "n_docs":              len(docs),
            "sources":             _sources_from_docs(docs),
            "retrieval_confidence": top_retrieval_confidence(docs),
        }
        if grading_trace:
            out["grader_sufficient"] = grading_trace.sufficient
            out["grader_reason"] = grading_trace.reason
            out["grader_requery_count"] = grading_trace.requery_count
            out["grader_catalog_fallback"] = grading_trace.catalog_fallback
        return out
