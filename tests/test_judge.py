from app import judge


def test_score_is_computed_by_code_not_by_the_model(monkeypatch):
    monkeypatch.setattr(judge.llm, "ask_json", lambda prompt, name: {
        "numbers_match_facts": 2, "complete_sections": 2, "sources_cited": 1, "safe_advice": 2,
        "clarity": 2, "score": 99, "reasoning": "fine"})
    assert judge.judge({}, "report")["score"] == 9          # the model's own "99" is ignored


def test_garbage_ratings_count_as_zero(monkeypatch):
    monkeypatch.setattr(judge.llm, "ask_json", lambda prompt, name: {"numbers_match_facts": "excellent", "clarity": 7})
    result = judge.judge({}, "report")
    assert result["criteria"]["numbers_match_facts"] == 0 and result["criteria"]["clarity"] == 2


def test_critical_failure_caps_the_score(monkeypatch):
    # everything perfect except an invented number: a plain sum would give 8/10 and pass
    monkeypatch.setattr(judge.llm, "ask_json", lambda prompt, name: {
        "numbers_match_facts": 0, "complete_sections": 2, "sources_cited": 2, "safe_advice": 2, "clarity": 2})
    assert judge.judge({}, "report")["score"] == judge.CRITICAL_FAIL_CAP


def test_unsafe_advice_also_caps_the_score():
    criteria = {"numbers_match_facts": 2, "complete_sections": 2, "sources_cited": 2, "safe_advice": 0, "clarity": 2}
    assert judge.total_score(criteria) == judge.CRITICAL_FAIL_CAP
