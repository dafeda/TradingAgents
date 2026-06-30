"""EIA weekly gas-storage vendor: config errors, output formatting, regional
filtering (SWO-only), 5-year average, lookahead-safe windowing, and router
integration.

All API access is mocked, so these run without a network connection or a key.
"""
import copy
import unittest
from unittest import mock

import pytest

import tradingagents.dataflows.config as config_module
import tradingagents.default_config as default_config
from tradingagents.dataflows import eia, interface
from tradingagents.dataflows.config import set_config

# EIA v2 returns rows newest-first (per the sort param). Values are strings.
# R48 + 5 regions; R33 (South Central) carries 3 processes (SWO total, SSO
# salt, SNO nonsalt) — only SWO must feed the regional breakdown.
_DATA = [
    {"period": "2026-06-19", "duoarea": "R48", "process": "SWO", "value": "2835", "units": "BCF", "series-description": "Weekly Lower 48 States Natural Gas Working Underground Storage (Billion Cubic Feet)"},
    {"period": "2026-06-12", "duoarea": "R48", "process": "SWO", "value": "2759", "units": "BCF", "series-description": "Weekly Lower 48 States Natural Gas Working Underground Storage (Billion Cubic Feet)"},
    {"period": "2026-06-05", "duoarea": "R48", "process": "SWO", "value": "2686", "units": "BCF", "series-description": "Weekly Lower 48 States Natural Gas Working Underground Storage (Billion Cubic Feet)"},
    {"period": "2026-06-19", "duoarea": "R31", "process": "SWO", "value": "558", "units": "BCF", "series-description": "Weekly East Region Natural Gas Working Underground Storage (Billion Cubic Feet)"},
    {"period": "2026-06-19", "duoarea": "R32", "process": "SWO", "value": "672", "units": "BCF", "series-description": "Weekly Midwest Region Natural Gas Working Underground Storage (Billion Cubic Feet)"},
    {"period": "2026-06-19", "duoarea": "R33", "process": "SWO", "value": "1066", "units": "BCF", "series-description": "Weekly South Central Region Natural Gas Working Underground Storage (Billion Cubic Feet)"},
    # Salt/nonsalt sub-components for R33 — must NOT appear in the regional
    # breakdown (they would double-count the South Central total).
    {"period": "2026-06-19", "duoarea": "R33", "process": "SSO", "value": "325", "units": "BCF", "series-description": "Weekly Salt Region Natural Gas Working Underground Storage (Billion Cubic Feet)"},
    {"period": "2026-06-19", "duoarea": "R33", "process": "SNO", "value": "741", "units": "BCF", "series-description": "Weekly Nonsalt Region Natural Gas Working Underground Storage (Billion Cubic Feet)"},
    {"period": "2026-06-19", "duoarea": "R34", "process": "SWO", "value": "227", "units": "BCF", "series-description": "Weekly Mountain Region Natural Gas Working Underground Storage (Billion Cubic Feet)"},
    {"period": "2026-06-19", "duoarea": "R35", "process": "SWO", "value": "312", "units": "BCF", "series-description": "Weekly Pacific Region Natural Gas Working Underground Storage (Billion Cubic Feet)"},
]


@pytest.mark.unit
class EiaConfigTests(unittest.TestCase):
    def test_missing_key_raises_not_configured(self):
        with mock.patch.dict("os.environ", {}, clear=True), \
                self.assertRaises(eia.EiaNotConfiguredError):
            eia.get_api_key()

    def test_not_configured_is_a_value_error(self):
        self.assertTrue(issubclass(eia.EiaNotConfiguredError, ValueError))

    def test_403_raises_not_configured(self):
        resp = mock.Mock(status_code=403)
        resp.json.return_value = {"error": "access denied"}
        resp.text = '{"error": "access denied"}'
        with mock.patch.dict("os.environ", {"EIA_API_KEY": "x"}, clear=False), \
                mock.patch.object(eia.requests, "get", return_value=resp), \
                self.assertRaises(eia.EiaNotConfiguredError):
            eia._request({"frequency": "weekly"})


@pytest.mark.unit
class EiaFormattingTests(unittest.TestCase):
    def test_report_has_header_latest_change_and_table(self):
        with mock.patch.object(eia, "_weekly_rows", return_value=_DATA), \
                mock.patch.object(eia, "_five_year_avg", return_value=2691.2):
            out = eia.get_us_gas_storage("2026-06-19", 120)
        self.assertIn("## EIA weekly gas storage: Lower 48", out)
        self.assertIn("**Latest:** 2,835 Bcf (2026-06-19)", out)
        self.assertIn("**Wk/wk:** +76 Bcf", out)  # 2835 - 2759
        self.assertIn("**5-yr avg (same wk):** 2,691 Bcf", out)
        self.assertIn("**vs norm:** +144 Bcf (+5.3%)", out)  # 2835 - 2691.2
        self.assertIn("| 2026-06-12 | 2,759 |", out)

    def test_regional_breakdown_uses_swo_total_only(self):
        # South Central must show the SWO total (1066), not the salt (325) or
        # nonsalt (741) sub-components, which would double-count.
        with mock.patch.object(eia, "_weekly_rows", return_value=_DATA), \
                mock.patch.object(eia, "_five_year_avg", return_value=None):
            out = eia.get_us_gas_storage("2026-06-19", 120)
        self.assertIn("| South Central | 1,066 |", out)
        self.assertNotIn("| South Central | 325 |", out)
        self.assertNotIn("| South Central | 741 |", out)

    def test_no_five_year_avg_omits_vs_norm_line(self):
        with mock.patch.object(eia, "_weekly_rows", return_value=_DATA), \
                mock.patch.object(eia, "_five_year_avg", return_value=None):
            out = eia.get_us_gas_storage("2026-06-19", 120)
        self.assertIn("**Latest:**", out)
        self.assertIn("**Wk/wk:**", out)
        self.assertNotIn("**vs norm:**", out)
        self.assertNotIn("5-yr avg", out)

    def test_empty_window_reports_no_observations(self):
        with mock.patch.object(eia, "_weekly_rows", return_value=[]):
            out = eia.get_us_gas_storage("2026-06-19", 5)
        self.assertIn("No storage observations", out)

    def test_window_is_lookahead_safe(self):
        captured = {}

        def _capture(end_date, look_back_days, regions):
            captured["end_date"] = end_date
            captured["look_back_days"] = look_back_days
            captured["regions"] = regions
            return _DATA

        with mock.patch.object(eia, "_weekly_rows", side_effect=_capture), \
                mock.patch.object(eia, "_five_year_avg", return_value=None):
            eia.get_us_gas_storage("2026-06-19", 120)
        self.assertEqual(captured["end_date"], "2026-06-19")
        self.assertEqual(captured["look_back_days"], 120)
        self.assertEqual(captured["regions"], list(eia.REGIONS))


@pytest.mark.unit
class EiaRoutingTests(unittest.TestCase):
    def setUp(self):
        config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)

    def tearDown(self):
        config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)

    def test_storage_category_routes_to_eia(self):
        self.assertEqual(
            interface.get_category_for_method("get_us_gas_storage"), "us_gas_storage"
        )
        set_config({"data_vendors": {"us_gas_storage": "eia"}})
        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_us_gas_storage": {"eia": lambda *a, **k: "STORAGE_OK"}},
            clear=False,
        ):
            out = interface.route_to_vendor("get_us_gas_storage", "2026-06-19", 120)
        self.assertEqual(out, "STORAGE_OK")

    def test_not_configured_degrades_gracefully(self):
        set_config({"data_vendors": {"us_gas_storage": "eia"}})

        def _unconfigured(*a, **k):
            raise eia.EiaNotConfiguredError("EIA_API_KEY not set")

        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_us_gas_storage": {"eia": _unconfigured}},
            clear=False,
        ):
            out = interface.route_to_vendor("get_us_gas_storage", "2026-06-19", 120)
        self.assertIn("DATA_UNAVAILABLE", out)

    def test_us_weather_routes_to_open_meteo(self):
        self.assertEqual(
            interface.get_category_for_method("get_us_weather"), "us_weather_data"
        )
        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_us_weather": {"open_meteo": lambda *a, **k: "US_WX_OK"}},
            clear=False,
        ):
            self.assertEqual(
                interface.route_to_vendor("get_us_weather", "2026-06-19", 14),
                "US_WX_OK",
            )


if __name__ == "__main__":
    unittest.main()
