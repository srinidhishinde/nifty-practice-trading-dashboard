from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time

import pandas as pd
from dotenv import load_dotenv
from neo_api_client import NeoAPI

OUT = Path("data/replay")

def unwrap(response):
    if isinstance(response, dict):
        return response.get("data", response)
    return response

def candles_frame(response):
    payload = unwrap(response)
    rows = payload.get("candles", []) if isinstance(payload, dict) else []
    if not rows:
        raise RuntimeError(f"No candles returned: {str(response)[:500]}")
    normalized = []
    for row in rows:
        if isinstance(row, dict):
            normalized.append({k: row.get(k) for k in ("timestamp", "open", "high", "low", "close", "volume")})
        elif isinstance(row, (list, tuple)) and len(row) >= 6:
            normalized.append(dict(zip(("timestamp", "open", "high", "low", "close", "volume"), row[:6])))
    df = pd.DataFrame(normalized)
    if df.empty:
        raise RuntimeError("Kotak returned no recognized candle rows.")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["timestamp", "open", "high", "low", "close"]).sort_values("timestamp").drop_duplicates("timestamp")

def chain_contracts(response):
    data = unwrap(response)
    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected option-chain response: {str(response)[:500]}")
    calls, puts = data.get("call", []), data.get("put", [])
    contracts = []
    for side, items in (("CE", calls), ("PE", puts)):
        for item in items or []:
            inst = item.get("instrument", {})
            quote = item.get("quote", {})
            try:
                strike = float(inst.get("strikePrice"))
                ltp = float(quote.get("ltp") or 0)
                neosymbol = str(inst.get("neoSymbol") or "")
                symbol = str(inst.get("symbol") or "")
                token = neosymbol.split("|", 1)[1]
                if neosymbol.startswith("nse_fo|") and ltp > 0:
                    contracts.append({"side": side, "strike": strike, "ltp": ltp, "neosymbol": neosymbol, "token": token, "symbol": symbol})
            except (TypeError, ValueError, IndexError):
                continue
    if not contracts:
        raise RuntimeError("Kotak option-chain response had no usable active CE/PE contracts.")
    return contracts

def fetch_history(client, neosymbol, start, end, interval):
    # Broker limits 1/3/5-minute history to 30 days per request.
    response = client.historical_data(neosymbol=neosymbol, interval=interval, from_date=start, to_date=end)
    return candles_frame(response)

def main():
    parser = argparse.ArgumentParser(description="Download NIFTY spot and active near-ATM CE/PE historical candles from Kotak Neo.")
    parser.add_argument("--start", required=True, help="YYYY-MM-DD; for 1/3/5 minute candles use a range no longer than 30 days.")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--interval", choices=["1min", "3min", "5min", "10min", "15min"], default="1min")
    parser.add_argument("--count", type=int, default=40, help="Number of strikes to request on each side; must be a multiple of 10.")
    args = parser.parse_args()
    if args.count < 10 or args.count % 10:
        parser.error("--count must be a positive multiple of 10 (10, 20, 30, 40...).")
    if pd.Timestamp(args.end) < pd.Timestamp(args.start):
        parser.error("--end must be on or after --start.")
    if args.interval in {"1min", "3min", "5min"} and (pd.Timestamp(args.end) - pd.Timestamp(args.start)).days > 30:
        parser.error("For 1/3/5-minute candles, keep the range within 30 days.")
    load_dotenv()
    key = os.getenv("NEO_CONSUMER_KEY", "").strip()
    if not key:
        sys.exit("NEO_CONSUMER_KEY is missing. Add your private Kotak Neo Trade API token to local .env.")
    client = NeoAPI(consumer_key=key, environment="prod")
    OUT.mkdir(parents=True, exist_ok=True)

    print("Fetching NIFTY option chain from Kotak Neo...")
    chain_response = client.option_chain(exchange="nse_fo", underlying="NIFTY", instrument_type="option", count=args.count)
    contracts = chain_contracts(chain_response)

    # Prefer broker's NIFTY 50 index quote; do not invent spot values.
    spot = None
    spot_errors = []
    for token in ("Nifty 50", "26000"):
        try:
            quotes = client.quotes(instrument_tokens=[{"instrument_token": token, "exchange_segment": "nse_cm"}], quote_type="ltp")
            quote_rows = quotes if isinstance(quotes, list) else quotes.get("data", []) if isinstance(quotes, dict) else []
            for row in quote_rows:
                if isinstance(row, dict):
                    raw = row.get("ltp", row.get("last_traded_price"))
                    if raw is not None and float(raw) > 0:
                        spot = float(raw)
                        break
            if spot:
                break
        except Exception as exc:
            spot_errors.append(f"{token}: {exc}")
    if not spot:
        # Current option chain marks its ATM contract; use that only as a strike-selection reference.
        atm = next((x for x in contracts if str((next((it.get("instrument", {}).get("moneyness") for it in (unwrap(chain_response).get("call", []) + unwrap(chain_response).get("put", [])) if it.get("instrument", {}).get("neoSymbol") == x["neosymbol"]), "")) == "ATM"), None)
        if atm:
            spot = atm["strike"]
            print("Warning: index quote unavailable; selecting CE/PE at broker-marked ATM strike, not claiming a spot quote.")
        else:
            sys.exit("Unable to retrieve NIFTY spot or ATM marker. No data downloaded. Quote errors: " + " | ".join(spot_errors))

    strikes = sorted({c["strike"] for c in contracts})
    atm_strike = min(strikes, key=lambda x: abs(x - spot))
    ce_pool = [c for c in contracts if c["side"] == "CE"]
    pe_pool = [c for c in contracts if c["side"] == "PE"]
    ce = min(ce_pool, key=lambda x: abs(x["strike"] - atm_strike))
    pe = min(pe_pool, key=lambda x: abs(x["strike"] - atm_strike))
    selected = [("nifty_spot", "nse_cm|Nifty 50", "NIFTY 50 INDEX"), ("nifty_ce", ce["neosymbol"], ce["symbol"]), ("nifty_pe", pe["neosymbol"], pe["symbol"])]
    print(f"Spot reference: {spot:.2f}; selected strike: {atm_strike:g}; CE: {ce['symbol']} @ snapshot {ce['ltp']:.2f}; PE: {pe['symbol']} @ snapshot {pe['ltp']:.2f}")
    manifest = []
    for name, neo_symbol, label in selected:
        print(f"Downloading {label} ({neo_symbol})...")
        try:
            df = fetch_history(client, neo_symbol, args.start, args.end, args.interval)
            path = OUT / f"{name}.csv"
            df.to_csv(path, index=False)
            print(f"  Saved {len(df)} candles -> {path}")
            manifest.append({"dataset": name, "symbol": label, "neosymbol": neo_symbol, "interval": args.interval, "start": args.start, "end": args.end, "rows": len(df), "file": str(path)})
        except Exception as exc:
            print(f"  FAILED: {type(exc).__name__}: {exc}")
        time.sleep(1.0)  # gentle pacing to reduce rate-limit risk
    if not manifest:
        sys.exit("No datasets were downloaded. Check API access, active contract availability, and date range.")
    pd.DataFrame(manifest).to_csv(OUT / "manifest.csv", index=False)
    print(f"\nFinished. Manifest: {OUT / 'manifest.csv'}")
    print("Note: Kotak may not return expired contracts. Files contain only candles the broker actually returned.")

if __name__ == "__main__":
    main()
