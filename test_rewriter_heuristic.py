from agents.query_rewriter import _needs_rewrite_score, rewrite


def test_needs_rewrite_score():
    score1 = _needs_rewrite_score("Còn cái đó?", [])
    assert score1 > 0.6, f"Follow-up should have high score, got {score1}"

    score2 = _needs_rewrite_score("Thế còn biểu mẫu?", [])
    assert score2 > 0.5, f"'Thế còn biểu mẫu?' should have medium-high score, got {score2}"

    score3 = _needs_rewrite_score("Ngành CNTT K68 tuyển bao nhiêu?", [])
    assert score3 < 0.4, f"Standalone query should have low score, got {score3}"

    score4 = _needs_rewrite_score("Tôi là sinh viên AT200201, tra điểm học kỳ 1?", [])
    assert score4 < 0.3, f"Query with MSSV should have very low score, got {score4}"

    score5 = _needs_rewrite_score("Điều gì", [])
    assert 0 <= score5 <= 1, f"Score should be in [0,1], got {score5}"

    print("PASS: All scoring tests passed!")


def test_rewrite_skip_llm():
    result1 = rewrite("Ngành CNTT K68?")
    assert not result1.was_rewritten, "Should skip rewrite for clear query"
    assert result1.retrieval_query == "Ngành CNTT K68?", "Should return original"

    result2 = rewrite("AT200201 diem?")
    assert not result2.was_rewritten, "Should skip for query with MSSV"

    print("PASS: Rewrite skip LLM tests passed!")


def test_rewrite_normalization():
    score_upper = _needs_rewrite_score("CON CAI DO?", [])
    score_lower = _needs_rewrite_score("con cai do?", [])
    assert score_upper == score_lower, "Case should not affect scoring"

    score1 = _needs_rewrite_score("Con cai do?", [])
    assert score1 >= 0, "Score should be non-negative"

    print("PASS: Normalization tests passed!")


if __name__ == "__main__":
    test_needs_rewrite_score()
    test_rewrite_skip_llm()
    test_rewrite_normalization()
