"""
Agentic-RAG Pipeline — plan → retrieve → evaluate → requery → generate
Hỗ trợ filter theo agent_id (Multi-Agent).
"""

import time
import logging
from openai import OpenAI
from config import OPENAI_API_KEY, LLM_MODEL, MAX_ROUNDS, LLM_MAX_TOKENS, ACCURACY_MODE
from pipelines.rag_prompts import build_rag_user_prompt
from pipelines.retrieval import QdrantRetriever, rerank_documents, top_sources_for_display
from utils.rag.document_grader import (
    expand_search_query,
    grade_document_relevance,
)
from utils.rag.table_context import build_context_header, persona_suffix_for_docs

log = logging.getLogger(__name__)

PLAN_PROMPT = """\
Bạn cần trả lời câu hỏi sau về Học viện Kỹ thuật Mật mã (KMA).
Hãy tạo một truy vấn tìm kiếm ngắn (5-10 từ) để tìm thông tin liên quan.
Chỉ trả lời bằng truy vấn tìm kiếm, không giải thích.

Câu hỏi: {question}
Truy vấn tìm kiếm:"""

# EVAL/REQUERY dùng chung utils.rag.document_grader (ý tưởng 6)

# GENERATE dùng build_rag_user_prompt() — đồng bộ với Native + chế độ accuracy


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


class AgenticRAGPipeline:
    def __init__(self):
        self.openai    = OpenAI(api_key=OPENAI_API_KEY)
        self.retriever = QdrantRetriever()

    def _llm(self, prompt: str, max_tokens: int = 512) -> tuple[str, float]:
        t0 = time.perf_counter()
        resp = self.openai.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.0,
        )
        return resp.choices[0].message.content.strip(), round(time.perf_counter() - t0, 3)

    def _chunk_excerpt(self, text: str) -> str:
        if ACCURACY_MODE:
            return text
        return text[:400]

    def _build_context(self, docs: list[dict]) -> str:
        header = build_context_header(docs)
        body = "\n\n".join(
            f"[{i+1}] (Nguồn: {d['source']} tr.{d['page']}"
            f"{'' if not d.get('document_type') else ' | ' + d['document_type']})\n"
            f"{self._chunk_excerpt(d['text'])}"
            for i, d in enumerate(docs)
        )
        return header + body

    def _prepare(
        self,
        question: str,
        *,
        agent_id: str | None = None,
        retrieval_query: str | None = None,
    ) -> tuple[list[dict], float, float, int]:
        t_retrieval = 0.0
        t_llm       = 0.0
        all_docs: list[dict] = []

        rq = (retrieval_query or question).strip()
        query, t = self._llm(PLAN_PROMPT.format(question=rq), max_tokens=32)
        t_llm += t
        if not query.strip():
            query = rq

        round_num = 1
        for round_num in range(1, MAX_ROUNDS + 1):
            docs, t = self.retriever.retrieve(query, agent_id=agent_id)
            t_retrieval += t
            all_docs.extend(docs)

            seen, unique = set(), []
            for d in all_docs:
                key = d["text"][:80]
                if key not in seen:
                    seen.add(key)
                    unique.append(d)
            all_docs = rerank_documents(question, unique)

            slice_docs = all_docs[-10:]
            sufficient, reason, t_g = grade_document_relevance(question, slice_docs)
            t_llm += t_g
            log.debug(
                f"[agentic] agent={agent_id} round={round_num} sufficient={sufficient} ({reason[:60]})"
            )

            if sufficient or round_num == MAX_ROUNDS:
                break

            query = expand_search_query(question, slice_docs, query)
            if not query.strip():
                break

        top_docs = sorted(
            all_docs,
            key=lambda x: x.get("_rank_score", x["score"]),
            reverse=True,
        )[:8]
        top_docs = rerank_documents(question, top_docs)[:8]
        return top_docs, t_retrieval, t_llm, round_num

    def _build_messages(
        self,
        question: str,
        top_docs: list[dict],
        history: list[dict] | None,
        system_prompt: str | None,
        extra_context: str | None,
        agent_id: str | None = None,
    ) -> list[dict]:
        context = self._build_context(top_docs)
        if extra_context:
            context = extra_context.strip() + "\n\n" + context

        prompt = build_rag_user_prompt(context, question)
        suffix = persona_suffix_for_docs(top_docs, agent_id)
        if system_prompt and suffix and suffix not in system_prompt:
            system_prompt = system_prompt + suffix
        elif suffix and not system_prompt:
            system_prompt = suffix.strip()

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history or [])
        messages.append({"role": "user", "content": prompt})
        return messages

    def run_stream(
        self,
        question: str,
        history: list[dict] | None = None,
        *,
        agent_id: str | None = None,
        retrieval_query: str | None = None,
        system_prompt: str | None = None,
        extra_context: str | None = None,
    ):
        t0 = time.perf_counter()
        yield {
            "type": "progress",
            "message": "Đang tra cứu tài liệu chi tiết, vui lòng đợi trong giây lát...",
        }
        top_docs, t_retrieval, t_llm, round_num = self._prepare(
            question, agent_id=agent_id, retrieval_query=retrieval_query,
        )
        sources = _sources_from_docs(top_docs)

        yield {"type": "info", "t_retrieval": t_retrieval, "sources": sources}

        messages = self._build_messages(
            question, top_docs, history, system_prompt, extra_context, agent_id,
        )
        t_llm_gen = time.perf_counter()
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

        t_llm += round(time.perf_counter() - t_llm_gen, 3)
        yield {
            "type":        "done",
            "t_total":     round(time.perf_counter() - t0, 3),
            "t_retrieval": t_retrieval,
            "t_llm":       t_llm,
            "n_rounds":    round_num,
        }

    def run(
        self,
        question: str,
        history: list[dict] | None = None,
        *,
        agent_id: str | None = None,
        retrieval_query: str | None = None,
        system_prompt: str | None = None,
        extra_context: str | None = None,
    ) -> dict:
        t0 = time.perf_counter()
        top_docs, t_retrieval, t_llm, round_num = self._prepare(
            question, agent_id=agent_id, retrieval_query=retrieval_query,
        )

        messages = self._build_messages(
            question, top_docs, history, system_prompt, extra_context, agent_id,
        )
        t0_llm = time.perf_counter()
        resp = self.openai.chat.completions.create(
            model=LLM_MODEL, messages=messages, max_tokens=LLM_MAX_TOKENS, temperature=0.0,
        )
        answer = resp.choices[0].message.content.strip()
        t_llm += round(time.perf_counter() - t0_llm, 3)

        return {
            "answer":      answer,
            "t_total":     round(time.perf_counter() - t0, 3),
            "t_retrieval": t_retrieval,
            "t_llm":       t_llm,
            "n_rounds":    round_num,
            "n_docs":      len(top_docs),
            "sources":     _sources_from_docs(top_docs),
        }
