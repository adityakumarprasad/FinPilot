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
