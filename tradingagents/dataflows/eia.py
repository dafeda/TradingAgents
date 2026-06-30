"""EIA weekly natural-gas storage vendor — Henry Hub (US) fundamentals.

Storage inventory is the single most important Henry Hub fundamental: the
Thursday 10:30am EIA Weekly Natural Gas Storage Report (Lower 48 working gas
in underground storage, in Bcf) sets the US supply cushion the whole curve
trades around — the direct US analog of GIE AGSI+ for TTF. This vendor fetches
the weekly series for the Lower 48 total plus the five EIA regions (East,
Midwest, South Central, Mountain, Pacific), the wk/wk change, and a 5-year
same-week average computed client-side from history so the analyst reads the
balance versus the seasonal norm rather than a raw Bcf number.

EIA API v2 (https://www.eia.gov/opendata/) — free key read from
``EIA_API_KEY`` and sent as the ``api_key`` query param. If it is unset the
vendor raises ``EiaNotConfiguredError`` so the routing layer treats storage as
"unavailable" rather than hard-crashing the run — matching the GIE/FRED
vendors' optional-enrichment behaviour.
"""
import logging
import os
from datetime import datetime, timedelta

import requests

from .errors import VendorNotConfiguredError

logger = logging.getLogger(__name__)

EIA_API_BASE = "https://api.eia.gov/v2/natural-gas/stor/wkly/data"

# Network timeout (seconds) so a stalled request can't hang the agents.
REQUEST_TIMEOUT = 30

# Default trailing window (~6 months) — the weekly storage report publishes
# Thursday, so this captures the current injection/withdrawal trajectory and
# the level a few months back, enough to read the balance.
DEFAULT_LOOKBACK_DAYS = 180

# Rows cap for the rendered table; weekly storage over a long window would
# otherwise flood the prompt. Latest values matter most for a decision.
MAX_ROWS = 16

# 5-year average window: same calendar week, prior 5 years. Used to compute
# the "vs seasonal norm" read that the gas desk trades around.
FIVE_YEAR_SPAN = 5

# EIA duoarea codes for the weekly storage route. R48 is the Lower 48 total;
# R31-R35 are the five Census-division storage regions. South Central (R33)
# is the LNG/export hub and splits into salt (SSO) / nonsalt (SNO) caverns,
# which have different injection/withdrawal physics — useful context but the
# regional SWO total is the primary read.
REGIONS = {
    "R48": "Lower 48",
    "R31": "East",
    "R32": "Midwest",
    "R33": "South Central",
    "R34": "Mountain",
    "R35": "Pacific",
}


class EiaNotConfiguredError(VendorNotConfiguredError):
    """Raised when EIA storage is selected but no API key is configured.

    A VendorNotConfiguredError (and thus a ValueError), so the routing layer's
    "vendor unavailable" handling treats missing storage as optional rather
    than crashing the run.
    """


def get_api_key() -> str:
    """Retrieve the EIA API v2 key from the environment."""
    api_key = os.getenv("EIA_API_KEY")
    if not api_key:
        raise EiaNotConfiguredError(
            "EIA_API_KEY environment variable is not set. Register for a free "
            "key at https://www.eia.gov/opendata/register.php."
        )
    return api_key


def _request(params: dict) -> dict:
    """GET the EIA v2 data endpoint, surfacing error bodies.

    EIA v2 returns the data rows under ``response.data`` (a list) when the
    route ends in ``/data``; a metadata-shaped response (``response.data`` as
    a dict with an empty ``value`` list) means the ``/data`` node was missing
    or no rows matched — handled by the caller.
    """
    response = requests.get(
        EIA_API_BASE,
        params={"api_key": get_api_key(), **params},
        timeout=REQUEST_TIMEOUT,
    )
    # EIA v2 returns 400/401/403 with a JSON {"error": ...} body for a bad
    # key or malformed params; treat auth failures as "not configured" so the
    # routing layer degrades instead of crashing.
    if response.status_code in (400, 401, 403):
        try:
            message = response.json().get("error", response.text)
        except ValueError:
            message = response.text
        raise EiaNotConfiguredError(
            f"EIA request rejected ({response.status_code}); check EIA_API_KEY. "
            f"{str(message)[:200]}"
        )
    response.raise_for_status()
    return response.json()


def _num(value) -> float | None:
    """EIA v2 returns values as strings (per the Jan 2024 standardization)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _weekly_rows(end_date: str, look_back_days: int, regions: list[str]) -> list[dict]:
    """Fetch weekly storage rows for ``regions`` over the trailing window.

    Returns the raw EIA row dicts (newest-first per the sort param). The
    caller pivots them into per-region series.
    """
    start = (datetime.strptime(end_date, "%Y-%m-%d")
             - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
    params = {
        "frequency": "weekly",
        "data[0]": "value",
        "start": start,
        "end": end_date,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 5000,
    }
    for i, r in enumerate(regions):
        params[f"facets[duoarea][{i}]"] = r
    payload = _request(params)
    rows = payload.get("response", {}).get("data", [])
    # Metadata-shaped response (no /data or no match) returns a dict here;
    # normalise to an empty list so downstream code sees a consistent type.
    if isinstance(rows, dict):
        return []
    return rows


def _five_year_avg(end_date: str, region: str) -> float | None:
    """Compute the 5-year same-week average storage for ``region``.

    Pulls the weekly observations whose period falls in the same ISO week
    number across the prior ``FIVE_YEAR_SPAN`` years and averages them, so the
    analyst sees the seasonal norm the desk trades around. Returns ``None``
    when history is unavailable (the route only goes back to 2010, so recent
    years always have coverage; older years may not).
    """
    target = datetime.strptime(end_date, "%Y-%m-%d")
    # Gather one observation per prior year closest to the target week. A
    # ~10-day window around the same calendar date catches the Thursday
    # report nearest the target day each year.
    samples: list[float] = []
    for years_ago in range(1, FIVE_YEAR_SPAN + 1):
        yr = target - timedelta(days=365 * years_ago)
        start = (yr - timedelta(days=7)).strftime("%Y-%m-%d")
        end = (yr + timedelta(days=7)).strftime("%Y-%m-%d")
        params = {
            "frequency": "weekly",
            "data[0]": "value",
            "facets[duoarea][0]": region,
            "start": start,
            "end": end,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "length": 5,
        }
        try:
            payload = _request(params)
        except Exception as e:
            logger.debug("EIA 5-yr avg window %s for %s failed: %s", end, region, e)
            continue
        yr_rows = payload.get("response", {}).get("data", [])
        if isinstance(yr_rows, dict):
            continue
        # Pick the row whose period is closest to the target date that year.
        best = None
        best_delta = None
        for r in yr_rows:
            if r.get("duoarea") != region:
                continue
            v = _num(r.get("value"))
            if v is None:
                continue
            try:
                rp = datetime.strptime(r["period"], "%Y-%m-%d")
            except (KeyError, ValueError):
                continue
            delta = abs((rp - yr).days)
            if best_delta is None or delta < best_delta:
                best, best_delta = v, delta
        if best is not None:
            samples.append(best)
    if not samples:
        return None
    return sum(samples) / len(samples)


def get_us_gas_storage(
    curr_date: str,
    look_back_days: int | None = None,
) -> str:
    """Fetch US weekly gas-storage inventory as a formatted markdown report.

    Args:
        curr_date: End of the window (yyyy-mm-dd); no later observations are
            returned, so a past date never leaks future data. The EIA weekly
            report publishes Thursdays, so the latest row on or before this
            date is the desk's storage read.
        look_back_days: Trailing window length; ``None`` uses
            ``DEFAULT_LOOKBACK_DAYS``.

    Returns:
        A markdown report: latest Lower 48 working gas (Bcf), wk/wk change,
        5-year same-week average and the vs-norm gap, a regional breakdown
        table, and a recent weekly history table.
    """
    if look_back_days is None:
        look_back_days = DEFAULT_LOOKBACK_DAYS

    rows = _weekly_rows(curr_date, look_back_days, list(REGIONS))
    if not rows:
        return (
            "## EIA weekly gas storage: Lower 48\n"
            f"- Window: trailing {look_back_days} days to {curr_date}\n"
            "- Units: working gas in underground storage, Bcf\n\n"
            "No storage observations in this window. The EIA weekly report "
            "publishes Thursdays; widen look_back_days or check EIA_API_KEY."
        )

    # Pivot rows into {region: [(period, value), ...]} ascending by period.
    # Only the SWO process (Underground Storage - Working Gas) is the regional
    # total; R33 also returns SNO (nonsalt) and SSO (salt) sub-components which
    # would double-count if pivoted in, so filter to SWO for the balance read.
    by_region: dict[str, list[tuple[str, float]]] = {}
    for r in rows:
        if r.get("process") != "SWO":
            continue
        region = r.get("duoarea")
        v = _num(r.get("value"))
        if region is None or v is None:
            continue
        by_region.setdefault(region, []).append((r.get("period", ""), v))
    for region in by_region:
        by_region[region].sort(key=lambda p: p[0])

    r48 = by_region.get("R48", [])
    if not r48:
        return (
            "## EIA weekly gas storage: Lower 48\n"
            f"- Window: trailing {look_back_days} days to {curr_date}\n"
            "- Units: working gas in underground storage, Bcf\n\n"
            "No Lower 48 (R48) storage observations in this window."
        )

    latest_period, latest_val = r48[-1]
    prev_val = r48[-2][1] if len(r48) >= 2 else None
    wk_change = (latest_val - prev_val) if prev_val is not None else None

    five_yr = _five_year_avg(latest_period, "R48")
    vs_norm = (latest_val - five_yr) if five_yr is not None else None

    header = (
        "## EIA weekly gas storage: Lower 48\n"
        f"- Window: trailing {look_back_days} days to {curr_date}\n"
        "- Units: working gas in underground storage, Bcf\n"
        "- Source: EIA Weekly Natural Gas Storage Report (api.eia.gov v2)\n"
    )

    summary_parts = [f"\n**Latest:** {latest_val:,.0f} Bcf ({latest_period})"]
    if wk_change is not None:
        summary_parts.append(f"**Wk/wk:** {wk_change:+,.0f} Bcf")
    if five_yr is not None and vs_norm is not None:
        pct = (vs_norm / five_yr * 100) if five_yr else 0.0
        summary_parts.append(
            f"**5-yr avg (same wk):** {five_yr:,.0f} Bcf | "
            f"**vs norm:** {vs_norm:+,.0f} Bcf ({pct:+.1f}%)"
        )
    summary = "\n- " + "\n- ".join(summary_parts) + "\n"

    # Regional breakdown at the latest period.
    regional_lines = []
    for code, name in REGIONS.items():
        if code == "R48":
            continue
        series = by_region.get(code, [])
        if not series:
            continue
        regional_lines.append(f"| {name} | {series[-1][1]:,.0f} |")
    regional = ""
    if regional_lines:
        regional = (
            "\n### Regional breakdown (latest week)\n\n"
            "| Region | Working gas (Bcf) |\n| --- | --- |\n"
            + "\n".join(regional_lines) + "\n"
        )

    # Recent weekly history (Lower 48), newest-first.
    shown = list(reversed(r48[-MAX_ROWS:]))
    note = (
        f"\n_(showing the most recent {len(shown)} of {len(r48)} weeks)_\n"
        if len(r48) > MAX_ROWS else "\n"
    )
    table = (
        "\n### Lower 48 weekly history\n\n"
        "| Week ending | Working gas (Bcf) |\n| --- | --- |\n"
        + "\n".join(f"| {p} | {v:,.0f} |" for p, v in shown)
        + "\n"
    )

    return header + summary + regional + note + table
