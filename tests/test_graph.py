import pytest

from app import graph, guardrails, judge, llm, tools

FAKE_PORTFOLIO = {"total_value": 1000.0, "allocation": {"cash": 1.0}, "concentrated_positions": [], "holdings": []}
REQUEST = {"age": 30, "retirement_age": 60, "monthly_contribution": 500, "desired_annual_income": 40000, "goals": "retire"}


@pytest.fixture
def fakes(monkeypatch):
    monkeypatch.setattr(tools, "value_portfolio", lambda user_id: FAKE_PORTFOLIO)
    monkeypatch.setattr(guardrails, "check_input", lambda text: (False, ""))
    monkeypatch.setattr(llm, "ask", lambda prompt, name="": f"report from {name}")

    def fake_agent(name, instructions, task, agent_tools):     # an agent that DOES call its tool
        args = {} if name == "portfolio-analyst" else \
            {"monthly_contribution": 500, "years_to_retirement": 30, "desired_annual_income": 40000}
        agent_tools[0].invoke(args)
        return f"analysis by {name}"

    monkeypatch.setattr(graph, "run_agent", fake_agent)
    return monkeypatch


def verdicts(monkeypatch, scores):
    queue = [{"score": s, "criteria": {}, "reasoning": "r"} for s in scores]
    monkeypatch.setattr(judge, "judge", lambda facts, report: queue.pop(0))


def test_good_report_passes_without_revision(fakes):
    verdicts(fakes, [9])
    state = graph.run_plan("demo", REQUEST)
    assert state["revisions"] == 0 and state["report"] == "report from reporter"
    assert set(state["facts"]) == {"portfolio", "simulation"}


def test_low_score_triggers_exactly_one_revision(fakes):
    verdicts(fakes, [4, 5])                            # still low after revising: must stop, not loop
    state = graph.run_plan("demo", REQUEST)
    assert state["revisions"] == 1 and state["report"] == "report from reporter-revision"
    assert state["verdict"]["score"] == 5


def test_blocked_request_stops_at_guardrail(fakes):
    fakes.setattr(guardrails, "check_input", lambda text: (True, "attack"))
    state = graph.run_plan("demo", REQUEST)
    assert state["blocked"] and "report" not in state


def test_agent_skipping_its_tool_fails_the_job(fakes):
    fakes.setattr(graph, "run_agent", lambda *args: "I made up some numbers")
    with pytest.raises(graph.MissingToolCall):
        graph.run_plan("demo", REQUEST)


def test_progress_reports_every_step_in_order(fakes):
    verdicts(fakes, [4, 8])
    steps = []
    graph.run_plan("demo", REQUEST, on_step=steps.append)
    assert steps == ["guardrail", "portfolio", "retirement", "reporter", "judge", "reporter", "judge"]
