import time

from agents.supervisor import SupervisorIntentCache, route, _supervisor_cache
from agents.routing_intel import SUP_INTENT_GRADE


def test_supervisor_cache():
    _supervisor_cache.clear()

    question = "Ngành CNTT K68 có điểm chuẩn bao nhiêu?"

    result1 = route(question)
    assert result1, "Result 1 should exist"
    agents1 = result1.agents
    confidence1 = result1.confidence

    assert _supervisor_cache.size() == 1, "Cache should have 1 entry"

    result2 = route(question)
    agents2 = result2.agents
    confidence2 = result2.confidence

    assert agents1 == agents2, f"Agents mismatch: {agents1} vs {agents2}"
    assert confidence1 == confidence2, f"Confidence mismatch: {confidence1} vs {confidence2}"
    assert _supervisor_cache.size() == 1, "Cache should still have 1 entry"

    question2 = "Biểu mẫu cần điền gì?"
    route(question2)
    assert _supervisor_cache.size() == 2, "Cache should have 2 entries"

    print("PASS: All cache tests passed!")


def test_cache_ttl():
    from agents.supervisor import RoutingDecision

    cache = SupervisorIntentCache(ttl_seconds=1)
    decision = RoutingDecision(
        agents=["tuyen_sinh"],
        primary="tuyen_sinh",
        reason="test",
        intent="",
        confidence=0.9,
    )
    cache.set("test", decision)

    assert cache.get("test") is not None, "Should have cache hit immediately"

    time.sleep(1.1)
    assert cache.get("test") is None, "Cache should be expired"

    print("PASS: TTL test passed!")


if __name__ == "__main__":
    test_cache_ttl()
    test_supervisor_cache()
