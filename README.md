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

## Full-width option-chain chart workspace

- Select a strike in the Scalper terminal and choose **Open CE** or **Open PE** to open a full-width chart workspace.
- The workspace includes a premium candlestick chart, EMA 9/21 overlays, entry premium, stop-loss, target, quantity and BUY / SELL-CLOSE paper controls.
- A practice BUY opens a simulated long option position; SELL / CLOSE records the simulated exit and net P&L. It does not send any broker order.
- The workspace follows the selected replay price. When synchronized Kotak historical data is installed, CE/PE replay prices come from the downloaded historical contracts. Otherwise the fallback is explicitly synthetic.
- Stop loss and target are shown as order-ticket levels. Check them and use SELL / CLOSE to exit; automated stop/target fills are not guaranteed by this UI.


## Candle Movement Lab (synthetic practice)

A dedicated page now demonstrates candles forming tick by tick, rather than revealing only completed historical candles. Open the Streamlit app and choose **Candle Movement Lab** from the multipage navigation.

- The active synthetic NIFTY candle updates its close, high, low and volume on each refresh, then a new candle begins after the configured number of ticks.
- Choose 1-, 2-, 3- or 5-minute candle labels, an intrabar update rate, and a price-action scenario (uptrend/pullbacks, downtrend/bounces, range, breakout/retest, or mixed).
- An illustrative CE/PE premium path and paper BUY / SELL-CLOSE ticket are provided for practice. Paper P&L is calculated from the synthetic premium path and user-entered quantity.
- Synthetic prices are not actual NIFTY/option quotes, not a forecast, and not intended for evaluating a strategy's real-world profitability. Use downloaded historical OHLCV replay when you want to study actual past candles.
- This lab sends no broker orders. Stop-loss and target crossings are warnings; positions are not automatically closed.

## Groww-style single-screen Scalper Desk

Open **Groww Style Scalper Desk** in the Streamlit page navigation for a compact, side-by-side practice layout:

- NIFTY spot candlestick chart with EMA 9/21, plus a CE/PE premium candlestick tab.
- Select a practice strike, CE or PE, quantity, candle formation duration (15–120 seconds), and refresh interval (1–5 seconds).
- Paper BUY and SELL/CLOSE ticket beside the chart, stop/target levels, open and realized net P&L, charges estimate, and downloadable trade journal.
- If synchronized historical files exist in `data/replay/`, the page replays the downloaded spot and option candles. Otherwise it uses explicitly labeled synthetic practice prices.
- **Historical strike limitation:** the downloader's CE/PE files represent the exact contract recorded in `manifest.csv`; changing the strike selector does not transform those historical prices into another strike. For strike-accurate historical replay, download that strike's own OHLCV first.
- Synthetic option premiums are illustrative only and do not model Greeks, volatility surface, expiry decay or bid/ask spread. The app sends no real orders.

After pulling, install dependencies and start Streamlit:

    python -m pip install -r requirements.txt
    python -m streamlit run app.py

Streamlit automatically lists the new desk page in the sidebar navigation.
