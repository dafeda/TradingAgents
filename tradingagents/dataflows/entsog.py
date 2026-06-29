"""ENTSOG pipeline-flow vendor — Norway pipe + LNG sendout into Europe (keyless).

Supply side of the TTF balance: Norwegian pipeline entries and LNG terminal
sendout are the swing imports, so a Norway maintenance outage or an LNG drop
tightens TTF. ENTSOG's transparency API publishes daily physical flows per
point; this aggregates them into total EU entry plus the largest entry points,
keyword-flagging Norway/LNG so the gas analyst reads the supply picture without
parsing thousands of point rows. No key required.
"""
import logging
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

ENTSOG_BASE = "https://transparency.entsog.eu/api/v1/operationaldata"
REQUEST_TIMEOUT = 40

# kWh/d -> GWh/d for readable totals.
KWH_TO_GWH = 1_000_000
DEFAULT_LOOKBACK_DAYS = 2
TOP_POINTS = 10


def _gwh(kwh: float) -> float:
    return kwh / KWH_TO_GWH


def get_pipeline_flows(curr_date: str, look_back_days: int | None = None) -> str:
    """Fetch EU physical entry flows, highlighting Norway pipe + LNG sendout.

    Args:
        curr_date: End of the window (yyyy-mm-dd).
        look_back_days: Trailing window; ``None`` uses DEFAULT_LOOKBACK_DAYS.
    """
    look_back_days = look_back_days or DEFAULT_LOOKBACK_DAYS
    start = (datetime.strptime(curr_date, "%Y-%m-%d")
             - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
    resp = requests.get(
        ENTSOG_BASE,
        params={
            "indicator": "Physical Flow", "periodType": "day",
            "from": start, "to": curr_date, "directionKey": "entry",
            "limit": 8000,
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    flows = resp.json().get("operationaldata", [])

    totals: dict[str, float] = {}
    for r in flows:
        try:
            v = float(r.get("value"))
        except (TypeError, ValueError):
            continue
        totals[r.get("pointLabel", "?")] = totals.get(r.get("pointLabel", "?"), 0.0) + v

    if not totals:
        return "## ENTSOG pipeline flows\nNo physical-flow data in window."

    grand = _gwh(sum(totals.values()))
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:TOP_POINTS]
    header = (
        f"## ENTSOG EU entry flows ({start} to {curr_date})\n"
        f"- Total physical entry: ~{grand:,.0f} GWh/d (sum over window); "
        f"Norway/LNG points flagged\n\n"
        "| Entry point | GWh/d | type |\n| --- | --- | --- |\n"
    )

    def _tag(name: str) -> str:
        n = name.lower()
        if "lng" in n or "gate" in n or "terminal" in n:
            return "LNG"
        if any(k in n for k in ("norw", "vesterled", "emden", "dornum", "easington")):
            return "Norway"
        return ""

    rows = "\n".join(
        f"| {p} | {_gwh(v):,.0f} | {_tag(p)} |" for p, v in top
    )
    return header + rows + "\n"
