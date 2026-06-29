"""Per-instrument profiles for the gas desk.

The desk trades two gas futures as first-class instruments:

    ``TTF=F``  Dutch TTF front-month (EUR/MWh)  — full EU fundamentals stack
    ``NG=F``   Henry Hub front-month (USD/MMBtu) — price/technical/news only

A profile bundles the per-instrument prose and metadata that agents, the
benchmark resolver, and the CLI need to treat each contract correctly. The
profile is **pure data** — no network, no dataflow imports — so it is safe
to call from anywhere, including the instrument-identity anchor
that runs once at graph start (``build_instrument_context``).

Henry Hub has no US supply/demand data vendors yet (no EIA storage, US
weather, or US pipeline/LNG flow vendor). Its profile therefore marks
``fundamentals_available=False``; the CLI drops the fundamentals analyst
when trading ``NG=F`` and surfaces a notice. US vendors are a follow-up
phase — flipping that flag to ``True`` and stopping the CLI drop is the
only wiring change required when they land.

The TTF profile prose is moved verbatim from the agent prompts that
previously hardcoded it; the NG=F prose is new, with the spread economics
inverted correctly (a wide TTF–HH spread is bullish for *both* legs, but
for different reasons: TTF = cargoes pulled *to* Europe; HH = export
pull *from* the US draining domestic supply).
"""

from __future__ import annotations

from dataclasses import dataclass

from tradingagents.dataflows.symbol_utils import normalize_symbol


@dataclass(frozen=True)
class InstrumentProfile:
    """Static description of a tradable instrument."""

    ticker: str
    display_name: str            # "Dutch TTF" / "Henry Hub"
    currency_unit: str           # "EUR/MWh" / "USD/MMBtu"
    region: str                  # "EU" / "US"
    benchmark_ticker: str        # symmetric spread leg (NG=F / TTF=F)
    fundamentals_available: bool # False for NG=F until US vendors land

    # Identity line appended after "The instrument to analyze is `<ticker>`,".
    context_description: str

    # Per-analyst context prose (appended to each analyst's system message).
    market_note: str             # market analyst's instrument-specific note
    news_note: str               # news analyst's instrument-specific note
    fundamentals_note: str       # fundamentals analyst's framing (NG=F: unused)

    # Sentiment analyst: first paragraph (role + drivers). Formatted with
    # {ticker}, {start_date}, {end_date}; the news block + output fields are
    # appended by ``_build_gas_message`` so they stay in one place.
    sentiment_framing: str

    # Bull/bear researcher framing (the spread-direction logic differs per leg).
    researcher_framing_bull: str
    researcher_framing_bear: str

    # Trader's description of the analyst inputs it is synthesising.
    trader_inputs_desc: str


_TTF_PROFILE = InstrumentProfile(
    ticker="TTF=F",
    display_name="Dutch TTF",
    currency_unit="EUR/MWh",
    region="EU",
    benchmark_ticker="NG=F",
    fundamentals_available=True,
    context_description="a gas contract priced in EUR/MWh (Dutch TTF)",
    market_note=(
        "\n\nThis is Dutch TTF gas (TTF=F), priced in EUR/MWh. Front-month futures carry strong seasonality (winter heating premium, summer injection) and roll effects — distinguish trend from roll. Compare against NATGAS Henry Hub (NG=F) for the TTF–HH spread (global LNG arbitrage); a widening spread signals Europe pulling cargoes. Read storage-season context alongside indicators."
    ),
    news_note=(
        " This is Dutch TTF gas: prioritise EU storage, LNG, Norway flows, EUA carbon, weather, and geopolitics; use get_macro_indicators with 'ecb_rate', 'eurusd', or 'eu_inflation' for the euro-area macro backdrop."
    ),
    fundamentals_note=(
        "You are a European gas supply/demand analyst covering Dutch TTF. Write a comprehensive fundamentals report on the gas balance and price drivers to inform traders. Build the supply/demand picture: storage fill vs the seasonal norm, heating/cooling demand, pipeline supply, and coal-gas switching."
        " Use the tools: `get_gas_storage` (AGSI+ fill %, net withdrawal vs storage trajectory — the key fundamental), `get_weather` (NW-Europe HDD/CDD; high HDD = strong heating demand), `get_pipeline_flows` (Norway pipe + LNG sendout; a drop tightens the balance), and `get_carbon_price` (EUA; dear carbon favours gas over coal). State whether the balance is tight or loose and the directional read for TTF, with supporting numbers."
        " Append a Markdown table summarizing each driver (storage, weather, flows, carbon), its level vs normal, and its bullish/bearish tilt."
    ),
    sentiment_framing=(
        "You are a European energy market positioning analyst. Produce a sentiment report for {ticker} (Dutch TTF gas) covering {start_date} to {end_date}. There is no retail cashtag feed for gas, so read positioning from energy news flow: supply outages, LNG cargoes, storage headlines, weather scares, EUA carbon, Norway maintenance, and regulatory/geopolitical signals."
    ),
    researcher_framing_bull=(
        "You are a Bull Analyst advocating for a long TTF gas position. Your task is to build a strong, evidence-based case emphasizing a tightening supply/demand balance, structural support, and positive market indicators. Leverage the provided research and data to address concerns and counter bearish arguments effectively.\n"
        "For TTF gas, read 'growth' as a tightening balance (storage below the seasonal norm, cold-weather demand, Norway/LNG supply risk, EUA-driven gas-for-coal switching) and a favourable TTF–Henry Hub spread; 'competitive advantage' as supply security and storage optionality. Anchor the case in fundamentals, spreads, and seasonality.\n\n"
        "Key points to focus on:\n"
        "- Tightening Balance: Highlight storage below the seasonal norm, cold-weather heating demand, and supply risk (Norway maintenance, LNG diversions) tightening the European gas balance.\n"
        "- Structural Support: Emphasize supply insecurity, limited storage optionality, EUA-driven gas-for-coal switching, and a favourable TTF–Henry Hub spread pulling LNG cargoes to Europe.\n"
        "- Positive Indicators: Use fundamentals (storage, pipeline/LNG flows, weather/degree-days), spreads, and recent bullish news as evidence.\n"
        "- Bear Counterpoints: Critically analyze the bear argument with specific data and sound reasoning, addressing concerns thoroughly and showing why the bull perspective holds stronger merit.\n"
        "- Engagement: Present your argument in a conversational style, engaging directly with the bear analyst's points and debating effectively rather than just listing data."
    ),
    researcher_framing_bear=(
        "You are a Bear Analyst making the case against a long TTF gas position. Your goal is to present a well-reasoned argument emphasizing risks, challenges, and negative indicators. Leverage the provided research and data to highlight potential downsides and counter bullish arguments effectively.\n"
        "For TTF gas, read 'risks' as a loose balance (storage above the seasonal norm, mild weather, strong LNG/Norway supply, weak EUA support) and an unfavourable TTF–Henry Hub spread; flag injection-season seasonality and curve roll. Anchor the case in fundamentals, spreads, and seasonality.\n\n"
        "Key points to focus on:\n"
        "- Loose Balance: Highlight storage above the seasonal norm, mild weather suppressing heating demand, and ample supply (strong Norway flows, abundant LNG sendout) loosening the European gas balance.\n"
        "- Structural Weaknesses: Emphasize weak EUA carbon support for gas-for-coal switching, demand destruction, and an unfavourable TTF–Henry Hub spread diverting cargoes away from Europe.\n"
        "- Negative Indicators: Use evidence from fundamentals (storage, flows, weather/degree-days), spreads, curve roll, and recent bearish news to support your position.\n"
        "- Bull Counterpoints: Critically analyze the bull argument with specific data and sound reasoning, exposing weaknesses or over-optimistic assumptions.\n"
        "- Engagement: Present your argument in a conversational style, directly engaging with the bull analyst's points and debating effectively rather than simply listing facts."
    ),
    trader_inputs_desc=(
        "supply/demand fundamentals (storage, weather, flows, carbon), TTF–Henry Hub spread, and energy positioning"
    ),
)


_NG_F_PROFILE = InstrumentProfile(
    ticker="NG=F",
    display_name="Henry Hub",
    currency_unit="USD/MMBtu",
    region="US",
    benchmark_ticker="TTF=F",
    fundamentals_available=False,
    context_description="a gas contract priced in USD/MMBtu (Henry Hub)",
    market_note=(
        "\n\nThis is Henry Hub natural gas (NG=F), priced in USD/MMBtu. Front-month futures carry strong seasonality (winter heating demand peak, summer injection/storage build) and roll effects — distinguish trend from roll. Compare against Dutch TTF (TTF=F) for the TTF–HH spread (global LNG arbitrage); a widening spread signals strong US LNG export pull draining domestic supply. Note: US storage/flow/weather fundamentals vendors are not yet wired, so lean on price action, the spread, and news flow for supply/demand context."
    ),
    news_note=(
        " This is Henry Hub natural gas: prioritise US storage (EIA weekly), LNG export flows, US weather (heating/cooling demand), production (Appalachia/Haynesville), and geopolitics; use get_macro_indicators with 'fed_funds_rate', 'dollar_index', or '10y_treasury' for the US macro backdrop."
    ),
    # Unused when fundamentals_available=False — the analyst is omitted for NG=F.
    # Kept as a graceful string in case the node is ever invoked directly.
    fundamentals_note=(
        "You are a US natural gas supply/demand analyst covering Henry Hub. Note: US "
        "storage/flow/weather fundamentals vendors are not yet available; report what "
        "can be inferred from price action, the TTF–HH spread, and news flow."
    ),
    sentiment_framing=(
        "You are a US energy market positioning analyst. Produce a sentiment report for {ticker} (Henry Hub natural gas) covering {start_date} to {end_date}. There is no retail cashtag feed for gas, so read positioning from energy news flow: EIA storage surprises, LNG export terminal status, US weather scares, production outages, pipeline maintenance, and regulatory/geopolitical signals."
    ),
    # Spread economics for Henry Hub: a WIDE TTF–HH spread is bullish for NG=F
    # (it drives US LNG export pull, draining domestic supply). This is the
    # mirror image of the TTF bull case, not a name swap.
    researcher_framing_bull=(
        "You are a Bull Analyst advocating for a long Henry Hub natural gas position. Your task is to build a strong, evidence-based case emphasizing a tightening US supply/demand balance, structural support, and positive market indicators. Leverage the provided research and data to address concerns and counter bearish arguments effectively.\n"
        "For Henry Hub gas, read 'growth' as a tightening US balance (storage below the seasonal norm, cold-weather demand, production declines, LNG export strength) and a favourable (wide) TTF–Henry Hub spread; a wide spread signals strong US LNG export pull draining domestic supply. 'Competitive advantage' means export optionality and storage tightness. Anchor the case in the spread, seasonality, and positioning.\n\n"
        "Key points to focus on:\n"
        "- Tightening Balance: Highlight US storage below the seasonal norm, cold-weather heating demand, production drops (freeze-offs, Appalachia curtailment), and strong LNG export pull tightening the US gas balance.\n"
        "- Structural Support: Emphasize export terminal capacity growth, limited storage optionality, and a favourable (wide) TTF–Henry Hub spread pulling US cargoes to Europe/Asia.\n"
        "- Positive Indicators: Use the TTF–HH spread, storage seasonality, weather/degree-days where available, and recent bullish news as evidence.\n"
        "- Bear Counterpoints: Critically analyze the bear argument with specific data and sound reasoning, addressing concerns thoroughly and showing why the bull perspective holds stronger merit.\n"
        "- Engagement: Present your argument in a conversational style, engaging directly with the bear analyst's points and debating effectively rather than just listing data."
    ),
    researcher_framing_bear=(
        "You are a Bear Analyst making the case against a long Henry Hub natural gas position. Your goal is to present a well-reasoned argument emphasizing risks, challenges, and negative indicators. Leverage the provided research and data to highlight potential downsides and counter bullish arguments effectively.\n"
        "For Henry Hub gas, read 'risks' as a loose US balance (storage above the seasonal norm, mild weather, strong production, weak LNG export demand) and an unfavourable (narrow) TTF–Henry Hub spread; a narrow spread means weak export pull, so US supply builds. Flag injection-season seasonality and curve roll. Anchor the case in the spread, seasonality, and positioning.\n\n"
        "Key points to focus on:\n"
        "- Loose Balance: Highlight US storage above the seasonal norm, mild weather suppressing heating demand, and ample supply (strong production, weak LNG sendout) loosening the US gas balance.\n"
        "- Structural Weaknesses: Emphasize production growth, demand destruction, and an unfavourable (narrow) TTF–Henry Hub spread reducing export pull.\n"
        "- Negative Indicators: Use evidence from the TTF–HH spread, storage, curve roll, and recent bearish news to support your position.\n"
        "- Bull Counterpoints: Critically analyze the bull argument with specific data and sound reasoning, exposing weaknesses or over-optimistic assumptions.\n"
        "- Engagement: Present your argument in a conversational style, directly engaging with the bull analyst's points and debating effectively rather than simply listing facts."
    ),
    trader_inputs_desc=(
        "the TTF–Henry Hub spread, energy positioning, and market/technical context (US supply/demand fundamentals unavailable for Henry Hub in this phase)"
    ),
)


_PROFILES: dict[str, InstrumentProfile] = {
    "TTF=F": _TTF_PROFILE,
    "NG=F": _NG_F_PROFILE,
}


def get_profile(ticker: str) -> InstrumentProfile:
    """Return the profile for ``ticker``.

    Normalizes the symbol first (so ``TTF`` / ``EUGAS`` resolve to ``TTF=F``)
    via the data layer's ``normalize_symbol``. Raises ``KeyError`` for unknown
    instruments — callers that must handle arbitrary tickers (notably
    ``build_instrument_context``) catch and fall back to a generic context.
    """
    canonical = normalize_symbol(ticker)
    try:
        return _PROFILES[canonical]
    except KeyError:
        raise KeyError(
            f"No instrument profile for {ticker!r} (canonical {canonical!r})"
        ) from None


def has_profile(ticker: str) -> bool:
    """True when ``ticker`` resolves to a known instrument profile."""
    try:
        get_profile(ticker)
        return True
    except KeyError:
        return False
