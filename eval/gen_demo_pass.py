"""
Tạo eval/demo_pass.md từ file kết quả benchmark — chỉ các câu PASS.

Usage:
  python eval/gen_demo_pass.py
  python eval/gen_demo_pass.py eval/results/run_20260523_114628.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
OUT_PATH = Path(__file__).parent / "demo_pass.md"
BENCHMARK = Path(__file__).parent / "benchmark.json"


def _latest_run() -> Path:
    runs = sorted(RESULTS_DIR.glob("run_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not runs:
        raise SystemExit("Chưa có file run_*.json — chạy eval/run_benchmark.py trước.")
    return runs[0]


def _answer_preview(result: dict) -> str:
    if result.get("turns"):
        parts = []
        for t in result["turns"]:
            ans = (t.get("response") or {}).get("answer", "")
            if ans:
                parts.append(ans)
        return "\n\n---\n\n".join(parts)
    return (result.get("response") or {}).get("answer", "")


def _expected_demo(case_id: str, bench: dict) -> str:
    for c in bench.get("cases", []):
        if c["id"] == case_id:
            exp = (c.get("demo") or {}).get("expected_answer", "")
            if isinstance(exp, list):
                return "\n".join(str(x) for x in exp)
            return str(exp) if exp else ""
    return ""


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    run_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _latest_run()
    data = json.loads(run_path.read_text(encoding="utf-8"))
    bench = json.loads(BENCHMARK.read_text(encoding="utf-8")) if BENCHMARK.exists() else {"cases": []}

    passed = [r for r in data.get("results", []) if r.get("passed")]
    failed = [r for r in data.get("results", []) if not r.get("passed")]

    lines = [
        "# Demo — các câu PASS benchmark",
        "",
        f"- Nguồn: `{run_path.name}`",
        f"- Pass: **{data.get('passed', len(passed))}/{data.get('total', len(passed) + len(failed))}** ({data.get('pass_rate', '')}%)",
        f"- Mode: content (agent + nội dung)",
        "",
        "Copy khối ` ```text ` vào http://127.0.0.1:8000 — so với **Câu trả lời mẫu (lần chạy)**.",
        "",
        "---",
        "",
    ]

    for r in sorted(passed, key=lambda x: x["id"]):
        cid = r["id"]
        tier = r.get("tier", "")
        q = r.get("question") or ""
        if not q and r.get("turns"):
            q = " → ".join(t.get("question", "") for t in r["turns"])
        exp = _expected_demo(cid, bench)
        ans = _answer_preview(r)
        agents = (r.get("response") or {}).get("agents_used") or []
        if r.get("turns"):
            agents = (r["turns"][-1].get("response") or {}).get("agents_used") or agents

        lines += [
            f"## {cid} ({tier})",
            "",
            "**Câu hỏi:**",
            "```text",
            q.strip(),
            "```",
            "",
        ]
        if exp:
            lines.extend(["**Kỳ vọng (rubric):**", exp, ""])
        if agents:
            lines += [f"**Agent:** `{', '.join(agents)}`", ""]
        lines += [
            "**Câu trả lời mẫu (lần chạy):**",
            ans.strip() or "(trống)",
            "",
            "---",
            "",
        ]

    if failed:
        lines += [
            "## Các câu FAIL (không demo trước)",
            "",
            ", ".join(r["id"] for r in sorted(failed, key=lambda x: x["id"])),
            "",
        ]

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(passed)} pass cases → {OUT_PATH}")


if __name__ == "__main__":
    main()
