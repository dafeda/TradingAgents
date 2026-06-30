import logging
from collections.abc import Mapping
from typing import Any

from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import get_stock_data
from tradingagents.agents.utils.gas_data_tools import (
    get_carbon_price,
    get_gas_storage,
    get_pipeline_flows,
    get_us_gas_storage,
    get_us_weather,
    get_weather,
)
from tradingagents.agents.utils.macro_data_tools import get_macro_indicators
from tradingagents.agents.utils.market_data_validation_tools import get_verified_market_snapshot
from tradingagents.agents.utils.news_data_tools import (
    get_global_news,
    get_news,
)
from tradingagents.agents.utils.prediction_markets_tools import get_prediction_markets
from tradingagents.agents.utils.technical_indicators_tools import get_indicators

# Public surface: the data tools are imported here so agents and the graph
# import them from one place, plus the instrument helpers defined below.
__all__ = [
    "get_stock_data",
    "get_indicators",
    "get_news",
    "get_global_news",
    "get_macro_indicators",
    "get_gas_storage",
    "get_weather",
    "get_pipeline_flows",
    "get_carbon_price",
    "get_us_gas_storage",
    "get_us_weather",
    "get_prediction_markets",
    "get_verified_market_snapshot",
    "build_instrument_context",
    "get_instrument_context_from_state",
    "create_msg_delete",
]

logger = logging.getLogger(__name__)


def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve identity and ticker.

    Looks up the per-instrument profile (Dutch TTF or Henry Hub) and emits
    the identity line from it, so each contract gets the right display name
    and currency unit. Anchoring every agent to this fixed identity prevents
    pattern-matching the price chart to a different instrument.

    Pure string formatting — no network lookup — so it is safe to call at
    graph start and from tests. Raises ``KeyError`` for tickers without a
    profile; callers pass a known gas contract (``TTF=F`` / ``NG=F``), and
    the production path pre-computes this once at run start.
    """
    from tradingagents.instrument_profiles import get_profile

    profile = get_profile(ticker)
    return (
        f"The instrument to analyze is `{ticker}`, {profile.context_description}. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving the `=F` futures suffix where applicable. Treat it as a "
        "commodity future, not a company — company fundamentals (P/E, "
        "balance sheet) do not apply."
    )


def get_instrument_context_from_state(state: Mapping[str, Any]) -> str:
    """Return the instrument context for the current run.

    Prefers the context computed once at run start and stored on the state
    (see ``TradingAgentsGraph._run_graph``). Falls back to building it from
    ``company_of_interest`` via ``build_instrument_context`` — which, like
    the run-start path, is pure-data (no network lookup) — when the state
    was constructed without it (bare programmatic states, tests). The
    fallback raises ``KeyError`` for tickers without a profile (e.g.
    equities) — pass a known gas contract or pre-compute
    ``instrument_context`` at run start.
    """
    context = state.get("instrument_context")
    if isinstance(context, str) and context.strip():
        return context
    return build_instrument_context(str(state["company_of_interest"]))


def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add a context-anchored placeholder.

        The placeholder must not be a bare ``"Continue"``: some
        OpenAI-compatible providers interpret that literally as the user task
        and produce output about the word "continue" instead of analysing the
        instrument. Anchoring it to the resolved instrument context and
        date keeps the next analyst on-task even if the provider treats the
        placeholder as a standalone request.
        """
        messages = state["messages"]
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        instrument_context = get_instrument_context_from_state(state)
        trade_date = state.get("trade_date", "the requested date")
        placeholder = HumanMessage(
            content=(
                f"Proceed with your assigned analysis for this workflow. "
                f"{instrument_context} The analysis date is {trade_date}."
            )
        )
        return {"messages": removal_operations + [placeholder]}

    return delete_messages



