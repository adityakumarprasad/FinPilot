from datetime import date

import pytest

from app import config, market


@pytest.fixture(autouse=True)
def temp_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PRICE_CACHE_DIR", str(tmp_path))


def broken(symbol):
    raise ConnectionError("Finnhub down")


def test_cash_is_always_one():
    assert market.get_price("CASH")["price"] == 1.0


def test_live_price_is_cached_for_the_day(monkeypatch):
    monkeypatch.setattr(market, "_fetch_finnhub", lambda symbol: 270.0)
    assert market.get_price("VTI")["status"] == "live"
    monkeypatch.setattr(market, "_fetch_finnhub", lambda symbol: pytest.fail("should use the cache"))
    assert market.get_price("VTI") == {"symbol": "VTI", "price": 270.0, "source": "Finnhub",
                                       "as_of": date.today().isoformat(), "status": "cached"}


def test_failed_fetch_falls_back_to_stale_price(monkeypatch):
    market._write_cache({"symbol": "BND", "price": 72.5, "source": "Finnhub", "as_of": "2026-01-02"})
    monkeypatch.setattr(market, "_fetch_finnhub", broken)
    quote = market.get_price("BND")
    assert quote["status"] == "stale" and quote["as_of"] == "2026-01-02"


def test_no_price_at_all_returns_none(monkeypatch):
    monkeypatch.setattr(market, "_fetch_finnhub", broken)
    assert market.get_price("XYZ") is None
