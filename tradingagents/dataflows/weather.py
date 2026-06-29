"""Weather degree-days vendor — NW Europe heating/cooling demand via Open-Meteo.

Heating degree days (HDD) are the dominant short-term TTF demand driver: a cold
NW-European spell pulls gas out of storage and bids the front of the curve. This
fetches daily temperatures for a NW-Europe centroid from Open-Meteo (keyless),
converts them to HDD/CDD, and splits realised vs forecast so the analyst sees
both the recent demand pull and what's coming. Includes a short forecast tail so
"next week's weather" is on the table, not just history.
"""
import logging

import requests

logger = logging.getLogger(__name__)

OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 30

# NW-Europe demand centroid (Ruhr/BeNeLux) — the core gas-heating load behind TTF.
LATITUDE, LONGITUDE = 51.0, 6.0

# Degree-day balance points (°C). 15.5 is the European heating convention; CDD
# uses 22 since AC cooling load only bites well above room temperature.
HDD_BASE, CDD_BASE = 15.5, 22.0

DEFAULT_LOOKBACK_DAYS = 14
FORECAST_DAYS = 7


def _degree_days(t_max: float, t_min: float) -> tuple[float, float]:
    mean = (t_max + t_min) / 2
    return max(0.0, HDD_BASE - mean), max(0.0, mean - CDD_BASE)


def get_weather_degree_days(curr_date: str, look_back_days: int | None = None) -> str:
    """Fetch NW-Europe HDD/CDD as a markdown report (realised + forecast).

    Args:
        curr_date: "Today" for the run (yyyy-mm-dd); days after it are forecast.
        look_back_days: Realised window length; ``None`` uses DEFAULT_LOOKBACK_DAYS.
    """
    look_back_days = look_back_days or DEFAULT_LOOKBACK_DAYS
    resp = requests.get(
        OPEN_METEO_BASE,
        params={
            "latitude": LATITUDE, "longitude": LONGITUDE,
            "daily": "temperature_2m_max,temperature_2m_min",
            "past_days": min(look_back_days, 92), "forecast_days": FORECAST_DAYS,
            "timezone": "UTC",
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    daily = resp.json().get("daily", {})
    dates = daily.get("time", [])
    tmax, tmin = daily.get("temperature_2m_max", []), daily.get("temperature_2m_min", [])

    rows, hdd_tot, cdd_tot = [], 0.0, 0.0
    for d, hi, lo in zip(dates, tmax, tmin, strict=False):
        if hi is None or lo is None:
            continue
        hdd, cdd = _degree_days(hi, lo)
        kind = "fcst" if d > curr_date else "real"
        if kind == "real":
            hdd_tot += hdd
            cdd_tot += cdd
        rows.append((d, (hi + lo) / 2, hdd, cdd, kind))

    if not rows:
        return "## NW-Europe weather (HDD/CDD)\nNo temperature data returned."

    header = (
        f"## NW-Europe weather degree-days ({LATITUDE}N {LONGITUDE}E)\n"
        f"- HDD base {HDD_BASE}°C, CDD base {CDD_BASE}°C; higher HDD = more gas heating demand\n"
        f"- Realised window totals: {hdd_tot:.0f} HDD, {cdd_tot:.0f} CDD; +7d forecast tail below\n\n"
        "| Date | Mean °C | HDD | CDD | type |\n| --- | --- | --- | --- | --- |\n"
    )
    table = "\n".join(
        f"| {d} | {m:.1f} | {h:.1f} | {c:.1f} | {k} |" for d, m, h, c, k in rows
    )
    return header + table + "\n"
