import pandas as pd
import pytest
from replay import normalize_ohlcv, resample_ohlcv, visible_bar_count, add_indicators

def sample():
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01 09:15", periods=16, freq="min"),
        "open": [100+i for i in range(16)],
        "high": [102+i for i in range(16)],
        "low": [99+i for i in range(16)],
        "close": [101+i for i in range(16)],
        "volume": [100]*16,
    })

def test_normalize_sorts_and_deduplicates():
    df = sample()
    df = pd.concat([df.iloc[::-1], df.iloc[[0]]], ignore_index=True)
    out = normalize_ohlcv(df)
    assert len(out) == 16
    assert out.timestamp.is_monotonic_increasing

def test_rejects_invalid_candle():
    df = sample()
    df.loc[0, "high"] = 1
    with pytest.raises(ValueError):
        normalize_ohlcv(df)

def test_5m_aggregation():
    out = resample_ohlcv(sample(), 5)
    assert len(out) == 4
    assert out.iloc[0]["volume"] == 500

def test_no_fake_finer_bars():
    df = sample().iloc[::5].reset_index(drop=True)
    with pytest.raises(ValueError):
        resample_ohlcv(df, 1)

def test_clock_reveals_bars_at_real_time_pace():
    assert visible_bar_count(0, 5, 20) == 1
    assert visible_bar_count(299, 5, 20) == 1
    assert visible_bar_count(300, 5, 20) == 2
    assert visible_bar_count(900, 5, 20) == 4

def test_indicators_have_expected_columns():
    out = add_indicators(sample())
    assert {"EMA 9", "EMA 21", "RSI 14", "VWAP"} <= set(out.columns)
    assert out["RSI 14"].between(0, 100).all()
