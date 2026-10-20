"""Tools the agents may call. READ-ONLY, locked to one user, and everything they return is recorded in `facts`."""
from langchain_core.tools import tool

from app import db, market, simulation

CONCENTRATION_LIMIT = 0.20     # one non-cash position above 20% of the portfolio = concentration risk


def value_portfolio(user_id: str) -> dict:
    rows, total = [], 0.0
    for h in db.get_holdings(user_id):
        quote = market.get_price(h["symbol"])
        if quote:
            price, source, as_of, status = quote["price"], quote["source"], quote["as_of"], quote["status"]
        else:
            price, source, as_of, status = float(h["avg_cost"]), "purchase price", None, "unavailable"
        value = float(h["quantity"]) * price
        total += value
        rows.append({"symbol": h["symbol"], "name": h.get("name") or h["symbol"],
                     "asset_class": h["asset_class"], "quantity": float(h["quantity"]),
                     "price": round(price, 2), "value": round(value, 2),
                     "price_source": source, "price_date": as_of, "price_status": status})

    by_class = {}
    for r in rows:
        by_class[r["asset_class"]] = by_class.get(r["asset_class"], 0.0) + r["value"]
    allocation = {c: round(v / total, 4) for c, v in by_class.items()} if total else {"cash": 1.0}
    concentrated = [r["symbol"] for r in rows
                    if total and r["asset_class"] != "cash" and r["value"] / total > CONCENTRATION_LIMIT]
    return {"total_value": round(total, 2), "allocation": allocation,
            "concentrated_positions": concentrated, "holdings": rows}


def make_tools(user_id: str) -> tuple[dict, dict]:
    facts = {}

    @tool
    def get_portfolio() -> dict:
        """Get the user's holdings valued at current market prices: total value, allocation by
        asset class, concentration risks, and each price's source, date and status."""
        facts["portfolio"] = value_portfolio(user_id)
        return facts["portfolio"]

    @tool
    def run_retirement_simulation(monthly_contribution: float, years_to_retirement: int,
                                  desired_annual_income: float) -> dict:
        """Monte Carlo simulation (10,000 futures) of the user's portfolio until retirement.
        monthly_contribution: monthly savings in dollars. years_to_retirement: retirement_age minus age.
        desired_annual_income: yearly income wanted in retirement, in today's dollars."""
        portfolio = facts.get("portfolio") or value_portfolio(user_id)
        target = desired_annual_income / 0.04          # "4% rule"
        facts["simulation"] = simulation.simulate_retirement(
            portfolio["total_value"], portfolio["allocation"], monthly_contribution, years_to_retirement, target)
        return facts["simulation"]

    return {"get_portfolio": get_portfolio, "run_retirement_simulation": run_retirement_simulation}, facts
