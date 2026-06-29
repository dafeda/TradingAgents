"""Instrument profile table: TTF=F and NG=F are both traded, with a symmetric
alpha benchmark and per-instrument fundamentals availability."""

import unittest

import pytest

from tradingagents.instrument_profiles import (
    InstrumentProfile,
    get_profile,
    has_profile,
)


@pytest.mark.unit
class InstrumentProfileTests(unittest.TestCase):
    def test_ttf_profile_fields(self):
        p = get_profile("TTF=F")
        self.assertIsInstance(p, InstrumentProfile)
        self.assertEqual(p.display_name, "Dutch TTF")
        self.assertEqual(p.currency_unit, "EUR/MWh")
        self.assertEqual(p.region, "EU")
        self.assertTrue(p.fundamentals_available)

    def test_ngf_profile_fields(self):
        p = get_profile("NG=F")
        self.assertEqual(p.display_name, "Henry Hub")
        self.assertEqual(p.currency_unit, "USD/MMBtu")
        self.assertEqual(p.region, "US")
        # No US supply/demand vendors yet — fundamentals analyst is omitted.
        self.assertFalse(p.fundamentals_available)

    def test_symmetric_benchmark(self):
        # Each contract is the other's alpha benchmark (TTF–HH spread).
        self.assertEqual(get_profile("TTF=F").benchmark_ticker, "NG=F")
        self.assertEqual(get_profile("NG=F").benchmark_ticker, "TTF=F")

    def test_unknown_ticker_raises(self):
        with self.assertRaises(KeyError):
            get_profile("AAPL")

    def test_has_profile(self):
        self.assertTrue(has_profile("TTF=F"))
        self.assertTrue(has_profile("NG=F"))
        self.assertFalse(has_profile("AAPL"))

    def test_context_description_mentions_currency(self):
        # The identity line must carry the right currency unit per contract.
        self.assertIn("EUR/MWh", get_profile("TTF=F").context_description)
        self.assertIn("USD/MMBtu", get_profile("NG=F").context_description)

    def test_researcher_framing_uses_instrument_name(self):
        # Bull framing must reference the correct instrument, not hardcode TTF.
        self.assertIn("TTF gas position", get_profile("TTF=F").researcher_framing_bull)
        self.assertIn("Henry Hub", get_profile("NG=F").researcher_framing_bull)
        self.assertIn("TTF gas position", get_profile("TTF=F").researcher_framing_bear)
        self.assertIn("Henry Hub", get_profile("NG=F").researcher_framing_bear)


@pytest.mark.unit
@pytest.mark.parametrize("raw,canonical", [
    ("TTF=F", "TTF=F"),
    ("TTF", "TTF=F"),
    ("eugas", "TTF=F"),
    ("NG=F", "NG=F"),
    ("NATGAS", "NG=F"),
])
def test_alias_resolves_to_profile(raw, canonical):
    # Broker aliases resolve to a known profile.
    assert get_profile(raw).ticker == canonical


if __name__ == "__main__":
    pytest.main([__file__])
