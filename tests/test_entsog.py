"""ENTSOG pipeline-flow vendor: aggregation, Norway/LNG tagging, routing."""
import unittest
from unittest import mock

import pytest

from tradingagents.dataflows import entsog, interface

_FLOWS = {
    "operationaldata": [
        {"pointLabel": "Dornum / NETRA", "value": "1000000000"},   # 1000 GWh, Norway
        {"pointLabel": "GATE LNG", "value": "500000000"},          # 500 GWh, LNG
        {"pointLabel": "GATE LNG", "value": "500000000"},          # +500 -> 1000
        {"pointLabel": "Mazara", "value": ""},                     # empty -> skipped
    ]
}


@pytest.mark.unit
class EntsogTests(unittest.TestCase):
    def test_aggregates_and_tags(self):
        resp = mock.Mock(status_code=200)
        resp.json.return_value = _FLOWS
        with mock.patch.object(entsog.requests, "get", return_value=resp):
            out = entsog.get_pipeline_flows("2026-06-27", 2)
        self.assertIn("ENTSOG EU entry flows", out)
        self.assertIn("| Dornum / NETRA | 1,000 | Norway |", out)
        self.assertIn("| GATE LNG | 1,000 | LNG |", out)  # summed
        self.assertNotIn("Mazara", out)                   # empty value skipped

    def test_empty(self):
        resp = mock.Mock(status_code=200)
        resp.json.return_value = {"operationaldata": []}
        with mock.patch.object(entsog.requests, "get", return_value=resp):
            self.assertIn("No physical-flow data", entsog.get_pipeline_flows("2026-06-27"))


@pytest.mark.unit
class EntsogRoutingTests(unittest.TestCase):
    def test_routes_to_entsog(self):
        self.assertEqual(interface.get_category_for_method("get_pipeline_flows"), "pipeline_flows")
        with mock.patch.dict(interface.VENDOR_METHODS,
                             {"get_pipeline_flows": {"entsog": lambda *a, **k: "FLOW_OK"}}, clear=False):
            self.assertEqual(interface.route_to_vendor("get_pipeline_flows", "2026-06-27", 2), "FLOW_OK")
