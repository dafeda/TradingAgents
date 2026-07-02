"""Gas analyst wiring: the fundamentals node binds supply/demand tools, and the
researchers/risk debators use TTF framing. A fake LLM captures the bound tools
and prompt strings, so these run without network or keys.
"""
import unittest

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
from tradingagents.agents.analysts.market_analyst import create_market_analyst
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator


class _CapturingLLM:
    """Records tools passed to bind_tools; returns a no-tool-call AIMessage."""
    def __init__(self): self.bound = []
    def bind_tools(self, tools):
        self.bound = [t.name for t in tools]
        return RunnableLambda(lambda _msgs: AIMessage(content="report body"))


class _PromptLLM:
    """Captures the prompt string passed to invoke."""
    def __init__(self): self.prompt = ""
    def invoke(self, prompt):
        self.prompt = prompt
        return AIMessage(content="argument")


def _state():
    return {"trade_date": "2026-06-27", "ticker_of_interest": "TTF=F", "messages": []}


class FundamentalsToolsTests(unittest.TestCase):
    def test_binds_eu_supply_demand_tools_for_ttf(self):
        llm = _CapturingLLM()
        create_fundamentals_analyst(llm)(_state())
        self.assertEqual(
            set(llm.bound),
            {"get_gas_storage", "get_weather", "get_pipeline_flows", "get_carbon_price"},
        )

    def test_binds_us_supply_demand_tools_for_henry_hub(self):
        # NG=F (Henry Hub) is US-region — the analyst must bind the US tool set
        # (EIA storage + CONUS weather), NOT the EU tools.
        llm = _CapturingLLM()
        create_fundamentals_analyst(llm)({**_state(), "ticker_of_interest": "NG=F"})
        self.assertEqual(
            set(llm.bound),
            {"get_us_gas_storage", "get_us_weather"},
        )
        # EU tools must not be bound for a US instrument.
        self.assertFalse(set(llm.bound) & {"get_gas_storage", "get_weather",
                                           "get_pipeline_flows", "get_carbon_price"})


class MarketGasNoteTests(unittest.TestCase):
    def test_market_runs_and_keeps_indicator_tools(self):
        llm = _CapturingLLM()
        out = create_market_analyst(llm)(_state())
        self.assertEqual(out["market_report"], "report body")
        self.assertIn("get_stock_data", llm.bound)


class ResearcherRiskFramingTests(unittest.TestCase):
    def _debate_state(self, ticker_of_interest="TTF=F", fundamentals_report="f"):
        return {
            "trade_date": "2026-06-27", "ticker_of_interest": ticker_of_interest,
            "market_report": "m", "sentiment_report": "s", "news_report": "n",
            "fundamentals_report": fundamentals_report,
            "investment_debate_state": {"history": "", "bull_history": "", "bear_history": "",
                                        "current_response": "", "count": 0},
            "risk_debate_state": {"history": "", "aggressive_history": "", "conservative_history": "",
                                  "neutral_history": "", "current_conservative_response": "",
                                  "current_neutral_response": "", "count": 0},
            "trader_investment_plan": "tp",
        }

    def test_bull_uses_ttf_framing(self):
        llm = _PromptLLM()
        create_bull_researcher(llm)(self._debate_state())
        self.assertIn("TTF gas position", llm.prompt)
        self.assertIn("Gas supply/demand report", llm.prompt)
        self.assertIn("Henry Hub spread", llm.prompt)

    def test_bull_uses_henry_hub_framing(self):
        # NG=F bull framing must reference Henry Hub, not TTF, and keep the
        # spread logic correct (wide TTF–HH = bullish for HH via export pull).
        state = self._debate_state(ticker_of_interest="NG=F")
        llm = _PromptLLM()
        create_bull_researcher(llm)(state)
        self.assertIn("Henry Hub", llm.prompt)
        self.assertIn("TTF–Henry Hub spread", llm.prompt)
        # Must not use the TTF-specific bull framing.
        self.assertNotIn("long TTF gas position", llm.prompt)

    def test_fundamentals_line_omitted_when_empty(self):
        # When no fundamentals analyst ran (e.g. Henry Hub in this phase), the
        # report is empty and the line must be omitted, not shown as a dangling
        # empty label.
        state = self._debate_state(
            ticker_of_interest="NG=F", fundamentals_report=""
        )
        llm = _PromptLLM()
        create_bull_researcher(llm)(state)
        self.assertNotIn("Gas supply/demand report", llm.prompt)

    def test_risk_relabels_fundamentals(self):
        llm = _PromptLLM()
        create_aggressive_debator(llm)(self._debate_state())
        self.assertIn("Gas Supply/Demand Report", llm.prompt)


if __name__ == "__main__":
    unittest.main()
