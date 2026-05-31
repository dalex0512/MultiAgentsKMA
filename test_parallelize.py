import time

from pipelines.multi_agent_system import MultiAgentSystem


def test_parallelize_timing():
    system = MultiAgentSystem()

    question = "Ngành CNTT K68 có điểm chuẩn bao nhiêu?"
    history = []

    t0 = time.perf_counter()
    result = system.chat(question, history=history)
    latency = time.perf_counter() - t0

    assert result.answer, "Answer không được empty"
    assert result.qc > 0, "Qc phải > 0"
    assert len(result.agents_used) > 0, "Agents không được empty"
    assert 0 <= result.qc <= 1, "Qc phải trong [0, 1]"
    assert result.pipeline in ["native_rag", "hybrid_rag", "agentic_rag", "multi_agent"], \
        f"Pipeline invalid: {result.pipeline}"

    print(f"PASS: Latency: {latency:.2f}s")
    print(f"PASS: Agents: {result.agents_used}, Pipeline: {result.pipeline}, Qc: {result.qc:.2f}")


if __name__ == "__main__":
    test_parallelize_timing()
    print("PASS: All tests passed!")
