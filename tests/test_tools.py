from app import db, market, tools


def test_portfolio_valuation_uses_live_prices_and_flags_concentration(monkeypatch):
    monkeypatch.setattr(db, "get_holdings", lambda user_id: [
        {"symbol": "VTI", "quantity": 10, "avg_cost": 200, "asset_class": "equity"},
        {"symbol": "CASH", "quantity": 1000, "avg_cost": 1, "asset_class": "cash"}])
    prices = {"VTI": {"symbol": "VTI", "price": 300.0, "source": "Finnhub", "as_of": "2026-10-18", "status": "live"},
              "CASH": {"symbol": "CASH", "price": 1.0, "source": "cash", "as_of": "2026-10-18", "status": "live"}}
    monkeypatch.setattr(market, "get_price", lambda symbol: prices[symbol])
    p = tools.value_portfolio("demo")
    assert p["total_value"] == 4000.0                     # 10 x 300 + 1000
    assert p["allocation"] == {"equity": 0.75, "cash": 0.25}
    assert p["concentrated_positions"] == ["VTI"]


def test_missing_price_falls_back_to_purchase_price(monkeypatch):
    monkeypatch.setattr(db, "get_holdings", lambda user_id: [
        {"symbol": "XYZ", "quantity": 2, "avg_cost": 50, "asset_class": "equity"}])
    monkeypatch.setattr(market, "get_price", lambda symbol: None)
    row = tools.value_portfolio("demo")["holdings"][0]
    assert row["value"] == 100.0 and row["price_status"] == "unavailable"


def test_tools_record_facts(monkeypatch):
    monkeypatch.setattr(tools, "value_portfolio", lambda user_id: {"total_value": 1000.0, "allocation": {"cash": 1.0}})
    tool_set, facts = tools.make_tools("demo")
    tool_set["get_portfolio"].invoke({})
    tool_set["run_retirement_simulation"].invoke(
        {"monthly_contribution": 100, "years_to_retirement": 10, "desired_annual_income": 4000})
    assert set(facts) == {"portfolio", "simulation"}
    assert facts["simulation"]["target"] == 100_000       # 4000 / 0.04
