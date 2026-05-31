"""
Benchmark latency sau 5 safe optimizations.

Luu y:
- Can Qdrant + OpenAI/9router hoat dong on dinh.
- Mot so cau (agentic_rag, grader requery) co the rat lau neu API/Qdrant cham.
- Dung Ctrl+C neu mot cau vuot timeout (mac dinh 120s).
"""

import argparse
import statistics
import sys
import time

from pipelines.multi_agent_system import MultiAgentSystem

QUESTIONS = [
    "Ngành CNTT K68 có điểm chuẩn bao nhiêu?",
    "Tôi là sinh viên AT200201, tra điểm học kỳ 1?",
    "Biểu mẫu tuyển sinh cần điền gì?",
    "Ma trận đề thi môn Tiếng Anh?",
    "Quy chế thi tốt nghiệp và chuẩn đầu ra tiếng Anh?",
]


def benchmark_optimizations(
    runs: int = 1,
    timeout_sec: float = 120.0,
    warmup: bool = True,
) -> None:
    system = MultiAgentSystem()
    latencies: list[float] = []
    rows: list[dict] = []

    if warmup:
        print("[warmup] 1 cau ngan...", flush=True)
        try:
            system.chat("Xin chao", history=[])
            print("[warmup] xong\n", flush=True)
        except Exception as e:
            print(f"[warmup] loi (bo qua): {e}\n", flush=True)

    total = runs * len(QUESTIONS)
    idx = 0

    for run in range(runs):
        for q in QUESTIONS:
            idx += 1
            print(f"[{idx}/{total}] {q[:55]}...", flush=True)
            t0 = time.perf_counter()
            try:
                result = system.chat(q, history=[])
                latency = time.perf_counter() - t0
                status = "OK"
            except KeyboardInterrupt:
                print("\n[DUNG] Ctrl+C", flush=True)
                sys.exit(130)
            except Exception as e:
                latency = time.perf_counter() - t0
                result = None
                status = f"ERR: {e}"

            flag = " SLOW" if latency > timeout_sec else ""
            if result:
                print(
                    f"  -> {latency:6.2f}s{flag} | pipeline={result.pipeline} "
                    f"qc={result.qc:.2f} agents={result.agents_used}",
                    flush=True,
                )
                rows.append({
                    "question": q,
                    "latency": latency,
                    "pipeline": result.pipeline,
                    "qc": result.qc,
                    "agents": result.agents_used,
                })
            else:
                print(f"  -> {latency:6.2f}s | {status}", flush=True)

            if latency <= timeout_sec * 3:
                latencies.append(latency)

    if not latencies:
        print("\nKhong co ket qua hop le de thong ke.", flush=True)
        return

    latencies_sorted = sorted(latencies)
    n = len(latencies_sorted)
    p50 = statistics.median(latencies_sorted)
    p95 = latencies_sorted[int(max(0, min(n - 1, n * 0.95 - 1)))]
    avg = statistics.mean(latencies_sorted)

    print("\n--- Latency (bo qua outlier > 3x timeout) ---", flush=True)
    print(f"  Samples:      {n}/{total}", flush=True)
    print(f"  P50 (median): {p50:.2f}s", flush=True)
    print(f"  P95:          {p95:.2f}s", flush=True)
    print(f"  Avg:          {avg:.2f}s", flush=True)

    slow = [r for r in rows if r["latency"] > timeout_sec]
    if slow:
        print(f"\n--- {len(slow)} cau > {timeout_sec}s (thuong do agentic/grader/Qdrant) ---", flush=True)
        for r in slow:
            print(
                f"  {r['latency']:7.1f}s | {r['pipeline']} | {r['agents']} | {r['question'][:50]}",
                flush=True,
        )
        print(
            "\nGoi y: KMA_FAST_MODE=1 hoac kiem tra Qdrant/9router neu latency qua cao.",
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1, help="So vong lap (mac dinh 1)")
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Nguong canh bao SLOW (giay)",
    )
    parser.add_argument("--no-warmup", action="store_true")
    args = parser.parse_args()
    benchmark_optimizations(
        runs=args.runs,
        timeout_sec=args.timeout,
        warmup=not args.no_warmup,
    )
