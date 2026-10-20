"""Real market prices from Finnhub, cached once per day, with honest fallbacks.
Every result says WHERE the price came from and HOW fresh it is."""
import json
import logging
import os
from datetime import date

import httpx

from app import config

log = logging.getLogger(__name__)

FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"


def _cache_path(symbol: str) -> str:
    return os.path.join(config.PRICE_CACHE_DIR, f"{symbol}.json")


def _read_cache(symbol: str) -> dict | None:
    try:
        with open(_cache_path(symbol), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_cache(data: dict):
    os.makedirs(config.PRICE_CACHE_DIR, exist_ok=True)
    with open(_cache_path(data["symbol"]), "w", encoding="utf-8") as f:
        json.dump(data, f)


def _fetch_finnhub(symbol: str) -> float:
    response = httpx.get(FINNHUB_QUOTE_URL, params={"symbol": symbol, "token": config.FINNHUB_API_KEY}, timeout=10)
    response.raise_for_status()
    price = response.json().get("c")          # "c" = current price
    if not price:                              # Finnhub returns 0 for unknown symbols
        raise ValueError(f"No price returned for {symbol}")
    return float(price)


def get_price(symbol: str) -> dict | None:
    symbol = symbol.upper()
    today = date.today().isoformat()
    if symbol == "CASH":
        return {"symbol": "CASH", "price": 1.0, "source": "cash", "as_of": today, "status": "live"}

    cached = _read_cache(symbol)
    if cached and cached["as_of"] == today:
        return {**cached, "status": "cached"}

    try:
        data = {"symbol": symbol, "price": _fetch_finnhub(symbol), "source": "Finnhub", "as_of": today}
        _write_cache(data)
        return {**data, "status": "live"}
    except Exception as e:                      # network error, rate limit, unknown symbol...
        log.warning("Price fetch failed for %s: %s", symbol, e)
        if cached:
            return {**cached, "status": "stale"}    # an old real price beats none, but we say so
        return None
