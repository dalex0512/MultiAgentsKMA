#!/usr/bin/env python3
"""
Chuyển mẫu .doc → .docx (cần Microsoft Word trên Windows).
Cập nhật catalog.json: đổi key .doc → .docx khi convert thành công.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import DOCS_ROOT  # noqa: E402

BIEU_MAU = Path(DOCS_ROOT) / "bieu_mau"
CATALOG_PATH = BIEU_MAU / "catalog.json"


def convert_one(doc_path: Path) -> Path | None:
    try:
        import win32com.client  # type: ignore
    except ImportError:
        print("win32com không khả dụng — bỏ qua convert.")
        return None

    out = doc_path.with_suffix(".docx")
    if out.is_file() and out.stat().st_mtime >= doc_path.stat().st_mtime:
        return out

    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    try:
        doc = word.Documents.Open(str(doc_path.resolve()))
        doc.SaveAs2(str(out.resolve()), FileFormat=16)  # wdFormatXMLDocument
        doc.Close(False)
        print(f"OK  {doc_path.name} -> {out.name}")
        return out
    except Exception as e:
        print(f"FAIL {doc_path.name}: {e}")
        return None
    finally:
        word.Quit()


def update_catalog(converted: dict[str, str]) -> None:
    if not CATALOG_PATH.is_file():
        return
    cat = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    new_cat: dict = {}
    for fname, meta in cat.items():
        if fname in converted:
            new_name = converted[fname]
            new_cat[new_name] = dict(meta)
            new_cat[new_name]["legacy_doc"] = fname
        else:
            new_cat[fname] = meta
    CATALOG_PATH.write_text(
        json.dumps(new_cat, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Updated catalog ({len(converted)} entries -> docx)")


def main() -> int:
    converted: dict[str, str] = {}
    for doc_path in sorted(BIEU_MAU.glob("*.doc")):
        out = convert_one(doc_path)
        if out and out.is_file():
            converted[doc_path.name] = out.name

    if converted:
        update_catalog(converted)
    else:
        print("Không convert được file nào.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
