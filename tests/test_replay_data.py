from pathlib import Path
import pandas as pd
from replay_data import load_synchronized_replay

def write_history(path, offset=0):
    pd.DataFrame({
        "timestamp":["2026-10-09T09:15:00+05:30","2026-10-09T09:16:00+05:30"],
        "open":[100+offset,101+offset],"high":[102+offset,103+offset],
        "low":[99+offset,100+offset],"close":[101+offset,102+offset],"volume":[10,20]
    }).to_csv(path,index=False)

def test_load_synchronized_spot_ce_pe(tmp_path, monkeypatch):
    folder=tmp_path/"data"/"replay"
    folder.mkdir(parents=True)
    write_history(folder/"nifty_spot.csv", 100)
    write_history(folder/"nifty_ce.csv", 10)
    write_history(folder/"nifty_pe.csv", 5)
    pd.DataFrame([{"dataset":"nifty_ce","strike":25000}]).to_csv(folder/"manifest.csv",index=False)
    data,strike=load_synchronized_replay(str(folder))
    assert len(data)==2
    assert data.iloc[0]["spot_close"]==201
    assert data.iloc[0]["ce_close"]==111
    assert data.iloc[0]["pe_close"]==106
    assert strike==25000

def test_missing_files_return_none(tmp_path):
    data,strike=load_synchronized_replay(str(tmp_path/"missing"))
    assert data is None
    assert strike is None
