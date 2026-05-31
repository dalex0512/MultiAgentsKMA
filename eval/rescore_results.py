"""
Chấm lại kết quả benchmark (không gọi API) — dùng rubric mới + logic chấm đã sửa.

Usage:
  python eval/rescore_results.py eval/results/merged_run_20260523_143737.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from eval.run_benchmark import (  # noqa: E402
    contains_all,
    contains_any,
    merge_turn_expected,
    score_turn,
    _term_in_text,
)

BENCHMARK = Path(__file__).parent / "benchmark.json"


def rescore_run(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    bench = {c["id"]: c for c in json.loads(BENCHMARK.read_text(encoding="utf-8"))["cases"]}

    results = []
    passed = 0
    for r in data.get("results", []):
        case = bench.get(r["id"])
        if not case:
            results.append(r)
            continue

        if case.get("multi_turn"):
            turns_out = []
            all_pass = True
            exp_global = case.get("expected", {})
            rub_global = case.get("rubric", {})
            for i, turn in enumerate(case["turns"]):
                prev = r.get("turns", [])
                resp = prev[i]["response"] if i < len(prev) else {}
                exp = merge_turn_expected(exp_global, turn.get("expected", {}))
                sc = score_turn(
                    resp,
                    exp,
                    {**rub_global, **turn.get("rubric", {})},
                    mode="content",
                )
                turns_out.append({
                    "question": turn["question"],
                    "response": resp,
                    "score": sc,
                })
                all_pass = all_pass and sc["passed"]
            nr = {**r, "passed": all_pass, "turns": turns_out}
        else:
            resp = r.get("response") or {}
            sc = score_turn(resp, case.get("expected", {}), case.get("rubric", {}), mode="content")
            nr = {**r, "passed": sc["passed"], "score": sc}

        if nr.get("passed"):
            passed += 1
        results.append(nr)

    from collections import defaultdict
    tier_stats = defaultdict(lambda: {"total": 0, "passed": 0})
    for r in results:
        tier_stats[r["tier"]]["total"] += 1
        if r.get("passed"):
            tier_stats[r["tier"]]["passed"] += 1

    return {
        **data,
        "rescored": True,
        "source_run": path.name,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(100 * passed / len(results), 1) if results else 0,
        "by_tier": dict(tier_stats),
        "results": results,
    }


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "results" / "merged_run_20260523_143737.json"
    out = src.parent / f"rescored_{src.name}"
    summary = rescore_run(src)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Rescored: {summary['passed']}/{summary['total']} ({summary['pass_rate']}%)")
    print(f"→ {out}")
    still = [r["id"] for r in summary["results"] if not r.get("passed")]
    print("Still fail:", ", ".join(still))


if __name__ == "__main__":
    main()
