"""Generate markdown of passed cases from a run_*.json file."""
import json
import sys
from pathlib import Path

def main():
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "eval/results/run_20260521_230117.json")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "eval/passed_cases_demo_20260521.md")
    data = json.loads(src.read_text(encoding="utf-8"))
    passed = [r for r in data["results"] if r.get("passed")]

    # Optional: enrich with benchmark titles / rubric
    bench_path = Path(__file__).parent / "benchmark.json"
    bench_by_id = {}
    if bench_path.exists():
        for c in json.loads(bench_path.read_text(encoding="utf-8")).get("cases", []):
            bench_by_id[c["id"]] = c

    lines = [
        "# Case PASS — copy vào web test (demo thực tế)",
        "",
        f"> Nguồn: [`{src.name}`](results/{src.name}) — lần chạy `{data.get('run_at', '')}`.",
        f"> **{len(passed)}/{data['total']}** case pass (pass rate {data.get('pass_rate', 0)}%).",
        "> **Cách test:** http://127.0.0.1:8000 — dán câu vào chat. **L5:** các lượt **cùng một** cửa sổ (không bấm + giữa chừng).",
        "",
        "## Mục lục nhanh",
        "",
        "| ID | Tier | Lượt |",
        "|----|------|------|",
    ]
    for r in passed:
        n = len(r["turns"]) if "turns" in r else 1
        anchor = r["id"].lower().replace("-", "")
        lines.append(f"| [{r['id']}](#{anchor}-{r['tier'].lower()}) | {r['tier']} | {n} |")
    lines.extend(["", "---", ""])

    for r in passed:
        anchor = f"{r['id'].lower()}-{r['tier'].lower()}"
        lines.append(f"## {r['id']} ({r['tier']})")
        lines.append("")
        bc = bench_by_id.get(r["id"])
        if bc:
            if bc.get("title"):
                lines.append(f"**Tiêu đề benchmark:** {bc['title']}")
            rub = bc.get("rubric", {})
            hints = rub.get("must_contain_any") or rub.get("gold_facts") or []
            if hints:
                lines.append(f"**Khi test nên thấy (ít nhất một):** {', '.join(f'`{h}`' for h in hints)}")
            lines.append("")
        if "turns" in r and r["turns"] and "question" in r["turns"][0] and "score" in r["turns"][0]:
            lines.append("**Multi-turn** — gửi lần lượt:")
            lines.append("")
            for i, t in enumerate(r["turns"], 1):
                lines.append(f"### Lượt {i}")
                lines.append("")
                lines.append("```text")
                lines.append(t["question"].strip())
                lines.append("```")
                lines.append("")
                sc = t.get("score", {})
                if sc.get("answer_preview"):
                    lines.append(f"- Preview trả lời (lúc chạy script): {sc['answer_preview'][:200]}…")
                    lines.append("")
        elif r.get("question"):
            lines.append("**Copy — một lượt:**")
            lines.append("")
            lines.append("```text")
            lines.append(r["question"].strip())
            lines.append("```")
            lines.append("")
            sc = r.get("score", {})
            resp = r.get("response", {})
            if sc.get("answer_preview"):
                lines.append("**Preview trả lời (lúc chạy script):**")
                lines.append("")
                lines.append(f"> {sc['answer_preview'].replace(chr(10), ' ')}")
                lines.append("")
            if resp.get("agents_used"):
                lines.append(f"- Agent: `{', '.join(resp['agents_used'])}` | pipeline: `{resp.get('pipeline', '')}` | qc: {resp.get('qc', '')} | t_total: {resp.get('t_total', '')}s")
                lines.append("")
        lines.append("---")
        lines.append("")

    lines.extend([
        "",
        "## Tạo lại file sau lần chạy mới",
        "",
        "```bash",
        "cd demo",
        "python eval/gen_passed_md.py eval/results/run_<timestamp>.json eval/passed_cases_demo_<timestamp>.md",
        "```",
        "",
    ])

    lines.append("## Case FAIL trong cùng file run (không dùng làm demo “chắc đúng”)")
    lines.append("")
    for r in data["results"]:
        if not r.get("passed"):
            lines.append(f"- `{r['id']}` ({r['tier']})")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(passed)} passed cases to {out}")


if __name__ == "__main__":
    main()
