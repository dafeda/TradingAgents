from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_carbon_price,
    get_gas_storage,
    get_instrument_context_from_state,
    get_pipeline_flows,
    get_us_gas_storage,
    get_us_weather,
    get_weather,
)
from tradingagents.instrument_profiles import get_profile

# Region-specific tool sets. The fundamentals analyst binds only the region's
# tools to the LLM so it sees accurate, region-specific docstrings (e.g. the
# EIA tool has no "area" param like AGSI+). The ToolNode holds the union so
# either region's calls can execute (see trading_graph._create_tool_nodes).
_EU_TOOLS = [get_gas_storage, get_weather, get_pipeline_flows, get_carbon_price]
_US_TOOLS = [get_us_gas_storage, get_us_weather]


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["ticker_of_interest"]
        instrument_context = get_instrument_context_from_state(state)

        try:
            profile = get_profile(ticker)
            system_message = profile.fundamentals_note
            tools = _US_TOOLS if profile.region == "US" else _EU_TOOLS
        except KeyError:
            system_message = (
                "You are a supply/demand analyst. Write a comprehensive fundamentals "
                "report on the balance and price drivers to inform traders."
            )
            tools = _EU_TOOLS

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}."
                    " Today's date is {current_date}; treat it as 'now' for all analysis and tool-call date ranges. {instrument_context}\n"
                    "{system_message}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
