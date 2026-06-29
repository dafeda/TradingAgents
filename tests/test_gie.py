"""GIE AGSI+ storage vendor: area resolution, config errors, output formatting,
missing-value handling, lookahead-safe windowing, and router integration.

All API access is mocked, so these run without a network connection or a key.
"""
import copy
import unittest
from unittest import mock

import pytest

import tradingagents.dataflows.config as config_module
import tradingagents.default_config as default_config
from tradingagents.dataflows import gie, interface
from tradingagents.dataflows.config import set_config

# AGSI+ returns newest-first; values are strings, "-" marks a missing day.
_DATA = {
    "data": [
        {"gasDayStart": "2026-06-04", "full": "48.3", "gasInStorage": "546.0", "netWithdrawal": "-3711"},
        {"gasDayStart": "2026-06-03", "full": "-", "gasInStorage": "-", "netWithdrawal": "-"},
        {"gasDayStart": "2026-06-02", "full": "47.9", "gasInStorage": "541.0", "netWithdrawal": "-3500"},
        {"gasDayStart": "2026-06-01", "full": "47.0", "gasInStorage": "531.0", "netWithdrawal": "-3000"},
    ]
}


@pytest.mark.unit
class GieAreaTests(unittest.TestCase):
    def test_eu_and_default_resolve_to_nl(self):
        # AGSI+ has no queryable aggregate window; NL is the TTF hub proxy.
        self.assertEqual(gie._resolve_area("EU"), "NL")
        self.assertEqual(gie._resolve_area("europe"), "NL")

    def test_ttf_and_dutch_map_to_nl(self):
        self.assertEqual(gie._resolve_area("TTF"), "NL")
        self.assertEqual(gie._resolve_area("Dutch"), "NL")

    def test_bare_iso_code_passes_through(self):
        self.assertEqual(gie._resolve_area("ES"), "ES")

    def test_unknown_phrase_falls_back_to_nl(self):
        self.assertEqual(gie._resolve_area("the whole continent"), "NL")


@pytest.mark.unit
class GieConfigTests(unittest.TestCase):
    def test_missing_key_raises_not_configured(self):
        with mock.patch.dict("os.environ", {}, clear=True), \
                self.assertRaises(gie.GieNotConfiguredError):
            gie.get_api_key()

    def test_not_configured_is_a_value_error(self):
        self.assertTrue(issubclass(gie.GieNotConfiguredError, ValueError))

    def test_invalid_key_200_error_body_raises_not_configured(self):
        # AGSI+ returns HTTP 200 with an error body for a bad key; that must be
        # treated as unavailable, not as empty storage data.
        resp = mock.Mock(status_code=200)
        resp.json.return_value = {"error": "access denied", "message": "Invalid or missing API key", "data": []}
        with mock.patch.dict("os.environ", {"GIE_API_KEY": "x"}, clear=False), \
                mock.patch.object(gie.requests, "get", return_value=resp), \
                self.assertRaises(gie.GieNotConfiguredError):
            gie._request({"country": "NL"})


@pytest.mark.unit
class GieFormattingTests(unittest.TestCase):
    def test_report_has_header_latest_change_and_table(self):
        with mock.patch.object(gie, "_request", return_value=_DATA):
            out = gie.get_gas_storage("TTF", "2026-06-04", 60)
        self.assertIn("## GIE AGSI+ gas storage: NL", out)
        self.assertIn("**Latest:** 48.3% full, 546.0 TWh (2026-06-04)", out)
        self.assertIn("+1.30pp from 47.0% (2026-06-01)", out)
        self.assertIn("| 2026-06-01 | 47.0 | 531.0 | -3000 |", out)

    def test_missing_day_is_rendered_without_crashing(self):
        with mock.patch.object(gie, "_request", return_value=_DATA):
            out = gie.get_gas_storage("EU", "2026-06-04", 60)
        self.assertIn("| 2026-06-03 | - | - | - |", out)

    def test_empty_window_reports_no_observations(self):
        with mock.patch.object(gie, "_request", return_value={"data": []}):
            out = gie.get_gas_storage("EU", "2026-06-04", 5)
        self.assertIn("No storage observations", out)

    def test_window_is_lookahead_safe(self):
        captured = {}

        def _capture(params):
            captured.update(params)
            return _DATA

        with mock.patch.object(gie, "_request", side_effect=_capture):
            gie.get_gas_storage("TTF", "2026-06-04", 60)
        self.assertEqual(captured["to"], "2026-06-04")
        self.assertEqual(captured["from"], "2026-04-05")  # 60d back
        self.assertEqual(captured["country"], "NL")


@pytest.mark.unit
class GieRoutingTests(unittest.TestCase):
    def setUp(self):
        config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)

    def tearDown(self):
        config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)

    def test_storage_category_routes_to_gie(self):
        self.assertEqual(
            interface.get_category_for_method("get_gas_storage"), "gas_storage"
        )
        set_config({"data_vendors": {"gas_storage": "gie"}})
        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_gas_storage": {"gie": lambda *a, **k: "STORAGE_OK"}},
            clear=False,
        ):
            out = interface.route_to_vendor("get_gas_storage", "EU", "2026-06-04", 60)
        self.assertEqual(out, "STORAGE_OK")

    def test_not_configured_degrades_gracefully(self):
        set_config({"data_vendors": {"gas_storage": "gie"}})

        def _unconfigured(*a, **k):
            raise gie.GieNotConfiguredError("GIE_API_KEY not set")

        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_gas_storage": {"gie": _unconfigured}},
            clear=False,
        ):
            out = interface.route_to_vendor("get_gas_storage", "EU", "2026-06-04", 60)
        self.assertIn("DATA_UNAVAILABLE", out)


if __name__ == "__main__":
    unittest.main()
