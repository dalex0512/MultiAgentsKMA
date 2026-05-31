import time

from agents.session_memory import session_store
from utils.session_storage_manager import SessionState


def test_query_cache():
    session_id = session_store.create()
    st = session_store.get(session_id)

    assert st.query_cache == {}, "Cache should be empty initially"

    question = "Ngành CNTT?"
    fake_result = {
        "answer": "Test answer",
        "agents_used": ["tuyen_sinh"],
        "qc": 0.5,
        "pipeline": "native_rag",
        "agent_names": ["Tuyển sinh"],
        "primary_agent": "tuyen_sinh",
        "supervisor_reason": "",
        "supervisor_intent": "",
        "supervisor_confidence": 0.0,
        "router_reason": "",
        "complexity_intent": "",
        "t_total": 0.1,
        "t_retrieval": 0.0,
        "t_llm": 0.0,
        "n_rounds": 1,
        "sources": [],
        "per_agent": [],
        "session_id": session_id,
        "retrieval_query": question,
        "was_rewritten": False,
        "session_turn": 0,
        "sub_questions": [],
        "planner_used": False,
        "planner_reason": "",
        "in_scope": True,
        "scope_category": "kma",
    }

    st.cache_query_result(question, fake_result)
    assert len(st.query_cache) == 1, "Cache should have 1 entry"

    cached = st.get_cached_query_result(question)
    assert cached is not None, "Should get cached result"
    assert cached["answer"] == "Test answer", "Cached answer should match"

    cached2 = st.get_cached_query_result("Biểu mẫu?")
    assert cached2 is None, "Different question should not hit cache"

    print("PASS: Query cache test passed!")


def test_cache_ttl_expiration():
    st = SessionState(session_id="test-ttl")
    st.QUERY_CACHE_TTL = 1

    question = "Test?"
    fake_result = {"answer": "test"}

    st.cache_query_result(question, fake_result)
    assert st.get_cached_query_result(question) is not None, "Should have cache hit"

    time.sleep(1.1)
    assert st.get_cached_query_result(question) is None, "Cache should be expired"

    print("PASS: Cache TTL test passed!")


if __name__ == "__main__":
    test_query_cache()
    test_cache_ttl_expiration()
