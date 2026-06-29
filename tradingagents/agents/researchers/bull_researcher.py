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
        ticker = state["company_of_interest"]

        try:
            framing = get_profile(ticker).researcher_framing_bull
        except KeyError:
            framing = (
                "You are a Bull Analyst advocating for a long position. Build a "
                "strong, evidence-based case emphasizing growth, structural "
                "support, and positive market indicators."
            )

        # Only surface the fundamentals report when it has content; for
        # instruments without a fundamentals analyst (e.g. Henry Hub in this
        # phase) the field is empty and the line is omitted rather than shown
        # as a dangling empty label.
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
