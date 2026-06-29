"""EUA carbon vendor — European emission allowance price via yfinance.

Coal-to-gas switching ties carbon to TTF: when EUA carbon is dear, gas-fired
power is favoured over coal, lifting gas demand. There is no free ICE EUA
front-month on Yahoo, so this uses exchange-traded EUA proxies (physical-EUA
ETC primary, global-carbon ETF fallback) priced through the existing yfinance
data path, keeping the gas analyst's switching signal keyless.
"""
import logging

from .errors import NoMarketDataError
from .y_finance import get_YFin_data_online

logger = logging.getLogger(__name__)

# Yahoo EUA proxies, tried in order: SparkChange Physical Carbon EUA ETC tracks
# allowances 1:1; KraneShares global-carbon ETF is the broader fallback.
EUA_PROXIES = ("CARB.L", "KRBN")

DEFAULT_LOOKBACK_DAYS = 30


def get_eua_carbon(curr_date: str, look_back_days: int | None = None) -> str:
    """Fetch EUA carbon allowance prices for coal-gas switching context.

    Args:
        curr_date: End of the window (yyyy-mm-dd); no later data is returned.
        look_back_days: Trailing window; ``None`` uses DEFAULT_LOOKBACK_DAYS.

    Returns:
        OHLCV markdown for the first available EUA proxy, prefixed with the
        proxy used so the analyst knows this tracks allowances, not TTF.
    """
    from datetime import datetime, timedelta

    if look_back_days is None:
        look_back_days = DEFAULT_LOOKBACK_DAYS
    start = (datetime.strptime(curr_date, "%Y-%m-%d")
             - timedelta(days=look_back_days)).strftime("%Y-%m-%d")

    last_err: Exception | None = None
    for symbol in EUA_PROXIES:
        try:
            data = get_YFin_data_online(symbol, start, curr_date)
            return f"## EUA carbon (proxy {symbol}, coal-gas switching)\n" + data
        except NoMarketDataError as e:
            last_err = e
            continue
    raise NoMarketDataError(
        "EUA", "EUA", detail=f"no EUA proxy returned data ({last_err})"
    )
