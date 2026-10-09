from __future__ import annotations
import numpy as np
import pandas as pd

ALIASES = {
    "timestamp": ("timestamp", "datetime", "date_time", "date", "time"),
    "open": ("open", "o"),
    "high": ("high", "h"),
    "low": ("low", "l"),
    "close": ("close", "last", "ltp", "c"),
    "volume": ("volume", "vol", "v", "qty"),
}

def normalize_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        raise ValueError("The CSV has no candle rows.")
    result = frame.copy()
    result.columns = [str(c).strip().lower().replace(" ", "_") for c in result.columns]
    rename = {}
    for canonical, candidates in ALIASES.items():
        match = next((c for c in candidates if c in result.columns), None)
        if match is None:
            raise ValueError(f"Missing required OHLCV column: {canonical}.")
        rename[match] = canonical
    result = result.rename(columns=rename)[list(ALIASES)]
    result["timestamp"] = pd.to_datetime(result["timestamp"], errors="coerce")
    for col in ("open", "high", "low", "close", "volume"):
        result[col] = pd.to_numeric(result[col], errors="coerce")
    result = result.dropna(subset=list(ALIASES)).sort_values("timestamp")
    result = result.drop_duplicates("timestamp", keep="last").reset_index(drop=True)
    if result.empty: raise ValueError("No valid timestamped OHLCV rows were found.")
    if (result["volume"] < 0).any(): raise ValueError("Volume cannot be negative.")
    if (result["high"] < result[["open","close","low"]].max(axis=1)).any():
        raise ValueError("Invalid candle: high is below open, close, or low.")
    if (result["low"] > result[["open","close","high"]].min(axis=1)).any():
        raise ValueError("Invalid candle: low is above open, close, or high.")
    return result

def resample_ohlcv(frame: pd.DataFrame, timeframe_minutes: int) -> pd.DataFrame:
    if timeframe_minutes not in (1,3,5,10,15):
        raise ValueError("Timeframe must be 1, 3, 5, 10, or 15 minutes.")
    data = normalize_ohlcv(frame)
    if len(data) > 1:
        gaps = data["timestamp"].diff().dropna().dt.total_seconds()
        positive = gaps[gaps > 0]
        source_seconds = float(positive.median()) if not positive.empty else 60.0
        if source_seconds > timeframe_minutes * 60 * 1.25:
            raise ValueError("Source bars are coarser than the selected timeframe; finer candles cannot be reconstructed.")
    data = data.set_index("timestamp")
    bars = data.resample(f"{timeframe_minutes}min", origin="start", label="left", closed="left").agg(
        open=("open","first"), high=("high","max"), low=("low","min"),
        close=("close","last"), volume=("volume","sum"))
    return bars.dropna(subset=["open","high","low","close"]).reset_index()

def visible_bar_count(elapsed_seconds: float, timeframe_minutes: int, total_bars: int) -> int:
    if total_bars <= 0: return 0
    return min(total_bars, 1 + max(0, int(max(0.0, elapsed_seconds) // (timeframe_minutes * 60))))

def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = result["close"].astype(float)
    result["EMA 9"] = close.ewm(span=9, adjust=False, min_periods=1).mean()
    result["EMA 21"] = close.ewm(span=21, adjust=False, min_periods=1).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=1).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=1).mean()
    rs = gain / loss.replace(0, np.nan)
    result["RSI 14"] = (100 - 100/(1+rs)).fillna(50.0)
    typical = (result["high"] + result["low"] + result["close"]) / 3
    vol = result["volume"].astype(float)
    result["VWAP"] = ((typical*vol).cumsum()/vol.cumsum().replace(0,np.nan)).fillna(typical)
    return result
