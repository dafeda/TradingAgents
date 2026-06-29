"""RSS/Atom news vendor for European gas-market sources.

The default ``news_data`` vendor (chained ahead of yfinance), since curated
energy newswires carry desk-relevant signal — LNG cargoes, Norway/supply
outages, EU storage, Henry Hub, geopolitics — at higher density than a generic
finance feed. Revert to Yahoo only with:

    config["data_vendors"]["news_data"] = "yfinance"

Feeds are configured as a list of ``{"name", "url", "topics"}`` dicts under the
``rss_news_feeds`` config key, so sources are added/removed without code
changes. The feeds themselves are the relevance filter — curate them for the
desk (TSOs, terminal/LNG operators, energy wires) rather than keyword-filtering
here, which is brittle.

Best suited to live runs. RSS exposes only the latest items with no
point-in-time query, so it cannot backfill a historical/backtest window — for
pinned past dates it raises (nothing in-window) and the default
``"rss_feeds,yfinance"`` chain falls through to Yahoo, which can query a past
window.

Look-ahead safety reuses the exact window filter from the yfinance news path
(``_in_news_window``): future-dated and (in a backtest window) undated articles
are excluded, so this vendor inherits the #992/#1007 guarantees.

Empty results raise ``NoMarketDataError`` rather than returning a sentinel
string: the router only advances to the next vendor on an exception, so raising
is what lets a chain like ``"rss_feeds,yfinance"`` actually fall through to
Yahoo when RSS has nothing.
"""

import html
import logging
import re
from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser
import requests
from dateutil.relativedelta import relativedelta

from .config import get_config
from .errors import NoMarketDataError

# Reuse the yfinance look-ahead window so both news vendors share one definition
# of "in range" (and the same backtest safety). Private import is deliberate:
# duplicating the rule would risk the two vendors drifting apart.
from .yfinance_news import _in_news_window

logger = logging.getLogger(__name__)

# Per-feed network timeout (seconds). Smaller than the 30s used by single-call
# vendors because we fetch several feeds per request and want bounded latency.
REQUEST_TIMEOUT = 15

# Some feeds reject the default urllib/requests agent; present a plain one.
_USER_AGENT = "TradingAgents/RSS (+https://github.com/anomalyco/opencode)"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    """RSS summaries often carry HTML; flatten to clean text for the prompt."""
    if not text:
        return ""
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", text))).strip()


def _published_datetime(entry) -> datetime | None:
    """Best-effort publish datetime (naive) for a feed entry, or None.

    Prefers feedparser's pre-parsed struct_time; falls back to RFC-822 string
    parsing. Returns naive datetimes to match ``_in_news_window``'s expectation.
    """
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6])
        except (TypeError, ValueError):
            pass
    raw = entry.get("published") or entry.get("updated")
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
            return dt.replace(tzinfo=None) if dt and dt.tzinfo else dt
        except (TypeError, ValueError):
            pass
    return None


def _extract_entry(entry, source_name: str) -> dict:
    """Normalize a feedparser entry into the same shape the formatter expects."""
    title = (entry.get("title") or "").strip() or "No title"
    summary = _strip_html(entry.get("summary") or entry.get("description") or "")
    link = (entry.get("link") or "").strip()
    return {
        "title": title,
        "summary": summary,
        "publisher": source_name,
        "link": link,
        "pub_date": _published_datetime(entry),
    }


def _fetch_feed(feed: dict) -> list:
    """Fetch and parse one feed, returning its entries.

    Network/parse errors propagate to the caller, which isolates them per feed
    so one bad source never sinks the batch.
    """
    url = feed["url"]
    response = requests.get(
        url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": _USER_AGENT}
    )
    response.raise_for_status()
    return feedparser.parse(response.content).entries


def _collect(start_dt: datetime, end_dt: datetime) -> tuple[list, int]:
    """Gather window-filtered, de-duplicated articles across all configured feeds.

    Returns ``(articles, errored_feed_count)``. Dedup is by link first, then by
    normalized title, so the same story syndicated across feeds appears once.
    """
    feeds = get_config().get("rss_news_feeds") or []
    articles: list[dict] = []
    seen_links: set[str] = set()
    seen_titles: set[str] = set()
    errored = 0

    for feed in feeds:
        name = feed.get("name") or feed.get("url", "RSS")
        try:
            entries = _fetch_feed(feed)
        except Exception as exc:  # network, parse, or a malformed feed entry
            errored += 1
            logger.warning("RSS feed %r failed: %s", name, exc)
            continue

        for entry in entries:
            data = _extract_entry(entry, name)
            if not _in_news_window(data["pub_date"], start_dt, end_dt):
                continue
            link_key = data["link"].lower()
            title_key = data["title"].lower()
            if (link_key and link_key in seen_links) or title_key in seen_titles:
                continue
            if link_key:
                seen_links.add(link_key)
            seen_titles.add(title_key)
            articles.append(data)

    return articles, errored


def _format(articles: list) -> str:
    """Render articles in the same markdown layout as the yfinance news vendor."""
    out = ""
    for a in articles:
        out += f"### {a['title']} (source: {a['publisher']})\n"
        if a["summary"]:
            out += f"{a['summary']}\n"
        if a["link"]:
            out += f"Link: {a['link']}\n"
        out += "\n"
    return out


def _no_feeds_detail() -> str:
    return "no RSS feeds configured (set 'rss_news_feeds' in config)"


def get_news_rss_feeds(ticker: str, start_date: str, end_date: str) -> str:
    """Retrieve gas-relevant news from configured RSS feeds for a date window.

    Args:
        ticker: Ticker symbol (used only in the report header; the feeds are the
            relevance filter, so no per-ticker keyword filtering is applied).
        start_date: Start date in yyyy-mm-dd format.
        end_date: End date in yyyy-mm-dd format.

    Returns:
        A markdown report of in-window articles.

    Raises:
        NoMarketDataError: when no feeds are configured or no article falls in
            the window — so a vendor chain falls through to the next vendor.
    """
    config = get_config()
    limit = config["news_article_limit"]
    if not config.get("rss_news_feeds"):
        raise NoMarketDataError(ticker, detail=_no_feeds_detail())

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    articles, errored = _collect(start_dt, end_dt)
    articles.sort(key=lambda a: a["pub_date"] or datetime.min, reverse=True)
    articles = articles[:limit]

    if not articles:
        extra = f" ({errored} feed(s) errored)" if errored else ""
        raise NoMarketDataError(
            ticker, detail=f"no RSS articles between {start_date} and {end_date}{extra}"
        )

    return f"## {ticker} News (RSS), from {start_date} to {end_date}:\n\n{_format(articles)}"


def get_global_news_rss_feeds(
    curr_date: str,
    look_back_days: int | None = None,
    limit: int | None = None,
) -> str:
    """Retrieve macro/global news from configured RSS feeds.

    Args:
        curr_date: Current date in yyyy-mm-dd format.
        look_back_days: Lookback window; ``None`` uses ``global_news_lookback_days``
            (shared with the yfinance global-news tool so switching vendors does
            not silently change the window).
        limit: Max articles; ``None`` uses ``global_news_article_limit``.

    Returns:
        A markdown report of in-window articles.

    Raises:
        NoMarketDataError: when no feeds are configured or no article falls in
            the window — so a vendor chain falls through to the next vendor.
    """
    config = get_config()
    if look_back_days is None:
        look_back_days = config["global_news_lookback_days"]
    if limit is None:
        limit = config["global_news_article_limit"]
    if not config.get("rss_news_feeds"):
        raise NoMarketDataError("global", detail=_no_feeds_detail())

    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = curr_dt - relativedelta(days=look_back_days)
    start_date = start_dt.strftime("%Y-%m-%d")
    articles, errored = _collect(start_dt, curr_dt)
    articles.sort(key=lambda a: a["pub_date"] or datetime.min, reverse=True)
    articles = articles[:limit]

    if not articles:
        extra = f" ({errored} feed(s) errored)" if errored else ""
        raise NoMarketDataError(
            "global", detail=f"no RSS articles between {start_date} and {curr_date}{extra}"
        )

    return f"## Global Market News (RSS), from {start_date} to {curr_date}:\n\n{_format(articles)}"
