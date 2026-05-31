"""
Gộp kết quả retest vào full run → báo cáo pass rate tổng hợp + demo_pass.md.

Usage:
  python eval/merge_benchmark_runs.py eval/results/run_20260523_134742.json eval/results/run_20260523_143737.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BENCHMARK = Path(__file__).parent / "benchmark.json"


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: merge_benchmark_runs.py <base_run.json> <patch_run.json>", file=sys.stderr)
        sys.exit(1)

    base = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    patch = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in base.get("results", [])}
    for r in patch.get("results", []):
        by_id[r["id"]] = r

    # Giữ thứ tự benchmark.json
    bench = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    order = [c["id"] for c in bench.get("cases", [])]
    merged_results = [by_id[i] for i in order if i in by_id]

    passed = sum(1 for r in merged_results if r.get("passed"))
    total = len(merged_results)

    from collections import defaultdict
    tier_stats = defaultdict(lambda: {"total": 0, "passed": 0})
    for r in merged_results:
        tier_stats[r["tier"]]["total"] += 1
        if r.get("passed"):
            tier_stats[r["tier"]]["passed"] += 1

    out = {
        **base,
        "merged_from": [Path(sys.argv[1]).name, Path(sys.argv[2]).name],
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(100 * passed / total, 1) if total else 0,
        "by_tier": dict(tier_stats),
        "results": merged_results,
    }

    out_path = Path(sys.argv[1]).parent / f"merged_{Path(sys.argv[2]).stem}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Merged: {passed}/{total} ({out['pass_rate']}%) → {out_path}")


if __name__ == "__main__":
    main()
