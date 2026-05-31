"""
Kiểm tra nhanh chế độ accuracy + (tuỳ chọn) gọi API /chat.

Usage:
  python eval/verify_accuracy_mode.py
  python eval/verify_accuracy_mode.py --live --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def check_config() -> bool:
    from config import (
        FAST_MODE,
        ACCURACY_MODE,
        TOP_K,
        THRESHOLD1,
        THRESHOLD2,
        MIN_RETRIEVAL_SCORE,
        LLM_MAX_TOKENS,
        MAX_ROUNDS,
    )
    from agents.router import route

    print("=== Cấu hình (sau khi load .env) ===")
    print(f"  KMA_FAST_MODE off     : {not FAST_MODE}")
    print(f"  KMA_ACCURACY_MODE on  : {ACCURACY_MODE}")
    print(f"  TOP_K                 : {TOP_K}")
    print(f"  THRESHOLD1 / 2        : {THRESHOLD1} / {THRESHOLD2}")
    print(f"  MIN_RETRIEVAL_SCORE   : {MIN_RETRIEVAL_SCORE}")
    print(f"  MAX_ROUNDS (agentic)  : {MAX_ROUNDS}")
    print(f"  LLM_MAX_TOKENS        : {LLM_MAX_TOKENS}")
    print("  Router (không ép Agentic):")
    for qc in (0.25, 0.45, 0.70):
        print(f"    qc={qc} -> {route(qc)}")

    from config import USE_LOCAL_QC
    t1_ok = abs(THRESHOLD1 - (0.50 if USE_LOCAL_QC else 0.40)) < 0.01
    t2_ok = abs(THRESHOLD2 - (0.70 if USE_LOCAL_QC else 0.65)) < 0.01
    ok = (
        not FAST_MODE
        and ACCURACY_MODE
        and TOP_K >= 10
        and t1_ok
        and t2_ok
        and MIN_RETRIEVAL_SCORE >= 0.35
    )
    print()
    if ok:
        print(f"OK: Accuracy bật + Router {THRESHOLD1}/{THRESHOLD2} (local_qc={USE_LOCAL_QC}).")
    else:
        print("CANH BAO: Chua dat accuracy toi da. Kiem tra .env:")
        print("  - Khong dat KMA_FAST_MODE=1")
        print("  - Dat KMA_ACCURACY_MODE=1 hoac bo trong (mac dinh bat)")
    return ok


def post_chat(base_url: str, question: str) -> dict:
    body = json.dumps({"question": question, "history": []}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def live_checks(base_url: str) -> None:
    cases = [
        (
            "L1 don (co the native hoac agentic)",
            "Mã trường đại học KMA là gì?",
            lambda r: r.get("agents_used") and r.get("pipeline"),
        ),
        (
            "L2 phuc tap (ky vong agentic_rag)",
            "So sanh diem chuan tuyen sinh 2023 va 2024 trong de an tuyen sinh.",
            lambda r: r.get("pipeline") in ("agentic_rag", "hybrid_rag", "grade_lookup"),
        ),
        (
            "diem_thi MSSV (ky vong grade_lookup hoac agentic)",
            "Cho xem diem hoc ky 1 2024-2025 dot 2 sinh vien AT200201.",
            lambda r: r.get("primary_agent") == "diem_thi",
        ),
    ]
    print()
    print(f"=== Test live API ({base_url}) ===")
    for label, q, pred in cases:
        try:
            r = post_chat(base_url, q)
            pipe = r.get("pipeline", "")
            qc = r.get("qc", "")
            agents = r.get("agents_used", [])
            ok = pred(r)
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {label}")
            print(f"       pipeline={pipe} qc={qc} agents={agents}")
            if not ok:
                print(f"       answer head: {(r.get('answer') or '')[:120]}...")
        except urllib.error.URLError as e:
            print(f"  [SKIP] {label}: khong ket noi server — {e}")
            print("         Chay: uvicorn api.main:app --host 127.0.0.1 --port 8000")
            return


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="Goi POST /chat (can server)")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    check_config()
    if args.live:
        live_checks(args.base_url)
    else:
        print()
        print("Buoc tiep: khoi dong server roi chay lai voi --live")
        print("  uvicorn api.main:app --host 127.0.0.1 --port 8000")
        print("  python eval/verify_accuracy_mode.py --live")


if __name__ == "__main__":
    main()
