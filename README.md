# NIFTY Scalper Practice Dashboard

A standalone Streamlit **NIFTY options scalper-style paper-trading terminal**, inspired by compact chart/order/position workflows. It supports simulated entries/exits, open-position marking from uploaded option-chain snapshots, estimated net P&L, and a downloadable paper journal. It is not connected to a broker and cannot place real orders.

## Features

- Compact scalper terminal with CE/PE selector, strike selector, snapshot premium, and one-click simulated BUY.
- Paper position quantity in lots × editable lot-size setting.
- Open-position mark-to-snapshot, simulated close/exit, gross/net P&L, estimated charges, and cumulative closed-trade P&L chart.
- Option-chain premium, OI, change-in-OI and nearby-volume charts; PCR (OI) summary.
- Optional NIFTY underlying OHLCV candlestick chart with EMA 9 and EMA 21.
- Downloadable paper order journal CSV.
- Demo data is clearly labeled and **paper entries are disabled in demo mode**.

## Data and P&L limitations

- **No Kotak Neo authentication, live feed, or order execution is implemented.** Upload an option-chain CSV from a trusted source and check its timestamp.
- A single option-chain snapshot is not a 1-minute/3-minute contract candle. Use real option-contract OHLCV or repeated timestamped snapshots to build a premium time-series chart.
- P&L is a practice estimate: configured per-order charges are deducted, but brokerage/taxes/levies, bid-ask spread, slippage, partial fills and latency are not fully modeled.
- The default lot-size value is editable and is not a guarantee of the current NIFTY contract lot size. Verify the relevant contract specification.
- Paper positions and journal are stored in Streamlit session state only. Download the journal CSV to keep records; data may be lost when the session resets.
- Uploaded data may be stale. No automatic live BUY CE/BUY PE recommendation is generated.

## Run on Windows PowerShell

```powershell
cd "$HOME\Downloads\nifty-practice-trading-dashboard"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python -m streamlit run app.py
```

Open the localhost URL printed by Streamlit, usually http://localhost:8501.

## Option-chain CSV

Include strike and, for full charts/P&L marking, CE LTP, PE LTP, CE OI, PE OI, CE Change in OI, PE Change in OI, CE Volume and PE Volume. Common variants such as "Strike Price", "Call LTP", "Put LTP", "CE Chg in OI" and "PE Chg in OI" are normalized.

## NIFTY underlying OHLCV CSV

Use a separate CSV with `timestamp,open,high,low,close,volume`. Do not treat an option-chain snapshot as OHLCV.

## Tests

`python -m pytest -q` runs existing CSV/replay tests and new paper P&L helper tests.
