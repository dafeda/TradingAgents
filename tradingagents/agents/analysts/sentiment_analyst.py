"""Sentiment analyst — energy-positioning sentiment for the traded gas contract.

There is no retail cashtag feed for gas, so sentiment is read from the energy
news flow (supply outages, LNG cargoes, storage headlines, weather scares, EUA
carbon, Norway maintenance, geopolitics) rather than social platforms.

The agent does not use tool-calling; the news data is pre-fetched and injected
into the prompt from turn 0. Output uses the structured-output pattern
(json_schema for OpenAI/xAI, response_schema for Gemini, tool-use for Anthropic),
falling back to free-text generation for providers that lack native support, so
the sentiment header (band + score + confidence) is deterministic across runs
and providers instead of free-form per-model prose.
"""

from datetime import datetime, timedelta

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.schemas import SentimentReport, render_sentiment_report
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_news,
)
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext,
)
from tradingagents.instrument_profiles import get_profile


def _seven_days_back(trade_date: str) -> str:
    return (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")


def create_sentiment_analyst(llm):
    """Create a sentiment analyst node for the trading graph.

    Pre-fetches energy news, injects it into the prompt, and produces a
    deterministic sentiment report via structured output (with a free-text
    fallback for providers that do not support it).
    """
    structured_llm = bind_structured(llm, SentimentReport, "Sentiment Analyst")

    def sentiment_analyst_node(state):
        ticker = state["company_of_interest"]
        end_date = state["trade_date"]
        start_date = _seven_days_back(end_date)
        instrument_context = get_instrument_context_from_state(state)

        # Gas has no cashtag — read positioning from energy news flow.
        news_block = get_news.func(ticker, start_date, end_date)
        system_message = _build_gas_message(
            ticker=ticker, start_date=start_date, end_date=end_date,
            news_block=news_block,
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " Today's date is {current_date}; treat it as 'now' for all analysis and tool-call date ranges. {instrument_context}"
                    "\n{system_message}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(current_date=end_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        # Format the template into a concrete message list so the structured
        # and free-text paths receive the same input. No bind_tools — the
        # data is already in the prompt.
        formatted_messages = prompt.format_messages(messages=state["messages"])

        report_text = invoke_structured_or_freetext(
            structured_llm,
            llm,
            formatted_messages,
            render_sentiment_report,
            "Sentiment Analyst",
        )

        return {
            "messages": [AIMessage(content=report_text)],
            "sentiment_report": report_text,
        }

    return sentiment_analyst_node


def _build_gas_message(*, ticker: str, start_date: str, end_date: str, news_block: str) -> str:
    """Energy-positioning message for gas: no cashtag, news-driven only.

    The role/drivers paragraph is per-instrument (European TTF vs US Henry Hub)
    and comes from the profile; the news block and output-fields section are
    constant across instruments.
    """
    try:
        framing = get_profile(ticker).sentiment_framing.format(
            ticker=ticker, start_date=start_date, end_date=end_date
        )
    except KeyError:
        framing = (
            f"Produce a sentiment report for {ticker} covering {start_date} to "
            f"{end_date}. Read positioning from the energy news flow below."
        )
    return f"""{framing}

### Energy news — past 7 days
<start_of_news>
{news_block}
<end_of_news>

How to analyze: weight confirmed events (outages, maintenance, storage figures) over opinion; identify the dominant narrative and any bullish/bearish skew in coverage; flag thin data honestly in `confidence`. Frame conclusions as signal to weigh with fundamentals/technicals, not a price call.

## Output fields
- **overall_band**: Bullish / Mildly Bullish / Neutral / Mixed / Mildly Bearish / Bearish.
- **overall_score**: 0 (bearish) to 10 (bullish); 5 neutral; consistent with band.
- **confidence**: low / medium / high by data quality.
- **narrative**: news-driven positioning, dominant themes, catalysts/risks, plus a markdown summary table."""
