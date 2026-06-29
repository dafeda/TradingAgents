"""EUA carbon vendor: proxy fallback, prefix label, routing."""
import copy
import unittest
from unittest import mock

import pytest

import tradingagents.dataflows.config as config_module
import tradingagents.default_config as default_config
from tradingagents.dataflows import eua, interface
from tradingagents.dataflows.errors import NoMarketDataError


@pytest.mark.unit
class EuaTests(unittest.TestCase):
    def test_first_proxy_used_and_labelled(self):
        with mock.patch.object(eua, "get_YFin_data_online", return_value="ROWS") as f:
            out = eua.get_eua_carbon("2026-06-20", 30)
        self.assertTrue(out.startswith("## EUA carbon (proxy CARB.L"))
        self.assertIn("ROWS", out)
        self.assertEqual(f.call_args[0][0], "CARB.L")

    def test_falls_back_to_second_proxy(self):
        def _side(sym, *a):
            if sym == "CARB.L":
                raise NoMarketDataError("CARB.L", "CARB.L")
            return "KRBN_ROWS"
        with mock.patch.object(eua, "get_YFin_data_online", side_effect=_side):
            out = eua.get_eua_carbon("2026-06-20", 30)
        self.assertIn("proxy KRBN", out)

    def test_all_fail_raises(self):
        with mock.patch.object(eua, "get_YFin_data_online",
                               side_effect=NoMarketDataError("x", "x")), \
             self.assertRaises(NoMarketDataError):
            eua.get_eua_carbon("2026-06-20", 30)


@pytest.mark.unit
class EuaRoutingTests(unittest.TestCase):
    def setUp(self): config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)
    def tearDown(self): config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)

    def test_routes_to_yfinance(self):
        self.assertEqual(interface.get_category_for_method("get_carbon_price"), "carbon_data")
        with mock.patch.dict(interface.VENDOR_METHODS,
                             {"get_carbon_price": {"yfinance": lambda *a, **k: "CO2_OK"}}, clear=False):
            self.assertEqual(interface.route_to_vendor("get_carbon_price", "2026-06-20", 30), "CO2_OK")
