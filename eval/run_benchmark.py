"""
Chạy benchmark JSON qua POST /chat — chấm Supervisor, Router pipeline, nội dung.

Usage:
  python eval/run_benchmark.py
  python eval/run_benchmark.py --tier L1
  python eval/run_benchmark.py --id L1-01
  python eval/run_benchmark.py --ids L0-05,L1-09,L3-01
  python eval/run_benchmark.py --ids-file eval/failed_retest_ids.txt
  python eval/run_benchmark.py --from-id L3-01 --timeout 900
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
BENCHMARK = Path(__file__).parent / "benchmark.json"
RESULTS_DIR = Path(__file__).parent / "results"

TIER_TIMEOUT_DEFAULT = {
    "L0": 90,
    "L1": 180,
    "L2": 300,
    "L3": 420,
    "L4": 600,
    "L5": 420,
    "L6": 300,
}


def timeout_for_case(case: dict, override: int | None) -> int:
    if override and override > 0:
        return override
    tier = case.get("tier", "L1")
    base = TIER_TIMEOUT_DEFAULT.get(tier, 240)
    if case.get("multi_turn"):
        return int(base * 1.2)
    return base


def post_chat(base_url: str, question: str, history: list, session_id: str, timeout: int = 300) -> dict:
    body = json.dumps({
        "question": question,
        "history": history,
        "session_id": session_id,
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_server(base_url: str, timeout: int = 5) -> None:
    """Dừng sớm nếu API chưa chạy (tránh 100 lần Connection refused)."""
    url = f"{base_url.rstrip('/')}/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise urllib.error.URLError(f"HTTP {resp.status}")
    except urllib.error.URLError as e:
        print(
            f"\nKhông kết nối được tới {base_url}\n"
            f"  Lỗi: {e}\n\n"
            "Benchmark cần server FastAPI đang chạy. Mở terminal khác:\n\n"
            "  cd D:\\DATN\\kma_rag\\demo\n"
            "  .\\.venv\\Scripts\\activate\n"
            "  uvicorn api.main:app --host 127.0.0.1 --port 8000\n\n"
            "Sau đó mở http://127.0.0.1:8000/ — thấy trang chat rồi chạy lại:\n"
            "  python eval/run_benchmark.py\n",
            file=sys.stderr,
        )
        sys.exit(2)


def new_session(base_url: str) -> str:
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/session/new",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))["session_id"]


import re


def _normalize_match(text: str) -> str:
    return re.sub(r"[\s.,']", "", (text or "").lower())


def _term_in_text(term: str, text: str) -> bool:
    if not term:
        return True
    if term.lower() in (text or "").lower():
        return True
    return _normalize_match(term) in _normalize_match(text)


def contains_any(text: str, terms: list[str]) -> bool:
    if not terms:
        return True
    return any(_term_in_text(t, text) for t in terms)


def contains_all(text: str, terms: list[str]) -> bool:
    if not terms:
        return True
    return all(_term_in_text(t, text) for t in terms)


def agents_match(actual: list[str], expected: list[str], *, exact: bool = False) -> bool:
    if not expected:
        return not actual
    if exact:
        return set(actual) == set(expected)
    return set(expected).issubset(set(actual))


def pipeline_match(resp: dict, pipe_any: list[str]) -> bool:
    if not pipe_any:
        return True
    root = resp.get("pipeline", "")
    if root in pipe_any:
        return True
    per = resp.get("per_agent") or []
    if any(p.get("pipeline", "") in pipe_any for p in per):
        return True
    return False


def per_agent_pipeline_match(resp: dict, specs: list[dict]) -> bool:
    """Mỗi agent kỳ vọng phải có pipeline thuộc pipeline_any của nó."""
    per = {p.get("agent_id"): p.get("pipeline", "") for p in (resp.get("per_agent") or [])}
    if not per and len(specs) == 1 and resp.get("agents_used"):
        aid = specs[0]["agent_id"]
        if aid in resp.get("agents_used", []):
            per[aid] = resp.get("pipeline", "")
    for spec in specs:
        aid = spec["agent_id"]
        allowed = spec.get("pipeline_any", [])
        if aid not in per:
            return False
        if allowed and per[aid] not in allowed:
            return False
    return True


def merge_turn_expected(global_exp: dict, turn_exp: dict) -> dict:
    """Gộp expected — turn ưu tiên; guardrail off-topic không kế thừa agents global."""
    out = {**global_exp, **turn_exp}
    if turn_exp.get("in_scope") is False or turn_exp.get("scope_category") == "off_topic":
        out["agents"] = turn_exp.get("agents", [])
        out.pop("primary", None)
        out.pop("agents_exact", None)
        out.pop("min_agents", None)
    return out


def score_turn(
    resp: dict,
    expected: dict,
    rubric: dict,
    *,
    mode: str = "content",
) -> dict:
    answer = resp.get("answer", "")
    checks = {}
    strict = mode == "strict"

    exp_agents = expected.get("agents", [])
    act_agents = resp.get("agents_used", [])
    checks["agents"] = agents_match(
        act_agents,
        exp_agents,
        exact=strict and expected.get("agents_exact", False),
    )

    if expected.get("not_agents"):
        checks["not_agents"] = not any(a in act_agents for a in expected["not_agents"])

    min_agents = expected.get("min_agents")
    if min_agents is not None:
        checks["min_agents"] = len(act_agents) >= min_agents

    if strict:
        if expected.get("primary"):
            checks["primary"] = resp.get("primary_agent") == expected["primary"]
        pipe_any = expected.get("pipeline_any", [])
        checks["pipeline"] = pipeline_match(resp, pipe_any)
        if expected.get("per_agent_pipelines"):
            checks["per_agent_pipelines"] = per_agent_pipeline_match(
                resp, expected["per_agent_pipelines"],
            )
        if expected.get("supervisor_intent"):
            checks["supervisor_intent"] = (
                resp.get("supervisor_intent") == expected["supervisor_intent"]
            )
        if expected.get("planner_used") is True:
            checks["planner_used"] = resp.get("planner_used") is True
        elif expected.get("planner_used") is False:
            checks["planner_used"] = resp.get("planner_used") is False
        qc_min = expected.get("qc_min")
        qc_max = expected.get("qc_max")
        qc = resp.get("qc", 0)
        if qc_min is not None:
            checks["qc_min"] = qc >= qc_min
        if qc_max is not None:
            checks["qc_max"] = qc <= qc_max

    if expected.get("was_rewritten") is True:
        checks["was_rewritten"] = resp.get("was_rewritten") is True

    if "in_scope" in expected:
        checks["in_scope"] = resp.get("in_scope", True) == expected["in_scope"]
    if expected.get("scope_category"):
        checks["scope_category"] = resp.get("scope_category") == expected["scope_category"]

    rubric = rubric or {}
    checks["must_contain_all"] = contains_all(answer, rubric.get("must_contain_all", []))
    checks["must_contain_any"] = contains_any(answer, rubric.get("must_contain_any", []))
    must_not = rubric.get("must_not_contain", [])
    checks["must_not_contain"] = not any(t.lower() in answer.lower() for t in must_not)

    for fact in rubric.get("gold_facts", []):
        key = f"gold:{fact[:24]}"
        checks[key] = _term_in_text(fact, answer)

    src_files = rubric.get("source_file_any", [])
    if src_files and strict:
        sources = " ".join(s.get("source", "") for s in resp.get("sources", []))
        for p in resp.get("per_agent", []):
            sources += " " + " ".join(
                s.get("source", "") for s in p.get("sources", [])
            )
        checks["sources"] = contains_any(sources, src_files)

    passed = all(checks.values()) if checks else True
    return {"passed": passed, "checks": checks, "answer_preview": answer[:400]}


def run_case(case: dict, base_url: str, timeout: int, *, mode: str = "content") -> dict:
    rubric = case.get("rubric", {})
    exp_global = case.get("expected", {})
    turns_out = []
    t0 = time.perf_counter()

    try:
        if case.get("multi_turn"):
            sid = new_session(base_url)
            history = []
            all_pass = True
            for turn in case["turns"]:
                q = turn["question"]
                resp = post_chat(base_url, q, history, sid, timeout=timeout)
                exp = merge_turn_expected(exp_global, turn.get("expected", {}))
                sc = score_turn(resp, exp, {**rubric, **turn.get("rubric", {})}, mode=mode)
                turns_out.append({
                    "question": q,
                    "response": resp,
                    "score": sc,
                })
                all_pass = all_pass and sc["passed"]
                history.append({"role": "user", "content": q})
                history.append({"role": "assistant", "content": resp.get("answer", "")})
            return {
                "id": case["id"],
                "tier": case["tier"],
                "passed": all_pass,
                "turns": turns_out,
                "elapsed_s": round(time.perf_counter() - t0, 2),
            }

        q = case["turns"][0]["question"]
        sid = new_session(base_url)
        resp = post_chat(base_url, q, [], sid, timeout=timeout)
        sc = score_turn(resp, exp_global, rubric, mode=mode)
        return {
            "id": case["id"],
            "tier": case["tier"],
            "passed": sc["passed"],
            "question": q,
            "response": resp,
            "score": sc,
            "elapsed_s": round(time.perf_counter() - t0, 2),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        err = f"{type(e).__name__}: {e}"
        if "timed out" in err.lower():
            err += f" (timeout={timeout}s — thử --timeout 900 hoặc chỉ chạy --id {case['id']})"
        return {
            "id": case["id"],
            "tier": case["tier"],
            "passed": False,
            "error": err,
            "elapsed_s": round(time.perf_counter() - t0, 2),
        }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--tier", default="", help="L0, L1, ...")
    parser.add_argument("--id", default="", help="Một case, vd L1-01")
    parser.add_argument(
        "--ids",
        default="",
        help="Nhiều case, cách nhau bởi dấu phẩy (vd L0-05,L1-09)",
    )
    parser.add_argument(
        "--ids-file",
        default="",
        help="File danh sách id (một id/dòng, # comment)",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--benchmark", default=str(BENCHMARK))
    parser.add_argument("--timeout", type=int, default=0, help="Giây/request (0 = theo tier)")
    parser.add_argument("--from-id", default="", help="Chạy từ case này trở đi")
    parser.add_argument(
        "--mode",
        choices=("content", "strict"),
        default="content",
        help="content = chỉ agent + nội dung (mặc định, khớp test tay); strict = thêm pipeline/Qc",
    )
    args = parser.parse_args()

    if not Path(args.benchmark).exists():
        print("Chưa có benchmark.json — chạy: python eval/build_benchmark.py", file=sys.stderr)
        sys.exit(1)

    data = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
    cases = data["cases"]
    if args.tier:
        cases = [c for c in cases if c["tier"] == args.tier]
    if args.id:
        cases = [c for c in cases if c["id"] == args.id]
    if args.ids:
        want = {x.strip() for x in args.ids.split(",") if x.strip()}
        cases = [c for c in cases if c["id"] in want]
        missing = want - {c["id"] for c in cases}
        if missing:
            print(f"Cảnh báo: không tìm thấy id {sorted(missing)}", file=sys.stderr)
    if args.ids_file:
        path = Path(args.ids_file)
        if not path.exists():
            path = Path(__file__).parent / Path(args.ids_file).name
        if not path.exists():
            print(f"Không tìm thấy ids-file: {args.ids_file}", file=sys.stderr)
            sys.exit(1)
        want = {
            ln.strip()
            for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        }
        cases = [c for c in cases if c["id"] in want]
        print(f"Lọc {len(cases)} case từ {path.name}", flush=True)
    if args.limit:
        cases = cases[: args.limit]
    if args.from_id:
        ids = [c["id"] for c in cases]
        if args.from_id not in ids:
            print(f"Không tìm thấy id {args.from_id}", file=sys.stderr)
            sys.exit(1)
        cases = cases[ids.index(args.from_id):]
        print(f"Chạy từ {args.from_id} → hết ({len(cases)} case)", flush=True)

    check_server(args.base_url)
    print(f"API OK tại {args.base_url} — mode={args.mode} — {len(cases)} case\n", flush=True)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"run_{stamp}.json"

    results = []
    passed = 0
    for i, case in enumerate(cases, 1):
        t_case = timeout_for_case(case, args.timeout or None)
        print(f"[{i}/{len(cases)}] {case['id']} (timeout={t_case}s) …", flush=True)
        r = run_case(case, args.base_url, timeout=t_case, mode=args.mode)
        results.append(r)
        if r.get("passed"):
            passed += 1
        elif r.get("error"):
            print(f"  ERROR {case['id']}: {r['error']}", flush=True)
        else:
            sc = r.get("score") or (r.get("turns") or [{}])[-1].get("score", {})
            failed = [k for k, v in (sc.get("checks") or {}).items() if not v]
            print(f"  FAIL {case['id']}: {failed}", flush=True)
        _write_summary(out_path, stamp, args.base_url, cases, results, passed)

    summary = _build_summary(stamp, args.base_url, cases, results, passed)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone: {passed}/{len(cases)} passed ({summary['pass_rate']}%)")
    print(f"Results: {out_path}")


def _build_summary(stamp: str, base_url: str, cases: list, results: list, passed: int) -> dict:
    from collections import defaultdict
    tier_stats = defaultdict(lambda: {"total": 0, "passed": 0})
    for r in results:
        tier_stats[r["tier"]]["total"] += 1
        if r.get("passed"):
            tier_stats[r["tier"]]["passed"] += 1
    return {
        "run_at": stamp,
        "base_url": base_url,
        "benchmark_version": json.loads(Path(BENCHMARK).read_text(encoding="utf-8")).get("version", ""),
        "total": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "pass_rate": round(100 * passed / len(cases), 1) if cases else 0,
        "by_tier": dict(tier_stats),
        "results": results,
    }


def _write_summary(path: Path, stamp: str, base_url: str, cases: list, results: list, passed: int):
    summary = _build_summary(stamp, base_url, cases, results, passed)
    summary["partial"] = len(results) < len(cases)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
