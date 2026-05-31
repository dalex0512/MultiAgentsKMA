"""
Kiểm tra parent–child chunking + collapse (không cần Qdrant).

  python scripts/test_parent_child_chunking.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.chunking.parent_child import (
    build_document_child_records,
    split_parent_segments,
    split_child_segments,
)
from utils.chunking.retrieval_expand import collapse_child_hits_to_parents


SAMPLE = """
Điều 1. Phạm vi điều chỉnh
Quy chế này quy định về đào tạo đại học hệ chính quy tại Học viện Kỹ thuật Mật mã.

Điều 2. Đối tượng áp dụng
Quy chế áp dụng cho sinh viên, giảng viên và cán bộ có liên quan.

Điều 3. Điều kiện dự thi
Sinh viên phải hoàn thành học phần và đăng ký thi đúng hạn.
Nếu nghỉ quá số buổi quy định thì không được dự thi.
""" * 3


def main():
    parents = split_parent_segments(SAMPLE)
    assert len(parents) >= 1, f"expected at least one parent, got {len(parents)}"
    for p in parents:
        assert len(p) <= 1600, f"parent too long: {len(p)}"

    children = split_child_segments(parents[0])
    assert len(children) >= 2, "parent should split into multiple children"
    for c in children:
        assert len(c) <= 250, f"child too long: {len(c)}"

    records = build_document_child_records(
        [{"page": 1, "text": SAMPLE}],
        "khao_thi_quy_che/test.pdf",
    )
    assert len(records) >= len(parents) + 1, "need multiple children across parents"
    parent_ids = {r.parent_id for r in records}
    assert len(parent_ids) == len(parents)

    # Collapse simulation
    hits = []
    for i, r in enumerate(records[:8]):
        hits.append({
            "text": r.child_text,
            "parent_text": r.parent_text,
            "parent_id": r.parent_id,
            "child_index": r.child_index,
            "chunk_role": "child",
            "score": 0.9 - i * 0.05,
            "_rank_score": 0.9 - i * 0.05,
            "source": "khao_thi_quy_che/test.pdf",
            "page": 1,
        })
    # Two hits same parent — should merge to one
    hits[1]["parent_id"] = hits[0]["parent_id"]
    collapsed = collapse_child_hits_to_parents(hits, max_parents=4)
    assert len(collapsed) <= 4
    assert all(len(d["text"]) >= len(d.get("child_text", "")) for d in collapsed)

    print("OK parent-child:", len(parents), "parents,", len(records), "children,", len(collapsed), "collapsed")


if __name__ == "__main__":
    main()
