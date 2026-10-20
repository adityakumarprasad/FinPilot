"""Monte Carlo retirement simulation: 10,000 possible futures instead of one fixed growth rate.
Pure Python + numpy: zero LLM calls, fully reproducible (fixed random seed)."""
import numpy as np

# Long-run REAL (after-inflation) annual returns, rounded from historical ranges.
# Working in real returns means every result is in TODAY's money.
ASSUMPTIONS = {
    "equity": {"mean": 0.05, "volatility": 0.16},
    "bond": {"mean": 0.015, "volatility": 0.06},
    "cash": {"mean": 0.0, "volatility": 0.01},
}
SIMULATIONS = 10_000


def simulate_retirement(current_value: float, allocation: dict, monthly_contribution: float,
                        years: int, target: float, seed: int = 42) -> dict:
    if not 1 <= years <= 70:
        raise ValueError("years must be between 1 and 70")
    if monthly_contribution < 0 or current_value < 0 or target <= 0:
        raise ValueError("amounts must be positive")

    # Portfolio return = weighted mix of the asset classes.
    mean = sum(w * ASSUMPTIONS.get(a, ASSUMPTIONS["equity"])["mean"] for a, w in allocation.items())
    # Weighted volatility assumes assets move together: a CONSERVATIVE simplification.
    volatility = sum(w * ASSUMPTIONS.get(a, ASSUMPTIONS["equity"])["volatility"] for a, w in allocation.items())

    rng = np.random.default_rng(seed)                                   # same seed -> same result every time
    yearly_returns = rng.normal(mean, volatility, size=(SIMULATIONS, years))   # one row = one possible future

    balance = np.full(SIMULATIONS, float(current_value))
    for year in range(years):
        balance = balance * (1 + yearly_returns[:, year]) + monthly_contribution * 12   # grow, then add savings

    return {
        "success_probability": round(float((balance >= target).mean()), 3),
        "median": round(float(np.median(balance)), 0),
        "bad_case_p10": round(float(np.percentile(balance, 10)), 0),
        "good_case_p90": round(float(np.percentile(balance, 90)), 0),
        "target": round(target, 0),
        "inputs": {"current_value": round(current_value, 2), "monthly_contribution": monthly_contribution,
                   "years": years, "allocation": allocation},
        "assumptions": {"expected_real_return": round(mean, 4), "volatility": round(volatility, 4),
                        "simulations": SIMULATIONS, "money": "today's dollars (after inflation)"},
    }