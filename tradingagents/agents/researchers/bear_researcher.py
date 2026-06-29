from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
)
from tradingagents.instrument_profiles import get_profile


def create_bear_researcher(llm):
    def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        instrument_context = get_instrument_context_from_state(state)
        ticker = state["company_of_interest"]

        try:
            framing = get_profile(ticker).researcher_framing_bear
        except KeyError:
            framing = (
                "You are a Bear Analyst making the case against a long position. "
                "Present a well-reasoned argument emphasizing risks, challenges, "
                "and negative indicators."
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
Last bull argument: {current_response}
Use this information to deliver a compelling bear argument, refute the bull's claims, and engage in a dynamic debate that demonstrates the risks and weaknesses of a long position.
"""

        response = llm.invoke(prompt)

        argument = f"Bear Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bear_history": bear_history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node
