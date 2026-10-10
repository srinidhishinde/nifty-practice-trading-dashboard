# NIFTY Scalper Practice Dashboard

A NIFTY options scalper-style practice simulator with synchronized NIFTY spot, CE and PE historical replay, moving candles, paper orders and P&L. It never sends real orders.

## Get and load real historical data (Kotak Neo)

The repository includes a downloader. It uses your own Kotak Neo Trade API consumer key to request real historical OHLCV for NIFTY 50 and a current near-ATM CE/PE pair. The dashboard automatically loads the resulting files from `data/replay/` and displays three aligned charts.

**I cannot fetch your account's private Kotak data from this chat, and I have not included fake data under the label of real backdata.** The downloader needs your local API token. Kotak only returns data for supported active contracts; expired options may not be available. Historical 1/3/5-minute requests are limited to 30 days per request; 10/15-minute requests are limited to 60 days. See the [official historical-data API docs](https://github.com/Kotak-Neo/kotak-neo-python/blob/main/docs/functions/market_data/historical_data.md) and [option-chain docs](https://github.com/Kotak-Neo/kotak-neo-python/blob/main/docs/functions/market_data/option_chain.md).

### Windows PowerShell — download last month's 1-minute candles

1. Pull the latest code and install dependencies:

    cd "$HOME\Downloads\nifty-practice-trading-dashboard"
    git pull origin main
    python -m pip install -r requirements.txt

2. Create your local token file if you have not already:

    Copy-Item .env.example .env
    notepad .env

3. Put your own Kotak Neo Trade API token in `.env` as `NEO_CONSUMER_KEY=...`. Never commit or share the token.

4. Run the downloader (defaults to the last 30 calendar days ending yesterday):

    python scripts/download_nifty_replay.py

   For 3-minute candles or a different date range:

    python scripts/download_nifty_replay.py --start 2026-09-10 --end 2026-10-09 --interval 3min

5. Start the app:

    python -m streamlit run app.py

The downloader writes actual returned data to:
- `data/replay/nifty_spot.csv`
- `data/replay/nifty_ce.csv`
- `data/replay/nifty_pe.csv`
- `data/replay/manifest.csv`

The app joins the three datasets by timestamp, so the replay cursor moves across matching spot, CE and PE candles together. It locks the practice strike to the downloaded CE/PE pair. If the API fails or returns no history, it prints an error rather than fabricating real data. Downloaded data is local; it is not committed to GitHub.

## Practice replay

- Enable **Animate simulated market** to advance one candle every 1–5 seconds.
- With synchronized Kotak files present, the three charts use real historical candles and the current simulated premium comes from the replayed CE or PE close.
- Without downloaded data, the fallback chart is synthetic UI practice only, clearly labeled; it is not actual NIFTY data.
- Uploading one option OHLCV CSV is also supported, but only the synchronized three-file download gives aligned spot/CE/PE charts.

## Paper trading and P&L

- CE/PE selection, simulated entries and exits, open/realized P&L, estimated charges, cumulative P&L chart and downloadable journal.
- No orders are sent to a broker.
- Estimated charges do not fully model taxes/levies, spread, slippage, partial fills or latency. Verify lot size and contract expiry.

## Run tests

    python -m pytest -q
