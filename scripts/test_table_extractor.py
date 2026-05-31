"""Unit test table markdown (không cần PDF thật).

  python scripts/test_table_extractor.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.ingest.table_extractor import table_to_markdown, _infer_headers
from utils.ingest.metadata_schema import build_table_payload, parse_table_headers


def main():
    headers, rows = _infer_headers(
        ["MSSV", "Mã môn", "Điểm"],
        ["AT200201", "Tin học", "8.5"],
    )
    md = table_to_markdown(headers, rows)
    assert "AT200201" in md
    assert "|" in md

    p = build_table_payload(
        {},
        text=md,
        table_headers=headers,
        section="Phụ lục 1",
        document_type="table",
        row_count=1,
    )
    assert p["document_type"] == "table"
    assert "MSSV" in parse_table_headers(p["table_headers"])[0]

    print("OK table extractor / metadata schema")


if __name__ == "__main__":
    main()
