from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_stock_data(
    symbol: Annotated[str, "gas contract symbol, e.g. TTF=F or NG=F"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve OHLCV price data for a given gas contract symbol.
    Uses the configured core_stock_apis vendor.
    Args:
        symbol (str): Gas contract symbol, e.g. TTF=F (Dutch TTF) or NG=F (Henry Hub)
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted dataframe containing the price data for the specified contract in the specified date range.
    """
    return route_to_vendor("get_stock_data", symbol, start_date, end_date)
