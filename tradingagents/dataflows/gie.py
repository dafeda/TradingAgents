"""GIE AGSI+ European gas-storage vendor.

Storage inventory is the single most important TTF fundamental: the EU's fill
level versus the seasonal norm sets the supply cushion the whole curve trades
around. This vendor fetches the AGSI+ daily series — fill %, gas in storage,
and net withdrawal/injection — for the EU aggregate or a single country, so the
gas supply/demand analyst can read the balance directly rather than from
headlines.

Free key (https://agsi.gie.eu/) is read from ``GIE_API_KEY`` and sent as the
``x-key`` header. If it is unset the vendor raises ``GieNotConfiguredError`` so
the routing layer treats storage as "unavailable" rather than hard-crashing the
run — matching the FRED vendor's optional-enrichment behaviour.
"""
import logging
import os
from datetime import datetime, timedelta

import requests

from .errors import VendorNotConfiguredError

logger = logging.getLogger(__name__)

AGSI_API_BASE = "https://agsi.gie.eu/api"

# Network timeout (seconds) so a stalled request can't hang the agents.
REQUEST_TIMEOUT = 30

# Default trailing window: ~60 days shows the current injection/withdrawal
# trajectory and the level a few months back, enough to read the balance.
DEFAULT_LOOKBACK_DAYS = 60

# Recent rows cap for the rendered table; daily storage over a long window
# would otherwise flood the prompt. Latest values matter most for a decision.
MAX_ROWS = 30

# Friendly area aliases -> AGSI+ country codes. AGSI+ only serves daily history
# per country (the "eu" aggregate exposes a live snapshot, not a queryable
# window), so EU/default resolve to NL — the Dutch hub behind TTF and the
# relevant supply gauge for this desk. Bare ISO codes pass through for DE/FR/etc.
STORAGE_AREAS = {
    "EU": "NL", "EUROPE": "NL",
    "TTF": "NL", "DUTCH": "NL", "NL": "NL", "NETHERLANDS": "NL",
    "DE": "DE", "GERMANY": "DE",
    "FR": "FR", "FRANCE": "FR",
    "IT": "IT", "ITALY": "IT",
}


class GieNotConfiguredError(VendorNotConfiguredError):
    """Raised when GIE storage is selected but no API key is configured.

    A VendorNotConfiguredError (and thus a ValueError), so the routing layer's
    "vendor unavailable" handling treats missing storage as optional rather
    than crashing the run.
    """


def get_api_key() -> str:
    """Retrieve the GIE AGSI+ API key from the environment."""
    api_key = os.getenv("GIE_API_KEY")
    if not api_key:
        raise GieNotConfiguredError(
            "GIE_API_KEY environment variable is not set. Register for a free "
            "key at https://agsi.gie.eu/ (account -> API key)."
        )
    return api_key


def _resolve_area(area: str) -> str:
    """Map a friendly area name to an AGSI+ country code, or pass one through."""
    key = (area or "NL").strip().upper()
    if key in STORAGE_AREAS:
        return STORAGE_AREAS[key]
    # Bare 2-letter ISO code -> pass through; anything else defaults to NL.
    return key if len(key) == 2 else "NL"


def _request(params: dict) -> dict:
    """GET the AGSI+ endpoint with the API key header, surfacing error bodies."""
    response = requests.get(
        AGSI_API_BASE,
        params=params,
        headers={"x-key": get_api_key()},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code in (400, 401, 403):
        raise GieNotConfiguredError(
            f"AGSI+ request rejected ({response.status_code}); check GIE_API_KEY. "
            f"{response.text[:200]}"
        )
    response.raise_for_status()
    payload = response.json()
    # AGSI+ returns 200 with an {"error": ...} body for a bad/missing key rather
    # than a 4xx, so an invalid key would otherwise read as empty data. Treat it
    # as unavailable so the routing layer degrades instead of fabricating "0%".
    if isinstance(payload, dict) and payload.get("error"):
        raise GieNotConfiguredError(
            f"AGSI+ rejected the request: {payload.get('message', payload['error'])}. "
            "Verify GIE_API_KEY is a real registered key (the docs sample key is "
            "not valid)."
        )
    return payload


def _num(value) -> float | None:
    """AGSI+ encodes a missing value as '-'; return a float or None."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def get_gas_storage(
    area: str,
    curr_date: str,
    look_back_days: int | None = None,
) -> str:
    """Fetch EU/country gas-storage inventory as a formatted markdown report.

    Args:
        area: "EU" aggregate, "TTF"/"NL", or an ISO country code (e.g. "DE").
        curr_date: End of the window (yyyy-mm-dd); no later observations are
            returned, so a past date never leaks future data.
        look_back_days: Trailing window length; ``None`` uses DEFAULT_LOOKBACK_DAYS.

    Returns:
        A markdown report: latest fill %, gas in storage, net withdrawal, the
        change over the window, and a recent daily table.
    """
    if look_back_days is None:
        look_back_days = DEFAULT_LOOKBACK_DAYS

    country = _resolve_area(area)
    end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_date = (end_dt - timedelta(days=look_back_days)).strftime("%Y-%m-%d")

    params = {"country": country, "from": start_date, "to": curr_date, "size": 300}
    label = country

    payload = _request(params)
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    # AGSI+ returns newest-first; sort ascending for a readable trend table.
    points = sorted(
        (
            (r.get("gasDayStart"), _num(r.get("full")), _num(r.get("gasInStorage")),
             _num(r.get("netWithdrawal")))
            for r in rows
        ),
        key=lambda p: p[0] or "",
    )
    points = [p for p in points if p[0]]

    header = (
        f"## GIE AGSI+ gas storage: {label}\n"
        f"- Window: {start_date} to {curr_date}\n"
        f"- Units: full = % of working capacity, stock = TWh, "
        f"net withdrawal = GWh/day\n"
    )

    if not points:
        return header + (
            "\nNo storage observations in this window. Widen look_back_days, or "
            "the area code may be unreported by AGSI+."
        )

    first = points[0]
    last = points[-1]
    fill_delta = (
        f"{last[1] - first[1]:+.2f}pp from {first[1]:.1f}% ({first[0]})"
        if last[1] is not None and first[1] is not None
        else "n/a"
    )
    summary = (
        f"\n**Latest:** {last[1]:.1f}% full, {last[2]:.1f} TWh ({last[0]}) | "
        f"**Change over window:** {fill_delta}\n"
    ) if last[1] is not None and last[2] is not None else f"\n**Latest:** {last[0]}\n"

    shown = points[-MAX_ROWS:]
    note = (
        f"\n_(showing the most recent {MAX_ROWS} of {len(points)} days)_\n"
        if len(points) > MAX_ROWS else ""
    )
    table = (
        "\n| Date | Full % | Stock (TWh) | Net withdrawal (GWh) |\n"
        "| --- | --- | --- | --- |\n"
        + "\n".join(
            f"| {d} | {f'{full:.1f}' if full is not None else '-'} | "
            f"{f'{stock:.1f}' if stock is not None else '-'} | "
            f"{f'{nw:+.0f}' if nw is not None else '-'} |"
            for d, full, stock, nw in shown
        )
        + "\n"
    )

    return header + summary + note + table
