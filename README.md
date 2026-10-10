# NIFTY Scalper Practice Dashboard

A NIFTY options scalper-style **practice simulator** inspired by compact chart, strike-selection, one-tap order, position and P&L workflows. It supports automatically advancing practice candles and paper trades. No real orders are sent.

## Simulated live movement (works after market hours)

- Enable **Animate simulated market** in the sidebar. The chart advances automatically, with a configurable 1–5 second delay per candle.
- Without a file, it creates clearly labeled synthetic practice candles. This is for practising the UI and order/P&L workflow only; it is not historical or current market data.
- For realistic replay, upload a historical option-contract OHLCV CSV with timestamp, open, high, low, close and volume. The chart replays one candle at a time and can loop.
- The selected practice option premium follows the replay price so you can practise simulated entries, exits and P&L as the chart moves.
- Synthetic/replay data must never be interpreted as live market prices or a predictive signal.

## Optional actual Kotak Neo quotes

The sidebar also has a separate **Enable Kotak Neo live quote polling** control. This is optional and distinct from practice replay. It requires your own Trade API consumer key and market-data access.

1. Copy .env.example to .env locally.
2. Set NEO_CONSUMER_KEY in .env.
3. Do not commit .env or share the token.
4. Install requirements and restart Streamlit.

The live quote chart polls every 3–15 seconds. It is not a tick-by-tick WebSocket stream. There is no silent fallback to third-party or demo data when the API fails.

## Paper trading and P&L

- CE/PE and strike selection, simulated BUY and close actions.
- Position size as lots × editable lot-size setting.
- Open-position, realized and unrealized P&L, estimated charges, cumulative closed-trade chart and downloadable CSV journal.
- Paper orders do not reach a broker. Charges are configurable estimates; taxes/levies, spread, slippage, partial fills and latency are not fully modeled.
- Paper positions and journal are held in Streamlit session state. Download the journal to retain a copy.

## Install and run (Windows PowerShell)

    cd $HOME\Downloads\nifty-practice-trading-dashboard
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python -m pytest -q
    python -m streamlit run app.py

## Historical replay CSV

Use a file for the exact option contract with these columns:

    timestamp,open,high,low,close,volume

A single option-chain snapshot (strikes with CE/PE LTP and OI) is not an OHLCV time series. The chain panel remains a snapshot; to replay historical premium movement, upload the contract's actual candle CSV.
