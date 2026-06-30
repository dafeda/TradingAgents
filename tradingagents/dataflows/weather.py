"""Weather degree-days vendor — heating/cooling demand via Open-Meteo.

Heating degree days (HDD) are the dominant short-term gas demand driver: a cold
spell pulls gas out of storage and bids the front of the curve. This fetches
daily temperatures for a demand centroid from Open-Meteo (keyless), converts
them to HDD/CDD, and splits realised vs forecast so the analyst sees both the
recent demand pull and what's coming. Includes a short forecast tail so
"next week's weather" is on the table, not just history.

Two centroids are served from one code path:
  * NW-Europe (Ruhr/BeNeLux) — the core gas-heating load behind Dutch TTF.
  * CONUS (~39°N 98°W) — the US population-weighted centroid behind Henry Hub.
The US is large, so a single national centroid is a v1; a multi-centroid
enhancement (Northeast heating + Gulf LNG) is a follow-up.
"""
import logging

import requests

logger = logging.getLogger(__name__)

OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 30

# Degree-day balance points (°C). 15.5 is the European heating convention; CDD
# uses 22 since AC cooling load only bites well above room temperature.
HDD_BASE, CDD_BASE = 15.5, 22.0

DEFAULT_LOOKBACK_DAYS = 14
FORECAST_DAYS = 7

# NW-Europe demand centroid (Ruhr/BeNeLux) — the core gas-heating load behind TTF.
EU_LATITUDE, EU_LONGITUDE = 51.0, 6.0

# CONUS population-weighted centroid (~39°N 98°W) — the US gas-heating load
# behind Henry Hub. A single national centroid is a v1; the US is large enough
# that a Northeast heating + Gulf LNG multi-centroid split is a follow-up.
US_LATITUDE, US_LONGITUDE = 39.0, -98.0


def _degree_days(t_max: float, t_min: float) -> tuple[float, float]:
    mean = (t_max + t_min) / 2
    return max(0.0, HDD_BASE - mean), max(0.0, mean - CDD_BASE)


def _fetch_degree_days(
    latitude: float, longitude: float, label: str, curr_date: str,
    look_back_days: int | None = None,
) -> str:
    """Fetch HDD/CDD as a markdown report (realised + forecast) for a centroid.

    Args:
        latitude, longitude: Demand centroid coordinates.
        label: Region label for the report header (e.g. "NW-Europe", "CONUS").
        curr_date: "Today" for the run (yyyy-mm-dd); days after it are forecast.
        look_back_days: Realised window length; ``None`` uses DEFAULT_LOOKBACK_DAYS.
    """
    look_back_days = look_back_days or DEFAULT_LOOKBACK_DAYS
    resp = requests.get(
        OPEN_METEO_BASE,
        params={
            "latitude": latitude, "longitude": longitude,
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
        return f"## {label} weather (HDD/CDD)\nNo temperature data returned."

    header = (
        f"## {label} weather degree-days ({latitude}N {longitude}E)\n"
        f"- HDD base {HDD_BASE}°C, CDD base {CDD_BASE}°C; higher HDD = more gas heating demand\n"
        f"- Realised window totals: {hdd_tot:.0f} HDD, {cdd_tot:.0f} CDD; +{FORECAST_DAYS}d forecast tail below\n\n"
        "| Date | Mean °C | HDD | CDD | type |\n| --- | --- | --- | --- | --- |\n"
    )
    table = "\n".join(
        f"| {d} | {m:.1f} | {h:.1f} | {c:.1f} | {k} |" for d, m, h, c, k in rows
    )
    return header + table + "\n"


def get_weather_degree_days(curr_date: str, look_back_days: int | None = None) -> str:
    """Fetch NW-Europe HDD/CDD as a markdown report (realised + forecast).

    Args:
        curr_date: "Today" for the run (yyyy-mm-dd); days after it are forecast.
        look_back_days: Realised window length; ``None`` uses DEFAULT_LOOKBACK_DAYS.
    """
    return _fetch_degree_days(
        EU_LATITUDE, EU_LONGITUDE, "NW-Europe", curr_date, look_back_days
    )


def get_us_weather_degree_days(curr_date: str, look_back_days: int | None = None) -> str:
    """Fetch CONUS HDD/CDD as a markdown report (realised + forecast).

    The US centroid is a single national point (~39°N 98°W); a multi-centroid
    split (Northeast heating + Gulf LNG) is a follow-up enhancement.

    Args:
        curr_date: "Today" for the run (yyyy-mm-dd); days after it are forecast.
        look_back_days: Realised window length; ``None`` uses DEFAULT_LOOKBACK_DAYS.
    """
    return _fetch_degree_days(
        US_LATITUDE, US_LONGITUDE, "CONUS", curr_date, look_back_days
    )
