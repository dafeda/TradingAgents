"""Weather degree-days vendor: HDD/CDD math, realised/forecast split, routing."""
import unittest
from unittest import mock

import pytest

from tradingagents.dataflows import interface, weather

_DAILY = {
    "daily": {
        "time": ["2026-06-26", "2026-06-27", "2026-06-28"],
        "temperature_2m_max": [10.0, 12.0, 20.0],
        "temperature_2m_min": [4.0, 6.0, 16.0],
    }
}


@pytest.mark.unit
class WeatherTests(unittest.TestCase):
    def test_degree_days_math(self):
        hdd, cdd = weather._degree_days(10.0, 4.0)  # mean 7 -> 8.5 HDD
        self.assertAlmostEqual(hdd, 8.5)
        self.assertEqual(cdd, 0.0)

    def test_realised_vs_forecast_split(self):
        resp = mock.Mock(status_code=200)
        resp.json.return_value = _DAILY
        with mock.patch.object(weather.requests, "get", return_value=resp):
            out = weather.get_weather_degree_days("2026-06-27", 14)
        self.assertIn("NW-Europe weather degree-days", out)
        self.assertIn("| 2026-06-26 | 7.0 |", out)
        self.assertIn("real |", out)
        self.assertIn("fcst |", out)  # 06-28 is after curr_date

    def test_us_centroid_labels_conus(self):
        resp = mock.Mock(status_code=200)
        resp.json.return_value = _DAILY
        with mock.patch.object(weather.requests, "get", return_value=resp):
            out = weather.get_us_weather_degree_days("2026-06-27", 14)
        self.assertIn("CONUS weather degree-days", out)
        # The CONUS centroid (~39°N 98°W) must be passed through, not the EU one.
        self.assertIn("39.0N -98.0E", out)
        self.assertNotIn("51.0N", out)

    def test_empty_payload(self):
        resp = mock.Mock(status_code=200)
        resp.json.return_value = {"daily": {}}
        with mock.patch.object(weather.requests, "get", return_value=resp):
            self.assertIn("No temperature data", weather.get_weather_degree_days("2026-06-27"))


@pytest.mark.unit
class WeatherRoutingTests(unittest.TestCase):
    def test_routes_to_open_meteo(self):
        self.assertEqual(interface.get_category_for_method("get_weather"), "weather_data")
        with mock.patch.dict(interface.VENDOR_METHODS,
                             {"get_weather": {"open_meteo": lambda *a, **k: "WX_OK"}}, clear=False):
            self.assertEqual(interface.route_to_vendor("get_weather", "2026-06-27", 14), "WX_OK")
