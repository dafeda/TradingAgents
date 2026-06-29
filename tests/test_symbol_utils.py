"""Tests for symbol normalization and the no-data routing sentinel."""

import unittest

import pytest

from tradingagents.dataflows.symbol_utils import (
    NoMarketDataError,
    is_yahoo_safe,
    normalize_symbol,
)


@pytest.mark.unit
class TestNormalizeSymbol(unittest.TestCase):
    def test_plain_equities_unchanged(self):
        for sym in ("AAPL", "MSFT", "TSM", "BRK.B", "0700.HK", "^GSPC", "GC=F"):
            self.assertEqual(normalize_symbol(sym), sym)

    def test_lowercases_are_upper(self):
        self.assertEqual(normalize_symbol("aapl"), "AAPL")
        self.assertEqual(normalize_symbol("  msft  "), "MSFT")

    def test_gas_aliases_map_to_futures(self):
        self.assertEqual(normalize_symbol("TTF"), "TTF=F")
        self.assertEqual(normalize_symbol("TTF+"), "TTF=F")   # broker CFD suffix
        self.assertEqual(normalize_symbol("ttf"), "TTF=F")
        self.assertEqual(normalize_symbol("DUTCHTTF"), "TTF=F")
        self.assertEqual(normalize_symbol("EUGAS"), "TTF=F")
        self.assertEqual(normalize_symbol("NATGAS"), "NG=F")
        self.assertEqual(normalize_symbol("XNGUSD"), "NG=F")

    def test_non_gas_symbols_pass_through(self):
        # Forex/crypto/metals are no longer special-cased on this gas-only desk;
        # unknown symbols pass through upper-cased.
        for sym in ("EURUSD", "BTCUSD", "XAUUSD", "USOIL", "SPX500"):
            self.assertEqual(normalize_symbol(sym), sym)

    def test_six_letter_non_currency_left_alone(self):
        # GOOGLE-style 6-letter tickers that aren't two currency codes
        # must not be mangled into a fake forex pair.
        self.assertEqual(normalize_symbol("ABCDEF"), "ABCDEF")

    def test_empty_input_passthrough(self):
        self.assertEqual(normalize_symbol(""), "")


@pytest.mark.unit
class TestNoMarketDataError(unittest.TestCase):
    def test_message_includes_resolution(self):
        err = NoMarketDataError("XAUUSD+", "GC=F", "no rows")
        self.assertIn("XAUUSD+", str(err))
        self.assertIn("GC=F", str(err))
        self.assertEqual(err.symbol, "XAUUSD+")
        self.assertEqual(err.canonical, "GC=F")

    def test_canonical_defaults_to_symbol(self):
        err = NoMarketDataError("FOOBAR")
        self.assertEqual(err.canonical, "FOOBAR")


@pytest.mark.unit
class TestIsYahooSafe(unittest.TestCase):
    def test_accepts_structural_chars(self):
        for sym in ("AAPL", "GC=F", "^GSPC", "BRK.B", "BTC-USD"):
            self.assertTrue(is_yahoo_safe(sym))

    def test_rejects_slash_and_space(self):
        for sym in ("a/b", "AA PL", ""):
            self.assertFalse(is_yahoo_safe(sym))


if __name__ == "__main__":
    unittest.main()
