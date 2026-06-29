"""CLI symbol normalization must agree with the data path (gas-only desk)."""
import pytest

from cli.utils import normalize_ticker_symbol
from tradingagents.dataflows.symbol_utils import normalize_symbol


# --- gas aliases resolve to canonical Yahoo futures; everything else passes through ---
@pytest.mark.parametrize("raw,expected", [
    ("TTF", "TTF=F"),
    ("ttf", "TTF=F"),
    ("DUTCHTTF", "TTF=F"),
    ("EUGAS", "TTF=F"),
    ("NATGAS", "NG=F"),
    ("XNGUSD", "NG=F"),
    # already-canonical symbols are untouched
    ("TTF=F", "TTF=F"),
    ("NG=F", "NG=F"),
    # unknown / Yahoo-native symbols pass through upper-cased
    ("CARB.L", "CARB.L"),
])
def test_normalize_symbol_gas_aliases_and_passthrough(raw, expected):
    assert normalize_symbol(raw) == expected


def test_cli_normalize_delegates_to_data_layer():
    # CLI must produce the same canonical symbol the data path will price.
    for raw in ("TTF", "ng=f", "TTF=F", "eugas"):
        assert normalize_ticker_symbol(raw) == normalize_symbol(raw)
