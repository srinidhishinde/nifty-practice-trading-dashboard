# NIFTY Options Scalper Dashboard

A standalone Streamlit **NIFTY options-chain analysis and practice dashboard** focused on 1–3 minute scalping workflows. It is not connected to a broker and does not provide live quotes or execute orders.

## Features

- Strike-wise CE/PE premium comparison, OI, change in OI, and nearby volume charts.
- PCR (open interest) summary and reference strike selected from observed spot, if supplied; otherwise explicitly a strike-midpoint proxy.
- CSV normalization for common option-chain labels.
- Optional separate NIFTY index OHLCV CSV chart with EMA 9, EMA 21 and VWAP.
- Demo chain clearly marked as invented example data. Demo data never creates a market bias or trade signal.
- Download normalized chain for review.

## Important data limits

- **No Kotak Neo authentication, live feed, or order execution is implemented.** Upload a snapshot from a source you trust and check its timestamp before interpreting it.
- A single option-chain snapshot is not a 1-minute/3-minute option candle. For premium candles, use real contract OHLCV or multiple timestamped snapshots per strike.
- OI, PCR, and volume alone do not justify buying CE or PE. Confirm with underlying price action, spread/liquidity, freshness, expiry and risk rules.
- Never use illustrative demo prices for trading decisions.

## Run on Windows PowerShell

```powershell
cd "$HOME\Downloads\nifty-practice-trading-dashboard"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the localhost URL printed by Streamlit, usually http://localhost:8501.

## Option-chain CSV

At minimum, include a strike column. To see the full analysis, include fields such as CE LTP, PE LTP, CE OI, PE OI, CE Change in OI, PE Change in OI, CE Volume, and PE Volume. Common variants such as "Strike Price", "Call LTP", "Put LTP", "CE Chg in OI" and "PE Chg in OI" are normalized. Exact headings depend on the export source.

## NIFTY underlying OHLCV CSV

Use a separate CSV with `timestamp,open,high,low,close,volume`. Do not treat an option-chain snapshot as OHLCV.

## Tests

```powershell
python -m pytest -q
```

The option-chain helper tests cover common header normalization, numeric commas, missing strikes, duplicate strikes, PCR calculation, reference strike selection, and demo-data safeguards. The original replay helper tests remain in the repository.
