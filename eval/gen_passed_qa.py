"""
Gộp eval/results/run_*.json → file .txt case PASS: mô tả tier + câu hỏi + câu trả lời.

Usage:
  python eval/gen_passed_qa.py
  python eval/gen_passed_qa.py eval/passed_cases_qa.txt
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
DEFAULT_OUT = Path(__file__).parent / "passed_cases_qa.txt"

# Mô tả từng tier — kết hợp thành phần hệ thống
TIER_INFO: dict[str, tuple[str, str]] = {
    "L0": (
        "L0 — Guardrail & chitchat",
        "Không tra cứu PDF. Luồng: Guardrail → trả lời cố định (chào hỏi / từ chối off-topic / giới thiệu KMA). "
        "Không qua Supervisor, Planner, RAG.",
    ),
    "L1": (
        "L1 — Đơn giản — một agent, RAG Native",
        "Luồng: Guardrail → Rewriter → Supervisor (1 agent) → Specialist: Qc thấp (<0.40) → Router chọn native_rag "
        "(1 lần tìm Qdrant + 1 lần GPT). Filter corpus theo agent_id.",
    ),
    "L2": (
        "L2 — Trung bình — một agent, Hybrid hoặc Agentic",
        "Luồng: giống L1 nhưng Qc trung bình–cao (≥0.40). Router: hybrid_rag (Native trước, nếu «không tìm thấy» → Agentic) "
        "hoặc agentic_rag (nhiều vòng Plan–Retrieve–Eval, tối đa 4 vòng). Câu so sánh, liệt kê, nhiều fact.",
    ),
    "L3": (
        "L3 — Multi-agent — Supervisor + Aggregator",
        "Luồng: Guardrail → Rewriter → Supervisor chọn 2–3 agent (chạy song song) → mỗi agent RAG riêng (Native/Hybrid/Agentic) "
        "→ Aggregator gộp 1 câu trả lời (pipeline tổng: multi_agent). Thường không bật Planner.",
    ),
    "L4": (
        "L4 — Phức tạp — Planner + multi-agent",
        "Luồng: câu dài → Planner tách tối đa 3 sub-questions → Supervisor gán agent cho từng ý → "
        "chạy specialist song song → Aggregator gộp. Kết hợp: Planner + Supervisor + (Native/Hybrid/Agentic từng agent) + Aggregator.",
    ),
    "L5": (
        "L5 — Multi-turn — memory & Query Rewriter",
        "Luồng: cùng session_id + history qua nhiều lượt. Lượt sau: Rewriter hiểu «còn», «đơn đó» → retrieval_query đủ nghĩa. "
        "Có thể 1 agent (L1/L2) hoặc multi-agent tùy câu. Cần không reset phiên giữa các lượt.",
    ),
    "L6": (
        "L6 — Biểu mẫu — catalog & form fill",
        "Luồng: agent bieu_mau — catalog.json (tìm tên/link đơn) + Qdrant; hoặc nhánh form_fill (điền Word, hỏi từng field). "
        "Pipeline có thể: native_rag, hybrid_rag, multi_agent, form_fill.",
    ),
}


def _tier_sort_key(case_id: str) -> tuple:
    m = re.match(r"L(\d+)-(\d+)", case_id)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return (99, 99)


def _tier_of(case_id: str) -> str:
    m = re.match(r"(L\d+)", case_id)
    return m.group(1) if m else "L?"


def _extract_qa(result: dict) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    cid = result["id"]

    if "turns" in result and result["turns"] and "score" in result["turns"][0]:
        for i, turn in enumerate(result["turns"], 1):
            q = turn.get("question", "").strip()
            ans = (turn.get("response") or {}).get("answer", "").strip()
            label = f"{cid} - luot {i}" if len(result["turns"]) > 1 else cid
            rows.append((label, q, ans))
        return rows

    q = result.get("question", "").strip()
    if not q and result.get("turns"):
        q = result["turns"][0].get("question", "").strip()
    ans = (result.get("response") or {}).get("answer", "").strip()
    rows.append((cid, q, ans))
    return rows


def collect_passed(paths: list[Path]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for path in sorted(paths):
        data = json.loads(path.read_text(encoding="utf-8"))
        for r in data.get("results", []):
            if r.get("passed"):
                by_id[r["id"]] = r
    return sorted(by_id.values(), key=lambda x: _tier_sort_key(x["id"]))


def render_txt(cases: list[dict]) -> str:
    qa_count = sum(len(_extract_qa(c)) for c in cases)
    parts: list[str] = [
        "CASE PASS - CAU HOI & CAU TRA LOI (co mo ta tung tier)",
        f"Tong: {len(cases)} case pass, {qa_count} khoi hoi-dap",
        "Copy CAU HOI vao http://127.0.0.1:8000 , doi chieu CAU TRA LOI",
        "=" * 60,
        "",
        "BANG TOM TAT CAC TIER (benchmark 80 case)",
        "-" * 60,
    ]
    for tier in ("L0", "L1", "L2", "L3", "L4", "L5", "L6"):
        title, desc = TIER_INFO[tier]
        parts.append(f"{title}")
        parts.append(f"  {desc}")
        parts.append("")
    parts.append("=" * 60)

    current_tier: str | None = None
    for r in cases:
        tier = _tier_of(r["id"])
        if tier != current_tier:
            current_tier = tier
            title, desc = TIER_INFO.get(tier, (tier, ""))
            parts.extend(["", "#" * 60, title, desc, "#" * 60, ""])
        for label, q, ans in _extract_qa(r):
            parts.extend([
                "=" * 60,
                f"[{label}]",
                "-" * 60,
                "CAU HOI:",
                q,
                "",
                "CAU TRA LOI:",
                ans or "(trong)",
                "",
            ])
    return "\n".join(parts) + "\n"


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    paths = sorted(RESULTS_DIR.glob("run_*.json"))
    if not paths:
        print("Khong co file eval/results/run_*.json", file=sys.stderr)
        raise SystemExit(1)

    cases = collect_passed(paths)
    out.write_text(render_txt(cases), encoding="utf-8")
    qa_count = sum(len(_extract_qa(c)) for c in cases)
    print(f"OK: {len(cases)} case pass, {qa_count} khoi -> {out}")


if __name__ == "__main__":
    main()
