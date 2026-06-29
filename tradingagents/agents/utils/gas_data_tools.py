"""Gas supply/demand tools — European TTF fundamentals for the gas analyst.

Thin LangChain wrappers over the gas vendors (AGSI+ storage, Open-Meteo
degree-days, ENTSOG flows, EUA carbon), routed through the configured vendors
so the fundamentals analyst reads the TTF supply/demand balance (storage,
weather, flows, carbon) as the instrument's core fundamentals.
"""
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_gas_storage(
    area: Annotated[str, "Storage area: 'EU'/'TTF'/'NL' (Dutch hub) or an ISO code like 'DE'"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format; the end of the window"],
    look_back_days: Annotated[int | None, "Trailing window in days; omit for ~60d"] = None,
) -> str:
    """European gas-storage inventory from GIE AGSI+: fill %, gas in storage,
    and net withdrawal/injection over the window. Storage vs the seasonal norm
    is the primary TTF fundamental. Returns a markdown report; configured
    gas_storage vendor."""
    return route_to_vendor("get_gas_storage", area, curr_date, look_back_days)


@tool
def get_weather(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format ('now' for the run)"],
    look_back_days: Annotated[int | None, "Realised window in days; omit for 14d"] = None,
) -> str:
    """NW-Europe heating/cooling degree days (Open-Meteo): realised window plus a
    7-day forecast tail. High HDD = strong gas heating demand. The dominant
    short-term TTF demand driver. Configured weather_data vendor."""
    return route_to_vendor("get_weather", curr_date, look_back_days)


@tool
def get_pipeline_flows(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format; the end of the window"],
    look_back_days: Annotated[int | None, "Trailing window in days; omit for ~2d"] = None,
) -> str:
    """European gas entry flows from ENTSOG: total entry plus the largest points,
    with Norway pipe and LNG sendout flagged. Swing supply behind TTF — a Norway
    outage or LNG drop tightens the balance. Configured pipeline_flows vendor."""
    return route_to_vendor("get_pipeline_flows", curr_date, look_back_days)


@tool
def get_carbon_price(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format; the end of the window"],
    look_back_days: Annotated[int | None, "Trailing window in days; omit for 30d"] = None,
) -> str:
    """EUA carbon allowance price (yfinance proxy). Dear carbon favours gas-fired
    over coal power (coal-gas switching), lifting gas demand. Returns OHLCV
    markdown; configured carbon_data vendor."""
    return route_to_vendor("get_carbon_price", curr_date, look_back_days)
