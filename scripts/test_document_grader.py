"""
Smoke test grader (mock docs, không gọi OpenAI nếu KMA_RELEVANCE_GRADER=0).

  python scripts/test_document_grader.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.rag.document_grader import (
    format_chunks_for_grader,
    _parse_yes_no,
    finalize_after_grading,
    GradingTrace,
)


def test_parse():
    assert _parse_yes_no("YES\nđủ thông tin") is True
    assert _parse_yes_no("NO\nkhông liên quan") is False
    assert _parse_yes_no("maybe") is False


def test_format():
    s = format_chunks_for_grader([
        {"text": "Điều 1 quy định về điểm chuẩn", "source": "a.pdf", "page": 1, "score": 0.9},
    ])
    assert "Điều 1" in s


def test_finalize_catalog():
    trace = GradingTrace(sufficient=False, reason="NO")
    docs, trace = finalize_after_grading(
        "q", [], trace, agent_id="bieu_mau", retrieval_query="đơn nghỉ học",
    )
    assert docs == []


def main():
    test_parse()
    test_format()
    test_finalize_catalog()
    print("OK document_grader unit checks")


if __name__ == "__main__":
    main()
