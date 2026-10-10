# NIFTY Scalper Practice Dashboard

A standalone Streamlit NIFTY options scalper-style paper-trading terminal with an optional Kotak Neo live quote chart, simulated entries/exits, open-position P&L, estimated charges and a downloadable paper journal. It does not place real orders.

## Live chart

- Enable Kotak Neo live quote polling in the sidebar.
- The default live instrument is the NIFTY 50 index (segment nse_cm, instrument name Nifty 50).
- To chart a NIFTY option premium, select nse_fo and enter the exact current pSymbol/token from the Kotak Neo scrip master.
- The chart requests an actual Kotak Neo LTP every 3–15 seconds and plots quotes received in the current Streamlit session. It does not interpolate prices or silently fall back to Yahoo/demo values.
- This is periodic quote polling, not a tick-by-tick WebSocket stream. It only moves when fresh quotes are returned and markets are trading.
- Live quote access requires your own Kotak Neo Trade API consumer key and supported market-data permissions. This dashboard does not submit orders.

### Configure credentials safely (Windows PowerShell)

1. In the project folder, copy .env.example to .env.
2. Edit .env locally and set NEO_CONSUMER_KEY to the Trade API token from your Kotak Neo app.
3. Do not upload .env, paste your token into chat, or put it in source code. The repository ignores .env.
4. Install packages and restart Streamlit:

    python -m pip install -r requirements.txt
    python -m streamlit run app.py

If the API returns an error, the app displays it and does not switch to synthetic or third-party prices. Check the consumer key, current token, segment and API access.

## Paper trading and P&L

- Compact scalper terminal with CE/PE selector, strike selector, snapshot premium and one-click simulated BUY.
- Paper position quantity in lots multiplied by the editable lot-size setting.
- Open-position mark-to-snapshot, simulated close/exit, gross/net P&L, estimated charges and cumulative closed-trade P&L chart.
- Downloadable paper order journal CSV.
- Demo data is clearly labeled and paper entries are disabled in demo mode.

## Data and P&L limitations

- The live chart uses broker LTP quotes. The option-chain chart and paper-position marking still depend on the uploaded option-chain CSV; they do not yet automatically ingest a full live option chain.
- A single option-chain snapshot is not a 1-minute/3-minute contract candle. Use real option-contract OHLCV or repeated timestamped snapshots to build a premium candle chart.
- P&L is a practice estimate: configured per-order charges are deducted, but taxes/levies, bid-ask spread, slippage, partial fills and latency are not fully modeled.
- The default lot-size value is editable and is not a guarantee of the current NIFTY contract lot size. Verify the relevant contract specification.
- Paper positions and journal are stored in Streamlit session state only. Download the journal CSV to keep records; data may be lost when the session resets.

## Run on Windows PowerShell

    cd $HOME\Downloads\nifty-practice-trading-dashboard
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python -m pytest -q
    python -m streamlit run app.py

Open the localhost URL printed by Streamlit, usually http://localhost:8501.

## CSV inputs

Option-chain CSV: include strike and, for full charts/P&L marking, CE LTP, PE LTP, CE OI, PE OI, CE Change in OI, PE Change in OI, CE Volume and PE Volume.

Underlying OHLCV CSV: use a separate CSV with timestamp, open, high, low, close, volume. Do not treat an option-chain snapshot as OHLCV.

## Tests

Run python -m pytest -q to run existing tests plus paper P&L and live-quote response normalization tests.