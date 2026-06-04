"""
Multi-Agent System — Memory + Planner + Supervisor → Specialists → Aggregator.
"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from config import AGENTS, AGENT_IDS, USE_KMA_TEXT_NORM
from agents.supervisor import route as supervisor_route, RoutingDecision, _grade_policy_compound_primary
from agents.routing_intel import SUP_INTENT_MULTI
from agents.aggregator import ResponseAggregator
from agents.query_rewriter import rewrite
from agents.planner import plan_questions, PlanResult
from agents.session_memory import session_store
from agents.conversation_context import trim_history
from agents.guardrail import check_scope
from pipelines.specialist_runner import SpecialistRunner
from agents.form_filler import form_fill_service, FormFillState
from agents.student_profile import StudentProfile

log = logging.getLogger(__name__)


@dataclass
class TurnContext:
    question:          str
    retrieval_query:   str
    was_rewritten:     bool
    history:           list[dict]
    session_id:        str | None
    session_summary:   str
    session_turn:      int = 0


@dataclass
class ExecutionPlan:
    decision:          RoutingDecision
    agent_tasks:       dict[str, list[str]]   # agent_id -> sub-questions
    sub_questions:     list[str]
    planner_used:      bool
    planner_reason:    str


@dataclass
class ChatResponse:
    answer:            str
    agents_used:       list[str] = field(default_factory=list)
    agent_names:       list[str] = field(default_factory=list)
    primary_agent:     str = ""
    supervisor_reason:     str = ""
    supervisor_intent:     str = ""
    supervisor_confidence: float = 0.0
    router_reason:         str = ""
    complexity_intent:     str = ""
    pipeline:              str = ""
    qc:                    float = 0.0
    t_total:           float = 0.0
    t_retrieval:       float = 0.0
    t_llm:             float = 0.0
    n_rounds:          int = 1
    sources:           list = field(default_factory=list)
    per_agent:         list = field(default_factory=list)
    session_id:        str = ""
    retrieval_query:   str = ""
    was_rewritten:     bool = False
    session_turn:      int = 0
    sub_questions:     list[str] = field(default_factory=list)
    planner_used:      bool = False
    planner_reason:    str = ""
    in_scope:          bool = True
    scope_category:    str = "kma"


class MultiAgentSystem:
    def __init__(self):
        self.aggregator = ResponseAggregator()
        self.runners    = {aid: SpecialistRunner(aid) for aid in AGENT_IDS}
        log.info("MultiAgentSystem ready — memory + planner")

    def create_session(self) -> str:
        return session_store.create()

    @staticmethod
    def _chat_response_to_dict(resp: ChatResponse) -> dict:
        return {
            "answer": resp.answer,
            "agents_used": resp.agents_used,
            "agent_names": resp.agent_names,
            "primary_agent": resp.primary_agent,
            "supervisor_reason": resp.supervisor_reason,
            "supervisor_intent": resp.supervisor_intent,
            "supervisor_confidence": resp.supervisor_confidence,
            "router_reason": resp.router_reason,
            "complexity_intent": resp.complexity_intent,
            "pipeline": resp.pipeline,
            "qc": resp.qc,
            "t_total": resp.t_total,
            "t_retrieval": resp.t_retrieval,
            "t_llm": resp.t_llm,
            "n_rounds": resp.n_rounds,
            "sources": resp.sources,
            "per_agent": resp.per_agent,
            "session_id": resp.session_id,
            "retrieval_query": resp.retrieval_query,
            "was_rewritten": resp.was_rewritten,
            "session_turn": resp.session_turn,
            "sub_questions": resp.sub_questions,
            "planner_used": resp.planner_used,
            "planner_reason": resp.planner_reason,
            "in_scope": resp.in_scope,
            "scope_category": resp.scope_category,
        }

    def _cache_response(self, question: str, session_id: str | None, resp: ChatResponse):
        if not session_id or resp.pipeline in ("guardrail", "form_fill"):
            return
        st = session_store.get(session_id)
        if st:
            st.cache_query_result(question.strip(), self._chat_response_to_dict(resp))

    def _prepare_turn(
        self,
        question: str,
        history: list[dict] | None,
        session_id: str | None,
    ) -> TurnContext:
        question = question.strip()
        if USE_KMA_TEXT_NORM:
            from utils.text.kma_text_processor import preprocess_student_query
            question = preprocess_student_query(question)
        history  = trim_history(history)

        sid = (session_id or "").strip() or None
        if sid and not session_store.get(sid):
            log.warning(f"[session] unknown id {sid[:8]}, creating new")
            sid = None
        if not sid:
            sid = session_store.create()

        state   = session_store.get(sid)
        summary = state.summary if state else ""
        turn    = state.turn_count if state else 0
        rw      = rewrite(question, history, summary)

        return TurnContext(
            question=question,
            retrieval_query=rw.retrieval_query,
            was_rewritten=rw.was_rewritten,
            history=history,
            session_id=sid,
            session_summary=summary,
            session_turn=turn,
        )

    def _build_execution_plan(self, ctx: TurnContext) -> ExecutionPlan:
        plan = plan_questions(
            ctx.retrieval_query,
            history=ctx.history,
            session_summary=ctx.session_summary,
        )

        agent_tasks: dict[str, list[str]] = {}

        if plan.use_decomposition and len(plan.sub_questions) > 1:
            for sq in plan.sub_questions:
                d = supervisor_route(
                    sq,
                    history=ctx.history,
                    session_summary=ctx.session_summary,
                )
                for aid in d.agents:
                    agent_tasks.setdefault(aid, []).append(sq)
            decision = supervisor_route(
                ctx.retrieval_query,
                history=ctx.history,
                session_summary=ctx.session_summary,
            )
            reason = f"{plan.reason} | Supervisor: {decision.reason}"
        else:
            decision = supervisor_route(
                ctx.retrieval_query,
                history=ctx.history,
                session_summary=ctx.session_summary,
            )
            for aid in decision.agents:
                agent_tasks[aid] = [ctx.retrieval_query]
            reason = decision.reason
            if len(plan.sub_questions) != 1 or plan.sub_questions[0] != ctx.retrieval_query:
                plan = PlanResult(
                    sub_questions=[ctx.retrieval_query],
                    use_decomposition=False,
                    reason=plan.reason,
                )

        return ExecutionPlan(
            decision=self._finalize_decision(
                decision, agent_tasks, ctx.retrieval_query, reason,
            ),
            agent_tasks=agent_tasks,
            sub_questions=plan.sub_questions,
            planner_used=plan.use_decomposition,
            planner_reason=plan.reason,
        )

    @staticmethod
    def _finalize_decision(
        decision: RoutingDecision,
        agent_tasks: dict[str, list[str]],
        retrieval_query: str,
        reason: str = "",
    ) -> RoutingDecision:
        """Đồng bộ agents/intent/primary khi planner tách nhiều mảng."""
        merged_reason = reason or decision.reason
        agents = list(agent_tasks.keys())
        if len(agents) >= 2:
            primary = decision.primary
            if "diem_thi" in agents and "khao_thi" in agents:
                primary = _grade_policy_compound_primary(retrieval_query)
            elif primary not in agents:
                primary = agents[0]
            return RoutingDecision(
                agents=agents,
                primary=primary,
                reason=merged_reason,
                intent=SUP_INTENT_MULTI,
                confidence=decision.confidence,
            )
        if agents:
            return RoutingDecision(
                agents=agents,
                primary=decision.primary if decision.primary in agents else agents[0],
                reason=merged_reason,
                intent=decision.intent,
                confidence=decision.confidence,
            )
        return decision

    def _combined_question(self, ctx: TurnContext, sub_qs: list[str]) -> str:
        if len(sub_qs) == 1:
            return ctx.question
        parts = "\n".join(f"{i+1}. {q}" for i, q in enumerate(sub_qs))
        return (
            f"Câu hỏi gốc: {ctx.question}\n\n"
            f"Trả lời đầy đủ các ý sau (dựa trên tài liệu KMA):\n{parts}"
        )

    def _combined_retrieval_query(self, sub_qs: list[str], agent_id: str | None = None) -> str:
        """Một sub-q giữ nguyên; nhiều ý cùng agent → câu dài nhất (tránh embedding loãng)."""
        if len(sub_qs) == 1:
            return sub_qs[0]
        if agent_id == "khao_thi":
            policy_qs = [
                q for q in sub_qs
                if any(m in q.lower() for m in (
                    "toeic", "vstep", "chuẩn ngoại ngữ", "chuan ngoai ngu",
                    "quy chế", "quy che", "đồ án", "do an", "de tai do an",
                ))
            ]
            if policy_qs:
                return max(policy_qs, key=lambda s: len(s.split()))
        if agent_id == "diem_thi":
            grade_qs = [
                q for q in sub_qs
                if not any(m in q.lower() for m in (
                    "toeic", "vstep", "chuẩn ngoại ngữ", "chuan ngoai ngu",
                    "quy chế", "quy che",
                )) or any(m in q.lower() for m in (
                    "at", "ct", "dt", "phân loại", "phan loai", "kết quả", "ket qua",
                ))
            ]
            if grade_qs:
                return max(grade_qs, key=lambda s: len(s.split()))
        return max(sub_qs, key=lambda s: len(s.split()))

    def _complexity_query_for_agent(self, sub_qs: list[str], ctx: TurnContext) -> str:
        """Qc / hybrid LLM: đủ các ý con của agent; câu gốc nếu planner tách nhiều mảng."""
        if len(sub_qs) == 1:
            return sub_qs[0]
        return f"{ctx.question.strip()} | " + " | ".join(sub_qs)

    def _run_specialists(self, ctx: TurnContext, exe: ExecutionPlan) -> list[dict]:
        sk_base = {
            "history": ctx.history,
            "session_summary": ctx.session_summary,
        }
        agents = exe.decision.agents

        def _run_one(aid: str) -> dict:
            sub_qs = exe.agent_tasks.get(aid, [ctx.retrieval_query])
            kwargs = {
                **sk_base,
                "retrieval_query": self._combined_retrieval_query(sub_qs, aid),
                "complexity_query": self._complexity_query_for_agent(sub_qs, ctx),
                "supervisor_intent": exe.decision.intent,
                "supervisor_confidence": exe.decision.confidence,
                "planner_used": exe.planner_used,
            }
            q = self._combined_question(ctx, sub_qs)
            return self.runners[aid].run(q, **kwargs)

        if len(agents) <= 1:
            return [_run_one(agents[0])]

        order = {aid: i for i, aid in enumerate(agents)}
        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=min(3, len(agents))) as pool:
            futs = {pool.submit(_run_one, aid): aid for aid in agents}
            for fut in as_completed(futs):
                results.append(fut.result())
        results.sort(key=lambda r: order.get(r["agent_id"], 99))
        return results

    def _normalize_answer(self, ctx: TurnContext, answer: str) -> str:
        if not USE_KMA_TEXT_NORM or not answer:
            return answer
        from utils.text.kma_text_processor import (
            looks_like_boolean_question,
            normalize_boolean_output,
        )
        if looks_like_boolean_question(ctx.question) or len(answer.strip()) <= 48:
            return normalize_boolean_output(answer)
        return answer

    def _finish_turn(self, ctx: TurnContext, answer: str, agents_used: list[str]):
        answer = self._normalize_answer(ctx, answer)
        session_store.after_turn(
            ctx.session_id,
            question=ctx.question,
            answer=answer,
            agents_used=agents_used,
            history=ctx.history,
        )

    def _try_form_fill(self, ctx: TurnContext, t0: float) -> ChatResponse | None:
        st = session_store.get(ctx.session_id)
        ff: FormFillState | None = None
        if st and getattr(st, "form_fill", None):
            ff = st.form_fill
        elif st and st.last_form_filename and form_fill_service.wants_fill(ctx.question, None):
            ff = FormFillState(filename=st.last_form_filename)

        if not form_fill_service.wants_fill(ctx.question, ff):
            return None

        profile = (
            st.student_profile
            if st and getattr(st, "student_profile", None)
            else StudentProfile()
        )
        answer, new_ff, extra, profile = form_fill_service.handle(
            ctx.question,
            ctx.history,
            ctx.session_id or "",
            ff,
            last_form_filename=st.last_form_filename if st else "",
            student_profile=profile,
        )
        if not answer:
            return None

        if st:
            st.form_fill = new_ff
            st.student_profile = profile
            if new_ff and new_ff.filename:
                st.last_form_filename = new_ff.filename
            if new_ff and new_ff.status == "done":
                st.form_fill = FormFillState(filename=new_ff.filename)

        self._finish_turn(ctx, answer, ["bieu_mau"])
        st2 = session_store.get(ctx.session_id)
        resp = ChatResponse(
            answer=answer,
            agents_used=["bieu_mau"],
            agent_names=[AGENTS["bieu_mau"]["name"]],
            primary_agent="bieu_mau",
            supervisor_reason="Form fill workflow",
            pipeline="form_fill",
            qc=1.0,
            t_total=round(time.perf_counter() - t0, 3),
            t_retrieval=0.0,
            t_llm=0.0,
            n_rounds=0,
            sources=[],
            per_agent=[{
                "agent_id": "bieu_mau",
                "agent_name": AGENTS["bieu_mau"]["name"],
                "pipeline": "form_fill",
                "qc": 1.0,
            }],
            session_id=ctx.session_id or "",
            retrieval_query=ctx.retrieval_query,
            was_rewritten=ctx.was_rewritten,
            session_turn=st2.turn_count if st2 else 0,
        )
        if extra and extra.get("form_download_url"):
            resp.sources = [{
                "source":       new_ff.filename if new_ff else "",
                "page":         0,
                "score":        1.0,
                "display_name": extra.get("form_download_name", "Đơn đã điền"),
                "download_url": extra["form_download_url"],
                "agent_id":     "bieu_mau",
            }]
        return resp

    def _guardrail_response(self, ctx: TurnContext, scope, t0: float) -> ChatResponse:
        self._finish_turn(ctx, scope.answer, [])
        st = session_store.get(ctx.session_id)
        return ChatResponse(
            answer=scope.answer,
            agents_used=[],
            agent_names=[],
            primary_agent="",
            supervisor_reason=f"Guardrail: {scope.category}",
            pipeline="guardrail",
            qc=0.0,
            t_total=round(time.perf_counter() - t0, 3),
            t_retrieval=0.0,
            t_llm=0.0,
            n_rounds=0,
            sources=[],
            per_agent=[],
            session_id=ctx.session_id or "",
            retrieval_query=ctx.retrieval_query,
            was_rewritten=ctx.was_rewritten,
            session_turn=st.turn_count if st else 0,
            in_scope=False,
            scope_category=scope.category,
        )

    def _merge_sources(self, results: list[dict]) -> list[dict]:
        seen, out = set(), []
        for r in results:
            for s in r.get("sources", []):
                key = (s.get("source"), s.get("page"), s.get("download_url"))
                if key not in seen:
                    seen.add(key)
                    out.append(s)
        return out[:12]

    def _build_response(
        self,
        ctx: TurnContext,
        exe: ExecutionPlan,
        results: list[dict],
        answer: str,
        t0: float,
        agg_t: float = 0.0,
    ) -> ChatResponse:
        st = session_store.get(ctx.session_id)
        agents_used = exe.decision.agents
        pipeline = "multi_agent" if len(results) > 1 else results[0]["pipeline"]
        primary_r = results[0] if len(results) == 1 else next(
            (r for r in results if r["agent_id"] == exe.decision.primary),
            results[0],
        )

        sup = exe.decision
        answer = self._normalize_answer(ctx, answer)
        return ChatResponse(
            answer=answer,
            agents_used=agents_used,
            agent_names=[r["agent_name"] for r in results],
            primary_agent=sup.primary,
            supervisor_reason=sup.reason,
            supervisor_intent=sup.intent,
            supervisor_confidence=sup.confidence,
            router_reason=primary_r.get("router_reason", ""),
            complexity_intent=primary_r.get("complexity_intent", ""),
            pipeline=pipeline,
            qc=primary_r["qc"],
            t_total=round(time.perf_counter() - t0, 3),
            t_retrieval=round(sum(r["t_retrieval"] for r in results), 3),
            t_llm=round(sum(r["t_llm"] for r in results) + agg_t, 3),
            n_rounds=max(r["n_rounds"] for r in results),
            sources=self._merge_sources(results),
            per_agent=[{
                "agent_id":          r["agent_id"],
                "agent_name":        r["agent_name"],
                "pipeline":          r["pipeline"],
                "qc":                r["qc"],
                "router_reason":     r.get("router_reason", ""),
                "complexity_intent": r.get("complexity_intent", ""),
            } for r in results],
            session_id=ctx.session_id or "",
            retrieval_query=ctx.retrieval_query,
            was_rewritten=ctx.was_rewritten,
            session_turn=st.turn_count if st else 0,
            sub_questions=exe.sub_questions,
            planner_used=exe.planner_used,
            planner_reason=exe.planner_reason,
        )

    def chat(
        self,
        question: str,
        history: list[dict] | None = None,
        session_id: str | None = None,
    ) -> ChatResponse:
        t0 = time.perf_counter()
        q_stripped = question.strip()
        sid_early = (session_id or "").strip() or None

        if sid_early:
            st_early = session_store.get(sid_early)
            if st_early:
                cached_result = st_early.get_cached_query_result(q_stripped)
                if cached_result:
                    cached = dict(cached_result)
                    cached["t_total"] = round(time.perf_counter() - t0, 3)
                    return ChatResponse(**cached)

        with ThreadPoolExecutor(max_workers=3) as pool:
            turn_fut = pool.submit(
                self._prepare_turn,
                question, history, session_id,
            )
            scope_fut = pool.submit(
                check_scope,
                q_stripped,
                history=history or [],
                session_summary="",
                session_id=sid_early,
            )
            ctx = turn_fut.result()
            scope_fut.result()

        scope = check_scope(
            ctx.retrieval_query,
            history=ctx.history,
            session_summary=ctx.session_summary,
            session_id=ctx.session_id,
        )

        form_resp = self._try_form_fill(ctx, t0)
        if form_resp:
            return form_resp

        if not scope.in_scope and scope.answer:
            return self._guardrail_response(ctx, scope, t0)

        exe = self._build_execution_plan(ctx)
        results = self._run_specialists(ctx, exe)

        if len(results) == 1:
            self._finish_turn(ctx, results[0]["answer"], exe.decision.agents)
            resp = self._build_response(ctx, exe, results, results[0]["answer"], t0)
            self._cache_response(q_stripped, ctx.session_id, resp)
            return resp

        agg_answer, agg_t = self.aggregator.aggregate(
            ctx.question, results, session_summary=ctx.session_summary,
        )
        self._finish_turn(ctx, agg_answer, exe.decision.agents)
        resp = self._build_response(ctx, exe, results, agg_answer, t0, agg_t)
        self._cache_response(q_stripped, ctx.session_id, resp)
        return resp

    def chat_stream(
        self,
        question: str,
        history: list[dict] | None = None,
        session_id: str | None = None,
    ):
        t0  = time.perf_counter()
        ctx = self._prepare_turn(question, history, session_id)

        form_resp = self._try_form_fill(ctx, t0)
        if form_resp:
            yield {
                "type":           "start",
                "agents_used":    form_resp.agents_used,
                "agent_names":    form_resp.agent_names,
                "in_scope":       True,
                "scope_category": "kma",
                "primary_agent":  form_resp.primary_agent,
                "supervisor_reason": form_resp.supervisor_reason,
                "session_id":     form_resp.session_id,
                "retrieval_query": form_resp.retrieval_query,
                "was_rewritten":  form_resp.was_rewritten,
                "session_turn":   form_resp.session_turn,
            }
            yield {
                "type":        "info",
                "t_retrieval": 0,
                "sources":     form_resp.sources,
                "pipeline":    "form_fill",
            }
            yield {"type": "delta", "content": form_resp.answer}
            yield {
                "type":       "done",
                "pipeline":   "form_fill",
                "qc":         1.0,
                "t_total":    form_resp.t_total,
                "t_retrieval": 0,
                "t_llm":      0,
                "n_rounds":   0,
                "session_id": form_resp.session_id,
            }
            return

        scope = check_scope(
            ctx.retrieval_query,
            history=ctx.history,
            session_summary=ctx.session_summary,
            session_id=ctx.session_id,
        )
        if not scope.in_scope and scope.answer:
            yield {
                "type":           "start",
                "agents_used":    [],
                "agent_names":    [],
                "in_scope":       False,
                "scope_category": scope.category,
                "session_id":     ctx.session_id or "",
                "retrieval_query": ctx.retrieval_query,
                "was_rewritten":  ctx.was_rewritten,
                "session_turn":   ctx.session_turn,
            }
            yield {"type": "info", "t_retrieval": 0, "sources": []}
            yield {"type": "delta", "content": scope.answer}
            self._finish_turn(ctx, scope.answer, [])
            st = session_store.get(ctx.session_id)
            yield {
                "type":           "done",
                "pipeline":       "guardrail",
                "qc":             0,
                "t_total":        round(time.perf_counter() - t0, 3),
                "t_retrieval":    0,
                "t_llm":          0,
                "n_rounds":       0,
                "session_id":     ctx.session_id or "",
                "scope_category": scope.category,
            }
            return

        exe = self._build_execution_plan(ctx)

        yield {
            "type":              "start",
            "agents_used":       exe.decision.agents,
            "in_scope":          True,
            "scope_category":    "kma",
            "agent_names":       [AGENTS[a]["name"] for a in exe.decision.agents],
            "primary_agent":     exe.decision.primary,
            "supervisor_reason":     exe.decision.reason,
            "supervisor_intent":     exe.decision.intent,
            "supervisor_confidence": exe.decision.confidence,
            "session_id":            ctx.session_id or "",
            "retrieval_query":       ctx.retrieval_query,
            "was_rewritten":         ctx.was_rewritten,
            "session_turn":          ctx.session_turn,
            "planner_used":          exe.planner_used,
            "planner_reason":        exe.planner_reason,
            "sub_questions":         exe.sub_questions,
        }

        if exe.planner_used:
            yield {
                "type":          "plan",
                "sub_questions": exe.sub_questions,
                "reason":        exe.planner_reason,
            }

        full_answer = ""

        if len(exe.decision.agents) == 1:
            aid = exe.decision.agents[0]
            sub_qs = exe.agent_tasks.get(aid, [ctx.retrieval_query])
            sk = {
                "history": ctx.history,
                "session_summary": ctx.session_summary,
                "retrieval_query": self._combined_retrieval_query(sub_qs, aid),
                "complexity_query": self._complexity_query_for_agent(sub_qs, ctx),
                "supervisor_intent": exe.decision.intent,
                "supervisor_confidence": exe.decision.confidence,
                "planner_used": exe.planner_used,
            }
            q = self._combined_question(ctx, sub_qs)
            pipeline, qc = "", 0.0
            router_reason, complexity_intent = "", ""

            for event in self.runners[aid].run_stream(q, **sk):
                if event.get("type") == "progress":
                    yield event
                    continue
                elif event.get("type") == "agent_start":
                    pipeline = event.get("pipeline", "")
                    qc = event.get("qc", 0.0)
                    router_reason = event.get("router_reason", "")
                    complexity_intent = event.get("complexity_intent", "")
                    yield {
                        "type":              "routing",
                        "agent_id":          aid,
                        "agent_name":        event.get("agent_name"),
                        "pipeline":          pipeline,
                        "qc":                qc,
                        "router_reason":     router_reason,
                        "complexity_intent": complexity_intent,
                    }
                elif event["type"] == "delta":
                    full_answer += event.get("content", "")
                elif event["type"] == "done":
                    pipeline = event.get("pipeline") or pipeline
                    router_reason = event.get("router_reason") or router_reason
                    complexity_intent = event.get("complexity_intent") or complexity_intent
                    event["agents_used"]       = exe.decision.agents
                    event["agent_names"]       = [AGENTS[a]["name"] for a in exe.decision.agents]
                    event["primary_agent"]     = exe.decision.primary
                    event["supervisor_reason"]     = exe.decision.reason
                    event["supervisor_intent"]     = exe.decision.intent
                    event["supervisor_confidence"] = exe.decision.confidence
                    event["router_reason"]         = router_reason
                    event["complexity_intent"]     = complexity_intent
                    event["pipeline"]              = pipeline
                    event["qc"]                    = event.get("qc", qc)
                    event["t_total"]               = round(time.perf_counter() - t0, 3)
                    event["session_id"]            = ctx.session_id or ""
                yield event

            if full_answer:
                self._finish_turn(ctx, full_answer, exe.decision.agents)
            return

        results = []
        for aid in exe.decision.agents:
            yield {
                "type":       "agent_working",
                "agent_id":   aid,
                "agent_name": AGENTS[aid]["name"],
            }
            sub_qs = exe.agent_tasks.get(aid, [ctx.retrieval_query])
            sk = {
                "history": ctx.history,
                "session_summary": ctx.session_summary,
                "retrieval_query": self._combined_retrieval_query(sub_qs, aid),
                "complexity_query": self._complexity_query_for_agent(sub_qs, ctx),
                "supervisor_intent": exe.decision.intent,
                "supervisor_confidence": exe.decision.confidence,
                "planner_used": exe.planner_used,
            }
            q = self._combined_question(ctx, sub_qs)
            results.append(self.runners[aid].run(q, **sk))

        yield {
            "type":        "info",
            "t_retrieval": round(sum(x["t_retrieval"] for x in results), 3),
            "sources":     self._merge_sources(results),
            "per_agent":   [{
                "agent_id":          x["agent_id"],
                "pipeline":          x["pipeline"],
                "qc":                x["qc"],
                "router_reason":     x.get("router_reason", ""),
                "complexity_intent": x.get("complexity_intent", ""),
            } for x in results],
        }

        for chunk in self.aggregator.aggregate_stream(
            ctx.question, results, session_summary=ctx.session_summary,
        ):
            full_answer += chunk
            yield {"type": "delta", "content": chunk}

        self._finish_turn(ctx, full_answer, exe.decision.agents)
        primary_r = next(
            (r for r in results if r["agent_id"] == exe.decision.primary),
            results[0],
        )
        st = session_store.get(ctx.session_id)
        yield {
            "type":              "done",
            "pipeline":          "multi_agent",
            "qc":                primary_r["qc"],
            "t_total":           round(time.perf_counter() - t0, 3),
            "t_retrieval":       round(sum(x["t_retrieval"] for x in results), 3),
            "t_llm":             round(sum(x["t_llm"] for x in results), 3),
            "n_rounds":          max(x["n_rounds"] for x in results),
            "agents_used":       exe.decision.agents,
            "agent_names":       [AGENTS[a]["name"] for a in exe.decision.agents],
            "primary_agent":     exe.decision.primary,
            "supervisor_reason":     exe.decision.reason,
            "supervisor_intent":     exe.decision.intent,
            "supervisor_confidence": exe.decision.confidence,
            "router_reason":         primary_r.get("router_reason", ""),
            "complexity_intent":     primary_r.get("complexity_intent", ""),
            "session_id":            ctx.session_id or "",
            "session_turn":          st.turn_count if st else 0,
        }
