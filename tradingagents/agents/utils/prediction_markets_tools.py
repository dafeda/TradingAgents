from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_prediction_markets(
    topic: Annotated[
        str,
        "Event topic/keyword, e.g. 'EU gas price cap', 'Russia pipeline "
        "sanctions', 'cold winter Europe', or 'recession 2026'.",
    ],
    limit: Annotated[int | None, "Max markets to return; omit for a default of 6"] = None,
) -> str:
    """
    Retrieve live, market-implied probabilities for forward-looking events from
    prediction markets (Polymarket): EU energy policy, sanctions, geopolitics,
    recession/demand, and cold-winter risk. Returns the most-traded open markets
    matching the topic, each with its implied probability, traded volume,
    resolution date, and recent move. Uses the configured prediction_markets vendor.

    Args:
        topic (str): Event keyword(s) to search
        limit (int): Max markets to return; omit for a default of 6

    Returns:
        str: A formatted markdown report of matching prediction markets
    """
    return route_to_vendor("get_prediction_markets", topic, limit)
