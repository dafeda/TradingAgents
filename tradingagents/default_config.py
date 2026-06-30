import os

_TRADINGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")

# Single source of truth for env-var → config-key overrides. To expose
# a new config key for environment-based override, add a row here — no
# entry-point script changes required. Coercion is driven by the type
# of the existing default, so users can keep writing plain strings in
# their .env file.
_ENV_OVERRIDES = {
    "TRADINGAGENTS_LLM_PROVIDER":         "llm_provider",
    "TRADINGAGENTS_DEEP_THINK_LLM":       "deep_think_llm",
    "TRADINGAGENTS_QUICK_THINK_LLM":      "quick_think_llm",
    "TRADINGAGENTS_LLM_BACKEND_URL":      "backend_url",
    "TRADINGAGENTS_MAX_DEBATE_ROUNDS":    "max_debate_rounds",
    "TRADINGAGENTS_MAX_RISK_ROUNDS":      "max_risk_discuss_rounds",
    "TRADINGAGENTS_CHECKPOINT_ENABLED":   "checkpoint_enabled",
    "TRADINGAGENTS_BENCHMARK_TICKER":     "benchmark_ticker",
    "TRADINGAGENTS_TEMPERATURE":          "temperature",
    # Provider-specific reasoning/thinking knobs (None = each provider's own
    # default). Settable here for non-interactive runs; the CLI also offers an
    # interactive choice, which is skipped when the matching var is set.
    "TRADINGAGENTS_GOOGLE_THINKING_LEVEL":   "google_thinking_level",
    "TRADINGAGENTS_OPENAI_REASONING_EFFORT": "openai_reasoning_effort",
    "TRADINGAGENTS_ANTHROPIC_EFFORT":        "anthropic_effort",
}


_BOOL_TRUE = ("true", "1", "yes", "on")
_BOOL_FALSE = ("false", "0", "no", "off")


def _coerce(value: str, reference):
    """Coerce env-var string to the type of the existing default value.

    Invalid values raise ``ValueError`` rather than silently falling back to a
    default — a misspelled boolean (e.g. ``treu``) or non-numeric int should fail
    loudly at startup, not quietly misconfigure an unattended run.
    """
    if isinstance(reference, bool):
        normalized = value.strip().lower()
        if normalized in _BOOL_TRUE:
            return True
        if normalized in _BOOL_FALSE:
            return False
        raise ValueError(
            f"expected a boolean ({'/'.join(_BOOL_TRUE + _BOOL_FALSE)}), got {value!r}"
        )
    if isinstance(reference, int) and not isinstance(reference, bool):
        return int(value)
    if isinstance(reference, float):
        return float(value)
    return value


def _apply_env_overrides(config: dict) -> dict:
    """Apply TRADINGAGENTS_* env vars to the config dict in-place."""
    for env_var, key in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_var)
        if raw is None or raw == "":
            continue
        try:
            config[key] = _coerce(raw, config.get(key))
        except ValueError as exc:
            raise ValueError(f"Invalid value for {env_var}: {exc}") from exc
    return config


DEFAULT_CONFIG = _apply_env_overrides({
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", os.path.join(_TRADINGAGENTS_HOME, "logs")),
    "data_cache_dir": os.getenv("TRADINGAGENTS_CACHE_DIR", os.path.join(_TRADINGAGENTS_HOME, "cache")),
    "memory_log_path": os.getenv("TRADINGAGENTS_MEMORY_LOG_PATH", os.path.join(_TRADINGAGENTS_HOME, "memory", "trading_memory.md")),
    # Optional cap on the number of resolved memory log entries. When set,
    # the oldest resolved entries are pruned once this limit is exceeded.
    # Pending entries are never pruned. None disables rotation entirely.
    "memory_log_max_entries": None,
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.5",
    "quick_think_llm": "gpt-5.4-mini",
    # When None, each provider's client falls back to its own default endpoint
    # (api.openai.com for OpenAI, generativelanguage.googleapis.com for Gemini, ...).
    # The CLI overrides this per provider when the user picks one. Keeping a
    # provider-specific URL here would leak (e.g. OpenAI's /v1 was previously
    # being forwarded to Gemini, producing malformed request URLs).
    "backend_url": None,
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "anthropic_effort": None,           # "high", "medium", "low"
    # Sampling temperature, forwarded to every provider when set. None leaves
    # each provider at its own default. Lower values reduce run-to-run
    # variation on models that honor it; reasoning models largely ignore it
    # and no setting makes LLM output bit-identical across runs (see README).
    "temperature": None,
    # Checkpoint/resume: when True, LangGraph saves state after each node
    # so a crashed run can resume from the last successful step.
    "checkpoint_enabled": False,
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # News / data fetching parameters
    # Increase for longer lookback strategies or to broaden macro coverage;
    # decrease to reduce token usage in agent prompts.
    "news_article_limit": 20,             # max articles per ticker (ticker-news)
    "global_news_article_limit": 10,      # max articles for global/macro news
    "global_news_lookback_days": 7,       # macro news lookback window
    # Search queries used by get_global_news for macro headlines. Extend or
    # replace to broaden geographic / sector coverage.
    "global_news_queries": [
        "TTF Dutch gas price front-month EUR/MWh",
        "EU gas storage AGSI fill level withdrawal",
        "LNG cargo Europe imports terminal sendout",
        "Norway pipeline gas flows maintenance outage",
        "EUA carbon price coal-gas switching",
        "Europe weather forecast cold spell heating demand",
    ],
    # RSS news feeds for the "rss_feeds" news vendor — the default news source
    # (see data_vendors["news_data"] below). Curated gas/energy newswires that
    # carry desk-relevant signal (LNG cargoes, Norway/supply outages, EU storage,
    # Henry Hub, geopolitics) at higher density than a generic finance feed.
    # The feeds ARE the relevance filter — curate them for the desk; add operator
    # feeds (TSOs, terminals) or paid wires here, or remove ones you don't want.
    # Each entry: name, url (RSS/Atom), topics (free-text tags, informational
    # only). A feed that errors is logged and skipped, never aborting the batch.
    # These URLs were verified reachable with fresh, dated entries; RSS exposes
    # only the latest items, so for pinned historical/backtest dates the chain
    # falls through to yfinance (which can query a past window).
    "rss_news_feeds": [
        {
            "name": "Natural Gas Intelligence",
            "url": "https://www.naturalgasintel.com/feed/",
            "topics": ["henry-hub", "lng", "storage", "us-gas"],
        },
        {
            "name": "Gas Outlook",
            "url": "https://gasoutlook.com/feed/",
            "topics": ["europe", "lng", "policy", "demand"],
        },
        {
            "name": "Offshore Energy",
            "url": "https://www.offshore-energy.biz/feed/",
            "topics": ["lng", "offshore", "supply"],
        },
        {
            "name": "Oilprice",
            "url": "https://oilprice.com/rss/main",
            "topics": ["geopolitics", "lng", "energy"],
        },
        {
            "name": "Rigzone",
            "url": "https://www.rigzone.com/news/rss/rigzone_latest.aspx",
            "topics": ["upstream", "norway", "outages"],
        },
    ],
    # Data vendor configuration
    # Category-level configuration (default for all tools in category).
    # The configured value is the exact vendor chain — requests are NOT silently
    # routed to vendors you didn't choose. "default" uses all available vendors.
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: yfinance (TTF=F / NG=F OHLCV)
        "technical_indicators": "yfinance",  # Options: yfinance
        "news_data": "rss_feeds,yfinance",   # RSS energy wires first, Yahoo fallback. Options: rss_feeds, yfinance (see rss_news_feeds)
        "macro_data": "fred",                # Options: fred (needs FRED_API_KEY)
        "gas_storage": "gie",                # Options: gie (needs GIE_API_KEY)
        "us_gas_storage": "eia",              # Options: eia (needs EIA_API_KEY) — Henry Hub
        "weather_data": "open_meteo",        # Options: open_meteo (keyless)
        "us_weather_data": "open_meteo",      # Options: open_meteo (keyless) — Henry Hub
        "pipeline_flows": "entsog",          # Options: entsog (keyless)
        "carbon_data": "yfinance",           # EUA carbon proxy via yfinance
        "prediction_markets": "polymarket",  # Options: polymarket (keyless)
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "yfinance",  # Override category default
    },
    # Benchmark for alpha calculation in the reflection layer. ``None`` lets
    # the instrument profile supply the symmetric spread leg (TTF=F -> NG=F,
    # NG=F -> TTF=F) so alpha reads as the TTF–HH spread in either direction.
    # Set to a ticker to force an explicit benchmark that overrides the profile.
    "benchmark_ticker": None,
    # Gas desk quote currency is resolved per-instrument from the profile
    # (EUR/MWh for Dutch TTF, USD/MMBtu for Henry Hub). Kept here as ``None``
    # for backward compatibility; agents read the unit from the profile prose.
    "quote_currency": None,
})
