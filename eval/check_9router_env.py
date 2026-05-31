"""
Checklist: .env hiện tại có chạy được KMA qua 9router không.

Usage:
  python eval/check_9router_env.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

FAILURES: list[str] = []
WARNINGS: list[str] = []


def ok(msg: str) -> None:
    print(f"[OK]   {msg}")


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    FAILURES.append(msg)


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")
    WARNINGS.append(msg)


def main() -> int:
    print("=== 1. .env bắt buộc ===")
    key = os.environ.get("OPENAI_API_KEY", "")
    base = os.environ.get("OPENAI_BASE_URL", "")
    qurl = os.environ.get("QDRANT_URL", "")
    qkey = os.environ.get("QDRANT_API_KEY", "")

    embed_key = os.environ.get("OPENAI_EMBED_API_KEY", "")
    for name, val in [
        ("OPENAI_API_KEY", key),
        ("OPENAI_BASE_URL", base),
        ("OPENAI_EMBED_API_KEY", embed_key),
        ("QDRANT_URL", qurl),
        ("QDRANT_API_KEY", qkey),
    ]:
        if val:
            ok(f"{name} có giá trị")
        else:
            if name == "OPENAI_EMBED_API_KEY":
                warn(f"{name} thiếu — sẽ fallback OPENAI_API_KEY (9router không embed được)")
            else:
                fail(f"{name} thiếu")

    if base and "20128" not in base:
        warn(f"OPENAI_BASE_URL không trỏ 9router mặc định: {base}")

    print("\n=== 2. 9router đang chạy ===")
    models: list[str] = []
    if base:
        url = base.rstrip("/") + "/models"
        try:
            req = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {key}"}, method="GET"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            models = [m["id"] for m in data.get("data", [])]
            ok(f"Kết nối OK — {len(models)} model")
        except urllib.error.URLError as e:
            fail(f"Không gọi được {url}: {e}")
        except Exception as e:
            fail(f"9router lỗi: {e}")

    embed_models = [m for m in models if "embed" in m.lower() or m == "text-embedding-3-small"]
    if embed_models:
        ok(f"9router có model embedding (tùy chọn): {', '.join(embed_models[:3])}")
    elif models:
        ok("Embedding không qua 9router — dùng OPENAI_EMBED_API_KEY trực tiếp")

    print("\n=== 3. Embedding trực tiếp OpenAI ===")
    try:
        from config import EMBED_MODEL, OPENAI_EMBED_BASE_URL, embed_client

        client = embed_client()
        resp = client.embeddings.create(input="test kma", model=EMBED_MODEL)
        ok(f"{EMBED_MODEL} @ {OPENAI_EMBED_BASE_URL} → dim={len(resp.data[0].embedding)}")
    except Exception as e:
        fail(f"Embedding: {e}")

    print("\n=== 4. Chat LLM qua 9router ===")
    from config import LLM_MODEL

    chat_ok: str | None = None
    try_models = [LLM_MODEL]
    for m in models:
        if m.startswith("cx/") and m not in try_models:
            try_models.append(m)

    from openai import OpenAI

    client = OpenAI()
    for model in try_models[:6]:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Trả lời đúng 1 từ: OK"}],
                max_tokens=10,
            )
            text = (resp.choices[0].message.content or "").strip()
            ok(f"Chat {model!r} → {text[:40]!r}")
            chat_ok = model
            break
        except Exception as e:
            fail(f"Chat {model!r}: {str(e)[:140]}")

    if chat_ok and chat_ok != LLM_MODEL:
        warn(
            f"config.py LLM_MODEL={LLM_MODEL!r} không chạy; "
            f"đặt LLM_MODEL={chat_ok!r} trong .env hoặc config"
        )

    print("\n=== 5. Qdrant ===")
    try:
        from qdrant_client import QdrantClient

        from config import COLLECTION_NAME

        qc = QdrantClient(url=qurl, api_key=qkey)
        info = qc.get_collection(COLLECTION_NAME)
        ok(f"Collection {COLLECTION_NAME!r} — {info.points_count} points")
    except Exception as e:
        fail(f"Qdrant: {e}")

    print("\n=== 6. RAG retrieve ===")
    try:
        from pipelines.retrieval import QdrantRetriever

        retriever = QdrantRetriever()
        docs, elapsed = retriever.retrieve(
            "điểm chuẩn CNTT 2024", agent_id="tuyen_sinh", top_k=3
        )
        ok(f"Lấy {len(docs)} chunk trong {elapsed:.2f}s")
        if docs:
            sample = docs[0].get("filename") or docs[0].get("source") or "?"
            ok(f"Mẫu: {sample}")
    except Exception as e:
        fail(f"Retrieve: {e}")

    print("\n=== 7. Chat pipeline đầy đủ ===")
    try:
        from pipelines.multi_agent_system import MultiAgentSystem

        system = MultiAgentSystem()
        result = system.chat("Điểm chuẩn ngành CNTT 2024 KMA là bao nhiêu?")
        answer = (result.answer or "")[:150]
        ok(f"Trả lời: {answer!r}")
    except Exception as e:
        fail(f"MultiAgent chat: {type(e).__name__}: {e}")

    print("\n=== 8. FastAPI (nếu đang chạy) ===")
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/health", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                ok("uvicorn /health OK")
    except Exception:
        warn("Server chưa chạy — bỏ qua (uvicorn api.main:app --port 8000)")

    print("\n" + "=" * 50)
    if WARNINGS:
        print(f"Cảnh báo ({len(WARNINGS)}):")
        for w in WARNINGS:
            print(f"  - {w}")
    if FAILURES:
        print(f"\nCHƯA SẴN SÀNG — {len(FAILURES)} lỗi:")
        for f in FAILURES:
            print(f"  - {f}")
        print("\nChạy lại sau khi sửa 9router / .env")
        return 1

    print("\nSẴN SÀNG — chat qua 9router + embedding trực tiếp OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
