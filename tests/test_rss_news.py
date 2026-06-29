"""RSS news vendor: window filtering (look-ahead safe), dedup, per-feed
isolation, and raise-on-empty so a vendor chain falls through to yfinance.

The router only advances to the next vendor on an exception, so an empty RSS
result MUST raise NoMarketDataError (not return a sentinel string) for
"rss_feeds,yfinance" to reach Yahoo. These tests pin that contract.
"""
import copy
from datetime import datetime, timedelta

import pytest

import tradingagents.dataflows.config as config_module
import tradingagents.default_config as default_config
from tradingagents.dataflows import interface, rss_news
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.errors import NoMarketDataError


def _reset_config():
    # Hard reset (matches test_vendor_routing): set_config merges, so replace the
    # global outright to avoid keys leaking across tests.
    config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)


@pytest.fixture(autouse=True)
def _config():
    _reset_config()
    # One feed configured by default so the "no feeds" guard passes; _fetch_feed
    # is monkeypatched per test, so the URL is never actually hit.
    set_config({"rss_news_feeds": [{"name": "Feed A", "url": "http://a/feed"}]})
    yield
    _reset_config()


def _entry(title, dt=None, link="", summary="body"):
    e = {"title": title, "summary": summary, "link": link}
    if dt is not None:
        e["published_parsed"] = dt.timetuple()
    return e


def _patch_entries(monkeypatch, entries):
    monkeypatch.setattr(rss_news, "_fetch_feed", lambda feed: entries)


# --- registration ---------------------------------------------------------

@pytest.mark.unit
def test_rss_feeds_registered():
    assert "rss_feeds" in interface.VENDOR_METHODS["get_news"]
    assert "rss_feeds" in interface.VENDOR_METHODS["get_global_news"]
    assert "rss_feeds" in interface.VENDOR_LIST


@pytest.mark.unit
def test_default_news_vendor_is_rss_then_yfinance():
    # RSS is the default news source, with yfinance chained as fallback so
    # historical/backtest windows (where RSS has nothing) still resolve.
    assert default_config.DEFAULT_CONFIG["data_vendors"]["news_data"] == "rss_feeds,yfinance"


# --- window filtering (look-ahead safety) ---------------------------------

@pytest.mark.unit
def test_in_window_article_included(monkeypatch):
    _patch_entries(monkeypatch, [_entry("Storage draw accelerates", datetime(2025, 5, 5), "http://x/1")])
    out = rss_news.get_news_rss_feeds("TTF=F", "2025-05-01", "2025-05-09")
    assert "Storage draw accelerates" in out
    assert "source: Feed A" in out
    assert "## TTF=F News (RSS)" in out


@pytest.mark.unit
def test_future_excluded_in_backtest(monkeypatch):
    _patch_entries(monkeypatch, [_entry("Future event", datetime(2025, 6, 1), "http://x/2")])
    with pytest.raises(NoMarketDataError):
        rss_news.get_news_rss_feeds("TTF=F", "2025-05-01", "2025-05-09")


@pytest.mark.unit
def test_old_excluded(monkeypatch):
    _patch_entries(monkeypatch, [_entry("Old event", datetime(2025, 4, 1), "http://x/3")])
    with pytest.raises(NoMarketDataError):
        rss_news.get_news_rss_feeds("TTF=F", "2025-05-01", "2025-05-09")


@pytest.mark.unit
def test_undated_excluded_in_backtest(monkeypatch):
    _patch_entries(monkeypatch, [_entry("Undated", None, "http://x/u")])
    with pytest.raises(NoMarketDataError):
        rss_news.get_news_rss_feeds("TTF=F", "2025-05-01", "2025-05-09")


@pytest.mark.unit
def test_undated_kept_in_live_window(monkeypatch):
    _patch_entries(monkeypatch, [_entry("Undated live", None, "http://x/u")])
    today = datetime.now()
    out = rss_news.get_news_rss_feeds(
        "TTF=F",
        (today - timedelta(days=2)).strftime("%Y-%m-%d"),
        today.strftime("%Y-%m-%d"),
    )
    assert "Undated live" in out


# --- dedup & resilience ---------------------------------------------------

@pytest.mark.unit
def test_dedupe_by_link_and_title(monkeypatch):
    _patch_entries(monkeypatch, [
        _entry("Same story", datetime(2025, 5, 5), "http://x/dup"),
        _entry("Same story", datetime(2025, 5, 5), "http://x/dup"),
        _entry("Other story", datetime(2025, 5, 6), "http://x/dup2"),
    ])
    out = rss_news.get_news_rss_feeds("TTF=F", "2025-05-01", "2025-05-09")
    assert out.count("Same story") == 1
    assert "Other story" in out


@pytest.mark.unit
def test_one_broken_feed_does_not_sink_others(monkeypatch):
    set_config({"rss_news_feeds": [
        {"name": "Bad", "url": "http://bad"},
        {"name": "Good", "url": "http://good"},
    ]})

    def fake_fetch(feed):
        if feed["url"] == "http://bad":
            raise RuntimeError("boom")
        return [_entry("Good item", datetime(2025, 5, 5), "http://g/1")]

    monkeypatch.setattr(rss_news, "_fetch_feed", fake_fetch)
    out = rss_news.get_news_rss_feeds("TTF=F", "2025-05-01", "2025-05-09")
    assert "Good item" in out
    assert "source: Good" in out


# --- raise-on-empty contract ----------------------------------------------

@pytest.mark.unit
def test_empty_after_filter_raises(monkeypatch):
    _patch_entries(monkeypatch, [_entry("Future", datetime(2025, 6, 1), "http://x/f")])
    with pytest.raises(NoMarketDataError):
        rss_news.get_news_rss_feeds("TTF=F", "2025-05-01", "2025-05-09")


@pytest.mark.unit
def test_no_feeds_configured_raises():
    set_config({"rss_news_feeds": []})
    with pytest.raises(NoMarketDataError):
        rss_news.get_news_rss_feeds("TTF=F", "2025-05-01", "2025-05-09")


# --- global news ----------------------------------------------------------

@pytest.mark.unit
def test_global_news_basic(monkeypatch):
    _patch_entries(monkeypatch, [_entry("Macro item", datetime(2025, 5, 5), "http://m/1")])
    out = rss_news.get_global_news_rss_feeds("2025-05-09", look_back_days=7, limit=10)
    assert "Macro item" in out
    assert "## Global Market News (RSS)" in out


@pytest.mark.unit
def test_global_news_empty_raises(monkeypatch):
    _patch_entries(monkeypatch, [_entry("Future macro", datetime(2025, 7, 1), "http://m/2")])
    with pytest.raises(NoMarketDataError):
        rss_news.get_global_news_rss_feeds("2025-05-09", look_back_days=7, limit=10)


# --- routing integration --------------------------------------------------

@pytest.mark.unit
def test_chain_falls_through_to_yfinance(monkeypatch):
    # Empty RSS (raises NoMarketDataError) must let "rss_feeds,yfinance" reach Yahoo.
    def raise_no_data(*a, **k):
        raise NoMarketDataError("TTF=F", detail="empty")

    monkeypatch.setitem(interface.VENDOR_METHODS["get_news"], "rss_feeds", raise_no_data)
    monkeypatch.setitem(interface.VENDOR_METHODS["get_news"], "yfinance", lambda *a, **k: "YF-DATA")
    set_config({"data_vendors": {"news_data": "rss_feeds,yfinance"}})
    out = interface.route_to_vendor("get_news", "TTF=F", "2025-05-01", "2025-05-09")
    assert out == "YF-DATA"


@pytest.mark.unit
def test_rss_only_empty_returns_no_data_sentinel(monkeypatch):
    def raise_no_data(*a, **k):
        raise NoMarketDataError("TTF=F", detail="empty")

    monkeypatch.setitem(interface.VENDOR_METHODS["get_news"], "rss_feeds", raise_no_data)
    set_config({"data_vendors": {"news_data": "rss_feeds"}})
    out = interface.route_to_vendor("get_news", "TTF=F", "2025-05-01", "2025-05-09")
    assert "NO_DATA_AVAILABLE" in out
