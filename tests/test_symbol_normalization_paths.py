"""Symbol normalization must apply on every yfinance path, not just price fetch.

Regression tests for #984 (reflection returns) and the news path: a broker
symbol like TTF must resolve to the same Yahoo symbol (TTF=F) that the price
path uses, so realized-return and news lookups hit the right instrument
instead of failing/mismatching.
"""
import pandas as pd

import tradingagents.dataflows.yfinance_news as ynews
import tradingagents.graph.trading_graph as tg
from tradingagents.graph.trading_graph import TradingAgentsGraph


def test_fetch_returns_normalizes_symbol(monkeypatch):
    queried = []

    class FakeTicker:
        def __init__(self, symbol):
            queried.append(symbol)

        def history(self, *args, **kwargs):
            return pd.DataFrame({"Close": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0]})

    monkeypatch.setattr(tg.yf, "Ticker", FakeTicker)

    # _fetch_returns does not use ``self``; call unbound to avoid building the graph.
    raw, alpha, days = TradingAgentsGraph._fetch_returns(
        None, "TTF", "2025-01-02", holding_days=5, benchmark="NG=F"
    )

    assert queried[0] == "TTF=F"  # traded symbol normalized
    assert queried[1] == "NG=F"   # benchmark left as the canonical symbol
    assert raw is not None and days is not None


def test_news_lookup_normalizes_symbol(monkeypatch):
    seen = {}

    class FakeTicker:
        def __init__(self, symbol):
            seen["symbol"] = symbol

        def get_news(self, count):
            return []

    monkeypatch.setattr(ynews.yf, "Ticker", FakeTicker)
    monkeypatch.setattr(ynews, "yf_retry", lambda fn: fn())

    out = ynews.get_news_yfinance("TTF", "2025-01-01", "2025-01-10")

    assert seen["symbol"] == "TTF=F"   # news queried with the canonical symbol
    assert "TTF" in out               # the user's ticker stays in the report
    assert "TTF=F" in out             # provenance noted
