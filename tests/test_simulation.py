import pytest

from app import simulation


def test_zero_volatility_matches_compound_interest_formula(monkeypatch):
    # With no randomness every future is identical, so the result must equal the textbook formula.
    monkeypatch.setitem(simulation.ASSUMPTIONS, "equity", {"mean": 0.05, "volatility": 0.0})
    result = simulation.simulate_retirement(10_000, {"equity": 1.0}, 100, years=10, target=1)
    expected = 10_000 * 1.05 ** 10 + 1200 * (1.05 ** 10 - 1) / 0.05
    assert result["median"] == pytest.approx(expected, abs=1)


def test_results_are_reproducible():
    args = (50_000, {"equity": 0.6, "bond": 0.4}, 500, 25, 600_000)
    assert simulation.simulate_retirement(*args) == simulation.simulate_retirement(*args)


def test_saving_more_increases_success_probability():
    low = simulation.simulate_retirement(20_000, {"equity": 1.0}, 200, 30, 800_000)
    high = simulation.simulate_retirement(20_000, {"equity": 1.0}, 1500, 30, 800_000)
    assert high["success_probability"] > low["success_probability"]


def test_percentiles_are_ordered():
    r = simulation.simulate_retirement(20_000, {"equity": 1.0}, 500, 30, 500_000)
    assert r["bad_case_p10"] < r["median"] < r["good_case_p90"]


def test_invalid_years_are_rejected():
    with pytest.raises(ValueError):
        simulation.simulate_retirement(1000, {"equity": 1.0}, 100, years=0, target=1000)
