"""Symbol normalization and market-data error types for vendor calls.

The desk trades European gas via Yahoo Finance, which uses specific ticker
conventions that differ from the broker / TradingView style symbols users
often type:

    user types        Yahoo wants       why
    ---------------   ---------------   -----------------------------------
    TTF, EUGAS        TTF=F             Dutch TTF front-month future (EUR/MWh)
    NATGAS            NG=F              Henry Hub future (TTF–HH spread ref)

Passing the raw broker symbol to Yahoo returns an empty result, which the
agents previously received as free text and could hallucinate a price
around (see issue #781). Centralizing the mapping here means every yfinance
entry point resolves symbols the same way, and new instruments are added by
appending a table row rather than editing call sites.
"""

from __future__ import annotations

import logging
import re

# NoMarketDataError lives in the vendor-error taxonomy (errors.py); re-exported
# here for the many call sites that import it alongside normalize_symbol.
from .errors import NoMarketDataError as NoMarketDataError

logger = logging.getLogger(__name__)


# Explicit aliases for instruments whose broker symbol does not map to a Yahoo
# symbol by rule. The gas desk trades Dutch TTF and references Henry Hub for the
# TTF–HH spread. Extend by adding rows — no call site changes required.
_ALIASES = {
    # European gas — Dutch TTF front-month future (priced in EUR/MWh)
    "TTF": "TTF=F", "DUTCHTTF": "TTF=F", "EUGAS": "TTF=F",
    # Henry Hub — reference leg for the TTF–Henry Hub (LNG arbitrage) spread
    "NATGAS": "NG=F", "XNGUSD": "NG=F",
}

# Yahoo symbols may contain letters, digits, and these structural characters.
_YAHOO_SAFE = re.compile(r"^[A-Za-z0-9._\-\^=]+$")


def normalize_symbol(raw: str) -> str:
    """Map a user/broker symbol to its canonical Yahoo Finance symbol.

    Resolution order (first match wins):
      1. Explicit alias table (TTF / Henry Hub).
      2. Otherwise the upper-cased symbol is returned unchanged (Yahoo-native
         symbols like ``TTF=F``, ``NG=F``, ``CARB.L`` or ``^GSPC``).

    A trailing ``+`` (broker CFD marker) is stripped before matching. The
    function is purely syntactic — it performs no network calls — so it is safe
    to apply on every request.
    """
    if not isinstance(raw, str) or not raw.strip():
        return raw

    s = raw.strip().upper()
    # Broker CFD/qualifier suffixes Yahoo never uses.
    s = s.rstrip("+")

    canonical = _ALIASES.get(s, s)

    if canonical != raw.strip().upper():
        logger.info("Resolved symbol %r to Yahoo symbol %r", raw, canonical)
    return canonical


def is_yahoo_safe(symbol: str) -> bool:
    """True when ``symbol`` only contains characters Yahoo symbols use."""
    return bool(symbol) and _YAHOO_SAFE.fullmatch(symbol) is not None
