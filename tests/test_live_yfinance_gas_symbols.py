"""Live Yahoo Finance smoke test for the gas desk's traded symbols.

Every other test in the suite mocks ``yf.download``, so there is no
automated proof that Yahoo still serves ``TTF=F`` (Dutch TTF) and ``NG=F``
(Henry Hub) with the OHLCV shape ``load_ohlcv`` expects. A yfinance version
bump, a Yahoo schema change, or a delisting would fail silently until an
agent run. This module is skipped by default (set ``RUN_LIVE_NETWORK_TESTS=1``)
and run manually to catch that breakage early.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest
import yfinance as yf

from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.stockstats_utils import load_ohlcv


def _run_live_network() -> bool:
    return os.environ.get("RUN_LIVE_NETWORK_TESTS") == "1"


_LIVE_GAS_SYMBOLS = ["TTF=F", "NG=F"]


@pytest.mark.integration
@pytest.mark.skipif(
    not _run_live_network(),
    reason="RUN_LIVE_NETWORK_TESTS!=1; skipping live Yahoo Finance call",
)
@pytest.mark.parametrize("symbol", _LIVE_GAS_SYMBOLS)
class TestLiveGasSymbols:
    def test_load_ohlcv_returns_clean_frame(self, symbol, tmp_path):
        set_config({"data_cache_dir": str(tmp_path)})
        curr_date = (pd.Timestamp.today() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        df = load_ohlcv(symbol, curr_date)
        assert not df.empty
        assert {"Date", "Open", "High", "Low", "Close", "Volume"} <= set(df.columns)
        assert pd.api.types.is_datetime64_any_dtype(df["Date"])
        assert (df["Date"] <= pd.Timestamp(curr_date)).all()
        assert df["Close"].notna().all()
        assert (df["Close"] > 0).all()

    def test_raw_yf_download_schema(self, symbol):
        curr_date = (pd.Timestamp.today() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        start = (pd.Timestamp(curr_date) - pd.Timedelta(days=60)).strftime("%Y-%m-%d")
        end = (pd.Timestamp(curr_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        raw = yf.download(
            symbol,
            start=start,
            end=end,
            auto_adjust=True,
            multi_level_index=False,
            progress=False,
        )
        raw = raw.reset_index()
        assert "Close" in raw.columns
        assert raw["Close"].notna().any()
