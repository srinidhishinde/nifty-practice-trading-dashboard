from pathlib import Path
import pandas as pd

def load_synchronized_replay(directory="data/replay"):
    root = Path(directory)
    paths = {"spot": root / "nifty_spot.csv", "ce": root / "nifty_ce.csv", "pe": root / "nifty_pe.csv"}
    if not all(path.exists() for path in paths.values()):
        return None, None
    frames = {}
    required = ["timestamp", "open", "high", "low", "close", "volume"]
    for prefix, path in paths.items():
        frame = pd.read_csv(path)
        if not set(required).issubset(frame.columns):
            raise ValueError(f"{path} must contain columns: {', '.join(required)}")
        frame = frame[required].copy()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
        for col in required[1:]:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame = frame.dropna(subset=required).sort_values("timestamp").drop_duplicates("timestamp")
        frames[prefix] = frame.rename(columns={c: f"{prefix}_{c}" for c in required if c != "timestamp"})
    synced = frames["spot"].merge(frames["ce"], on="timestamp", how="inner").merge(frames["pe"], on="timestamp", how="inner")
    synced = synced.sort_values("timestamp").reset_index(drop=True)
    if len(synced) < 2:
        return None, None
    strike = None
    manifest_path = root / "manifest.csv"
    if manifest_path.exists():
        manifest = pd.read_csv(manifest_path)
        selected = manifest.loc[manifest["dataset"] == "nifty_ce"]
        if not selected.empty and "strike" in selected.columns:
            try:
                strike = float(selected.iloc[0]["strike"])
            except (TypeError, ValueError):
                pass
    return synced, strike
