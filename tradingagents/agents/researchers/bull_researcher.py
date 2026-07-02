from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
)
from tradingagents.instrument_profiles import get_profile


def create_bull_researcher(llm):
    def bull_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        instrument_context = get_instrument_context_from_state(state)
        ticker = state["ticker_of_interest"]

        framing = get_profile(ticker).researcher_framing_bull

        # Only surface the fundamentals report when it has content; omit the
        # line rather than showing a dangling empty label.
        fundamentals_line = (
            f"Gas supply/demand report: {fundamentals_report}"
            if fundamentals_report.strip()
            else ""
        )

        prompt = f"""{framing}

Resources available:
{instrument_context}
Market research report: {market_research_report}
Sentiment report (energy-news positioning): {sentiment_report}
Latest world affairs news: {news_report}
{fundamentals_line}
Conversation history of the debate: {history}
Last bear argument: {current_response}
Use this information to deliver a compelling bull argument, refute the bear's concerns, and engage in a dynamic debate that demonstrates the strengths of the bull position.
"""

        response = llm.invoke(prompt)

        argument = f"Bull Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": bull_history + "\n" + argument,
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
