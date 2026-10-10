from __future__ import annotations

from datetime import datetime
import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

from live_market import extract_quote
from chain_utils import normalize_option_chain, summarize_chain, scalping_context
from paper_trading import pnl_for_long, close_long

load_dotenv()
st.set_page_config(page_title="NIFTY Scalper Practice", page_icon="📈", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: .8rem; max-width: 1800px}
[data-testid="stMetric"] {background:#111b26;border:1px solid #293b4d;padding:10px;border-radius:9px}
div.stButton > button {min-height: 2.7rem; font-weight: 600}
</style>
""", unsafe_allow_html=True)
st.title("NIFTY Scalper")
st.caption("PAPER TRADING ONLY · SIMULATED POSITIONS · NO BROKER ORDERS")
st.warning("No live broker feed is connected. Upload a current option-chain snapshot and/or NIFTY OHLCV CSV. Demo data is illustrative only and must never be used for trading.")

ALIASES = {
 "strike":["strike","strike price","strike_price","strikeprice"],
 "ce_ltp":["ce ltp","call ltp","call last price","ce last price","ce_ltp","call price"],
 "pe_ltp":["pe ltp","put ltp","put last price","pe last price","pe_ltp","put price"],
 "ce_oi":["ce oi","call oi","call open interest","ce open interest","ce_oi"],
 "pe_oi":["pe oi","put oi","put open interest","pe open interest","pe_oi"],
 "ce_change_oi":["ce change in oi","ce chg in oi","call change in oi","call chg in oi","ce_change_oi"],
 "pe_change_oi":["pe change in oi","pe chg in oi","put change in oi","put chg in oi","pe_change_oi"],
 "ce_volume":["ce volume","call volume","ce_volume"],
 "pe_volume":["pe volume","put volume","pe_volume"],
 "ce_iv":["ce iv","call iv","ce_iv"], "pe_iv":["pe iv","put iv","pe_iv"],
 "ce_delta":["ce delta","call delta","ce_delta"], "pe_delta":["pe delta","put delta","pe_delta"],
 "timestamp":["timestamp","time","datetime","date time","snapshot time"],
}

def demo_chain():
    strikes = list(range(24000, 25101, 50))
    rows = []
    for k in strikes:
        d = (k - 24550) / 50
        rows.append({"strike":k, "ce_ltp":round(max(1,220-d*8+abs(d)*1.2),2),
        "pe_ltp":round(max(1,215+d*8+abs(d)*1.2),2),
        "ce_oi":int(100000+max(0,d)*12000+(k%7)*1300),
        "pe_oi":int(90000+max(0,-d)*13500+(k%5)*1700),
        "ce_change_oi":int((d+2)*800), "pe_change_oi":int((-d+2)*750),
        "ce_volume":int(10000+max(0,5-abs(d))*2500),
        "pe_volume":int(9500+max(0,5-abs(d))*2600),
        "ce_iv":round(13+abs(d)*.35,2), "pe_iv":round(13.4+abs(d)*.34,2),
        "ce_delta":round(max(.05,min(.95,.5-d*.045)),3),
        "pe_delta":round(max(-.95,min(-.05,-.5-d*.045)),3)})
    return pd.DataFrame(rows)

with st.sidebar:
    st.header("Data & risk settings")
    st.subheader("Practice market movement")
    replay_enabled = st.toggle("Animate simulated market", value=True, help="Moves candles automatically for practice; no real quotes are used.")
    replay_speed = st.slider("Replay speed (seconds per candle)", min_value=1, max_value=5, value=1)
    replay_repeat = st.toggle("Loop replay when it reaches the end", value=True)
    replay_file = st.file_uploader("Optional historical option-contract OHLCV CSV", type=["csv"], help="For historical replay, upload candles for the exact option contract with timestamp, open, high, low, close, volume.")
    st.caption("Without a file, the app generates clearly labeled synthetic practice candles.")
    live_enabled = st.toggle("Enable Kotak Neo live quote polling", value=False, help="Fetches genuine broker quotes only when a valid consumer key is configured.")
    live_segment = st.selectbox("Live instrument segment", ["nse_cm", "nse_fo"], index=0, help="nse_cm for NIFTY index spot; nse_fo for a NIFTY option contract.")
    live_token = st.text_input("Live instrument token / index name", value="Nifty 50", help="Index example: Nifty 50. For options, enter the exact current pSymbol from the Kotak scrip master.")
    refresh_seconds = st.slider("Chart refresh interval (seconds)", min_value=3, max_value=15, value=5)
    live_timeframe = st.selectbox("Live candle timeframe", ["1-minute", "2-minute", "3-minute", "5-minute"], index=0)
    max_live_points = st.slider("Live chart history (points)", min_value=30, max_value=600, value=180, step=30)
    st.caption("Set NEO_CONSUMER_KEY in a local .env file. Never commit credentials.")
    chain_file = st.file_uploader("Option-chain CSV snapshot", type=["csv"])
    candles_file = st.file_uploader("Optional NIFTY OHLCV CSV", type=["csv"])
    spot = st.number_input("Observed NIFTY spot (₹)", min_value=0.0, value=0.0, step=50.0)
    lot_size = st.number_input("Contract quantity per lot", min_value=1, max_value=10000, value=65, step=1, help="Verify the current exchange contract specification; editable.")
    lots = st.number_input("Lots per paper trade", min_value=1, max_value=100, value=1, step=1)
    charge_per_order = st.number_input("Estimated charges per order (₹)", min_value=0.0, value=20.0, step=1.0, help="Approximation for practice; set to your chosen estimate.")
    max_loss = st.number_input("Practice daily loss limit (₹)", min_value=0.0, value=2000.0, step=100.0)
    st.caption("Paper mode only: no real orders are sent.")

if chain_file:
    try:
        chain = normalize_option_chain(pd.read_csv(chain_file), ALIASES)
        demo = False
        source = "UPLOADED SNAPSHOT"
    except Exception as exc:
        st.error(f"CSV validation failed: {exc}")
        st.stop()
else:
    chain = normalize_option_chain(demo_chain(), ALIASES)
    demo = True
    source = "ILLUSTRATIVE DEMO — NOT LIVE"

summary = summarize_chain(chain, spot=spot if spot > 0 else None)
ref_strike = summary["reference_strike"]
nearby = chain.loc[(chain["strike"]-ref_strike).abs() <= 500].copy()
if nearby.empty: nearby = chain.copy()
st.info(f"DATA: {source} · {len(chain)} strikes · reference strike {ref_strike:,.0f}" + (f" · timestamp {summary['timestamp']}" if summary["timestamp"] else " · no timestamp supplied"))
if demo: st.error("DEMO MODE: prices, OI and volume are invented. Paper orders are disabled until you upload a real snapshot.")

if "live_quote_history" not in st.session_state: st.session_state.live_quote_history = []
if "live_quote_error" not in st.session_state: st.session_state.live_quote_error = ""
if "live_quote_client" not in st.session_state: st.session_state.live_quote_client = None
if "live_quote_key" not in st.session_state: st.session_state.live_quote_key = None
current_live_key = (live_segment, live_token.strip())
if st.session_state.live_quote_key != current_live_key:
    st.session_state.live_quote_history = []
    st.session_state.live_quote_key = current_live_key

if live_enabled:
    consumer_key = os.getenv("NEO_CONSUMER_KEY", "").strip()
    if not consumer_key:
        st.session_state.live_quote_error = "NEO_CONSUMER_KEY is missing. Add it to your local .env file, restart Streamlit and enable live quotes again."
    elif not live_token.strip():
        st.session_state.live_quote_error = "Enter a current Kotak Neo instrument token or index name."
    else:
        st_autorefresh(interval=refresh_seconds * 1000, key="kotak_live_quote_refresh")
        try:
            if st.session_state.live_quote_client is None:
                from neo_api_client import NeoAPI
                st.session_state.live_quote_client = NeoAPI(consumer_key=consumer_key, environment="prod")
            quote_response = st.session_state.live_quote_client.quotes(
                instrument_tokens=[{"instrument_token": live_token.strip(), "exchange_segment": live_segment}],
                quote_type="ltp",
            )
            quote = extract_quote(quote_response, live_token.strip())
            quote["segment"] = live_segment
            quote["requested_instrument"] = live_token.strip()
            st.session_state.live_quote_history.append(quote)
            st.session_state.live_quote_history = st.session_state.live_quote_history[-max_live_points:]
            st.session_state.live_quote_error = ""
        except Exception as exc:
            st.session_state.live_quote_error = f"Kotak Neo quote request failed: {type(exc).__name__}: {exc}"
else:
    st.session_state.live_quote_error = ""

# Prepare a replay stream. Historical option OHLCV is preferred; otherwise use clearly synthetic practice candles.
def make_demo_replay(n=600):
    rng = __import__("numpy").random.default_rng(20261010)
    regimes = [0.10, -0.08, 0.02, -0.03, 0.12, -0.10]
    changes = []
    for i in range(n):
        drift = regimes[(i // 70) % len(regimes)]
        changes.append(drift + rng.normal(0, 1.25))
    close = 180 + __import__("numpy").cumsum(changes)
    close = __import__("numpy").maximum(close, 8)
    open_ = __import__("numpy").concatenate(([close[0] - changes[0]], close[:-1]))
    spread = rng.uniform(0.2, 2.2, size=n)
    high = __import__("numpy").maximum(open_, close) + spread
    low = __import__("numpy").maximum(0.05, __import__("numpy").minimum(open_, close) - spread * rng.uniform(0.7, 1.1, size=n))
    start = pd.Timestamp("2026-10-09 09:15:00")
    ts = pd.date_range(start=start, periods=n, freq="min")
    return pd.DataFrame({"timestamp":ts,"open":open_.round(2),"high":high.round(2),"low":low.round(2),"close":close.round(2),"volume":rng.integers(100,6000,size=n)})

replay_source = "SYNTHETIC PRACTICE DATA"
try:
    if replay_file is not None:
        replay_raw = pd.read_csv(replay_file)
        replay_cols = {str(c).strip().lower().replace(" ","_"):c for c in replay_raw.columns}
        needed = ["timestamp","open","high","low","close","volume"]
        missing = [c for c in needed if c not in replay_cols]
        if missing:
            st.sidebar.error("Replay CSV missing columns: " + ", ".join(missing))
            replay_candles = make_demo_replay()
        else:
            replay_candles = replay_raw.rename(columns={replay_cols[c]:c for c in needed})[needed].copy()
            replay_candles["timestamp"] = pd.to_datetime(replay_candles["timestamp"], errors="coerce")
            for c in ["open","high","low","close","volume"]:
                replay_candles[c] = pd.to_numeric(replay_candles[c], errors="coerce")
            replay_candles = replay_candles.dropna(subset=needed).sort_values("timestamp").reset_index(drop=True)
            if replay_candles.empty:
                raise ValueError("No valid OHLCV rows found")
            replay_source = "HISTORICAL OPTION OHLCV REPLAY"
    else:
        replay_candles = make_demo_replay()
except Exception as exc:
    st.sidebar.error(f"Replay CSV error: {exc}")
    replay_candles = make_demo_replay()

replay_fingerprint = f"{replay_source}:{len(replay_candles)}:{str(replay_candles.iloc[0]['timestamp'])}"
if st.session_state.get("replay_fingerprint") != replay_fingerprint:
    st.session_state.replay_fingerprint = replay_fingerprint
    st.session_state.replay_start_counter = 0
    st.session_state.replay_restart_requested = True
if "replay_restart_requested" not in st.session_state:
    st.session_state.replay_restart_requested = True
if replay_enabled:
    replay_counter = st_autorefresh(interval=replay_speed * 1000, key="practice_replay_refresh")
else:
    replay_counter = st.session_state.get("practice_replay_refresh", 0)
if st.session_state.replay_restart_requested:
    st.session_state.replay_start_counter = replay_counter
    st.session_state.replay_restart_requested = False
replay_index = max(0, int(replay_counter) - int(st.session_state.replay_start_counter))
if replay_repeat:
    replay_index = replay_index % len(replay_candles)
else:
    replay_index = min(replay_index, len(replay_candles)-1)
replay_visible = replay_candles.iloc[:replay_index+1].tail(120).copy()
replay_current_price = float(replay_candles.iloc[replay_index]["close"])
replay_is_historical = replay_source == "HISTORICAL OPTION OHLCV REPLAY"

if "paper_positions" not in st.session_state: st.session_state.paper_positions = []
if "paper_orders" not in st.session_state: st.session_state.paper_orders = []
if "paper_realized" not in st.session_state: st.session_state.paper_realized = 0.0
if "paper_session_date" not in st.session_state: st.session_state.paper_session_date = str(datetime.now().date())
if st.session_state.paper_session_date != str(datetime.now().date()):
    st.session_state.paper_session_date = str(datetime.now().date())
    st.session_state.paper_realized = 0.0

tabs = st.tabs(["Scalper terminal", "Positions & P&L", "Trade journal"])
with tabs[0]:
    st.subheader("Practice market chart")
    if replay_enabled:
        r1,r2,r3 = st.columns(3)
        r1.metric("Simulated / replay premium (₹)", f"{replay_current_price:,.2f}")
        r2.metric("Replay candle", f"{replay_index+1:,} / {len(replay_candles):,}")
        r3.metric("Replay source", "Historical CSV" if replay_is_historical else "Synthetic demo")
        replay_fig = go.Figure(data=[go.Candlestick(x=replay_visible["timestamp"],open=replay_visible["open"],high=replay_visible["high"],low=replay_visible["low"],close=replay_visible["close"],name="Practice premium")])
        replay_fig.update_layout(template="plotly_dark",height=430,xaxis_rangeslider_visible=False,xaxis_title="Replay time",yaxis_title="Option premium (₹)",margin=dict(l=10,r=10,t=20,b=10))
        st.plotly_chart(replay_fig,use_container_width=True)
        st.caption(f"{replay_source}. Candles advance every {replay_speed} second(s). Historical CSV replays past prices; synthetic mode is generated practice data, not market data.")
        if st.button("Restart practice replay"):
            st.session_state.replay_start_counter = replay_counter
            st.rerun()
    if live_enabled:
        if st.session_state.live_quote_error:
            st.error(st.session_state.live_quote_error)
            st.caption("No demo or third-party fallback is used. Check your Kotak Neo API access, exact instrument token and network, then retry.")
        elif st.session_state.live_quote_history:
            live_df = pd.DataFrame(st.session_state.live_quote_history)
            latest = live_df.iloc[-1]
            lc1, lc2, lc3 = st.columns(3)
            lc1.metric("Latest live LTP (₹)", f"{float(latest['price']):,.2f}")
            lc2.metric("Instrument", str(latest.get("symbol", live_token)))
            lc3.metric("Last quote time", str(latest["timestamp"]).split("T")[-1])
            live_df["timestamp"] = pd.to_datetime(live_df["timestamp"], errors="coerce")
            minutes = int(live_timeframe.split("-")[0])
            live_df = live_df.dropna(subset=["timestamp"]).sort_values("timestamp").set_index("timestamp")
            candle_groups = live_df["price"].resample(f"{minutes}min").ohlc().dropna().reset_index()
            live_fig = go.Figure(data=[go.Candlestick(x=candle_groups["timestamp"], open=candle_groups["open"], high=candle_groups["high"], low=candle_groups["low"], close=candle_groups["close"], name="Kotak Neo LTP")])
            live_fig.update_layout(template="plotly_dark", height=430, xaxis_title="Quote time", yaxis_title="Price (₹)", margin=dict(l=10,r=10,t=20,b=10), xaxis_rangeslider_visible=False)
            st.plotly_chart(live_fig, use_container_width=True)
            st.caption(f"Real broker LTP polled every {refresh_seconds}s · aggregated into {live_timeframe} candles from received quotes · {len(live_df)} samples retained in this session.")
        else:
            st.info("Waiting for the first Kotak Neo quote...")
    else:
        st.info("Practice replay is paused. Enable Animate simulated market in the sidebar to advance candles.")
    a,b,c,d = st.columns(4)
    a.metric("PCR (OI)", f"{summary['pcr_oi']:.2f}" if pd.notna(summary["pcr_oi"]) else "N/A")
    a2 = float(sum(p["net_unrealized"] for p in st.session_state.paper_positions))
    b.metric("Open positions", str(len(st.session_state.paper_positions)))
    c.metric("Realized net P&L", f"₹{st.session_state.paper_realized:,.2f}")
    d.metric("Open net P&L", f"₹{a2:,.2f}")
    chart_col, ticket_col = st.columns([1.55, 1])
    with chart_col:
        st.subheader("Option contract view")
        side = st.radio("Contract side", ["CE / Call", "PE / Put"], horizontal=True)
        strikes = nearby["strike"].astype(float).tolist()
        default_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i]-ref_strike))
        strike = st.selectbox("Strike", strikes, index=default_idx, format_func=lambda x: f"{x:,.0f}")
        price_col = "ce_ltp" if side.startswith("CE") else "pe_ltp"
        chosen = chain.loc[chain["strike"] == strike].iloc[-1]
        chain_ltp = chosen[price_col]
        current_ltp = float(chain_ltp) if pd.notna(chain_ltp) else 0.0
        # In practice replay mode, the selected contract follows the replayed option-premium candle.
        if replay_enabled:
            current_ltp = replay_current_price
        st.session_state["selected_replay_instrument"] = f"NIFTY {int(strike)} {'CE' if side.startswith('CE') else 'PE'}"
        st.session_state["selected_replay_price"] = current_ltp
        st.metric("Current practice premium (₹)", f"{current_ltp:,.2f}" if current_ltp > 0 else "Unavailable")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=nearby["strike"], y=nearby["ce_ltp"], name="CE premium"))
        fig.add_trace(go.Bar(x=nearby["strike"], y=nearby["pe_ltp"], name="PE premium"))
        fig.update_layout(template="plotly_dark", barmode="group", height=320, margin=dict(l=5,r=5,t=20,b=5), xaxis_title="Strike", yaxis_title="Premium (₹)", legend=dict(orientation="h",y=1.1))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("The upper chart is the moving practice contract chart. Upload matching historical option OHLCV for realistic replay; the built-in stream is synthetic.")
    with ticket_col:
        st.subheader("Quick paper order")
        instrument = f"NIFTY {int(strike)} {'CE' if side.startswith('CE') else 'PE'}"
        mark_default = current_ltp if current_ltp > 0 else 0.0
        order_price = st.number_input("Observed entry premium (₹)", min_value=0.0, value=float(mark_default), step=0.05, format="%.2f", help="Prefills from uploaded snapshot. Verify quote freshness before using.")
        qty = int(lots * lot_size)
        st.write(f"**Contract:** {instrument}")
        st.write(f"**Quantity:** {qty} units ({lots} lot(s) × {lot_size})")
        st.write(f"**Entry notional:** ₹{order_price*qty:,.2f}")
        st.write(f"**Estimated entry charges:** ₹{charge_per_order:,.2f}")
        if st.button("BUY · Open paper position", type="primary", use_container_width=True, disabled=order_price <= 0):
            if max_loss > 0 and st.session_state.paper_realized <= -max_loss:
                st.error("Daily practice loss limit reached. New entries blocked.")
            else:
                pos = {"id":len(st.session_state.paper_orders)+1,"instrument":instrument,"side":"LONG","strike":float(strike),"option_side":"CE" if side.startswith("CE") else "PE","quantity":qty,"lots":int(lots),"entry":float(order_price),"mark":float(order_price),"entry_charge":float(charge_per_order),"entry_time":datetime.now().isoformat(timespec="seconds"),"gross_unrealized":0.0,"net_unrealized":-float(charge_per_order)}
                st.session_state.paper_positions.append(pos)
                st.session_state.paper_orders.append({"time":pos["entry_time"],"action":"PAPER BUY","instrument":instrument,"quantity":qty,"price":float(order_price),"gross_pnl":0.0,"charges":float(charge_per_order),"net_pnl":-float(charge_per_order),"status":"OPEN"})
                st.success("Paper position opened at the current practice price. No real order was sent.")
        st.divider()
        st.subheader("Current snapshot context")
        context = scalping_context(chain, spot=spot if spot > 0 else None, is_demo=demo)
        st.metric("Descriptive flow", context["bias"])
        st.write(context["explanation"])
        if st.button("Clear all paper positions & journal", use_container_width=True):
            st.session_state.paper_positions = []
            st.session_state.paper_orders = []
            st.session_state.paper_realized = 0.0
            st.rerun()

    if candles_file:
        try:
            raw = pd.read_csv(candles_file)
            cols = {str(c).strip().lower():c for c in raw.columns}
            required = ["timestamp","open","high","low","close","volume"]
            missing = [x for x in required if x not in cols]
            if missing: st.error("OHLCV CSV missing: " + ", ".join(missing))
            else:
                candles = raw.rename(columns={cols[x]:x for x in required}).copy()
                candles["timestamp"] = pd.to_datetime(candles["timestamp"], errors="coerce")
                for col in ["open","high","low","close","volume"]: candles[col] = pd.to_numeric(candles[col], errors="coerce")
                candles = candles.dropna(subset=required).sort_values("timestamp")
                if len(candles) >= 2:
                    candles["ema9"] = candles["close"].ewm(span=9,adjust=False).mean()
                    candles["ema21"] = candles["close"].ewm(span=21,adjust=False).mean()
                    cf = go.Figure(data=[go.Candlestick(x=candles["timestamp"],open=candles["open"],high=candles["high"],low=candles["low"],close=candles["close"],name="NIFTY spot")])
                    cf.add_trace(go.Scatter(x=candles["timestamp"],y=candles["ema9"],name="EMA 9"))
                    cf.add_trace(go.Scatter(x=candles["timestamp"],y=candles["ema21"],name="EMA 21"))
                    cf.update_layout(template="plotly_dark",height=430,xaxis_rangeslider_visible=False,margin=dict(l=5,r=5,t=20,b=5))
                    st.subheader("NIFTY underlying chart")
                    st.plotly_chart(cf,use_container_width=True)
                    last = candles.iloc[-1]
                    trend = "UP" if last["close"] > last["ema9"] > last["ema21"] else "DOWN" if last["close"] < last["ema9"] < last["ema21"] else "MIXED"
                    st.caption(f"Uploaded candle trend context: {trend} · last close {last['close']:,.2f} · not live")
                else: st.warning("Upload at least two valid OHLCV rows.")
        except Exception as exc: st.error(f"Could not parse OHLCV file: {exc}")

with tabs[1]:
    st.subheader("Open positions")
    if st.session_state.paper_positions:
        for pos in list(st.session_state.paper_positions):
            chain_side = "ce_ltp" if pos["option_side"] == "CE" else "pe_ltp"
            found = chain.loc[chain["strike"] == pos["strike"]]
            observed = found.iloc[-1][chain_side] if not found.empty else float("nan")
            if replay_enabled and pos["instrument"] == st.session_state.get("selected_replay_instrument"):
                pos["mark"] = float(st.session_state.get("selected_replay_price", pos["mark"]))
            elif not demo and pd.notna(observed) and float(observed) > 0:
                pos["mark"] = float(observed)
            pos["gross_unrealized"] = pnl_for_long(pos["entry"], pos["mark"], pos["quantity"])
            pos["net_unrealized"] = pos["gross_unrealized"] - pos["entry_charge"] - float(charge_per_order)
        st.dataframe(pd.DataFrame(st.session_state.paper_positions)[["id","instrument","quantity","entry","mark","gross_unrealized","net_unrealized","entry_time"]], use_container_width=True, hide_index=True)
        close_ids = [p["id"] for p in st.session_state.paper_positions]
        selected_id = st.selectbox("Position to close", close_ids, format_func=lambda x: next((p["instrument"] for p in st.session_state.paper_positions if p["id"]==x), str(x)))
        selected_pos = next(p for p in st.session_state.paper_positions if p["id"] == selected_id)
        close_price = st.number_input("Observed exit premium (₹)", min_value=0.0, value=float(selected_pos["mark"]), step=0.05, format="%.2f")
        if st.button("SELL · Close selected paper position", type="primary", disabled=close_price <= 0):
            result = close_long(selected_pos["entry"],float(close_price),selected_pos["quantity"],selected_pos["entry_charge"],float(charge_per_order))
            now = datetime.now().isoformat(timespec="seconds")
            st.session_state.paper_realized += result["net_pnl"]
            st.session_state.paper_orders.append({"time":now,"action":"PAPER SELL / CLOSE","instrument":selected_pos["instrument"],"quantity":selected_pos["quantity"],"price":float(close_price),"gross_pnl":result["gross_pnl"],"charges":result["charges"],"net_pnl":result["net_pnl"],"status":"CLOSED"})
            st.session_state.paper_positions = [p for p in st.session_state.paper_positions if p["id"] != selected_id]
            st.success(f"Position closed in simulation. Net realized P&L: ₹{result['net_pnl']:,.2f}")
            st.rerun()
    else:
        st.info("No open paper positions. Open one from the Scalper terminal using an uploaded option-chain snapshot.")
    st.subheader("P&L overview")
    open_net = sum(p.get("net_unrealized",0.0) for p in st.session_state.paper_positions)
    gross_realized = sum(float(o.get("gross_pnl",0)) for o in st.session_state.paper_orders if o["status"]=="CLOSED")
    charges_total = sum(float(o.get("charges",0)) for o in st.session_state.paper_orders)
    x1,x2,x3,x4 = st.columns(4)
    x1.metric("Realized net",f"₹{st.session_state.paper_realized:,.2f}")
    x2.metric("Unrealized net",f"₹{open_net:,.2f}")
    x3.metric("Gross realized",f"₹{gross_realized:,.2f}")
    x4.metric("Recorded charges",f"₹{charges_total:,.2f}")
    closed = [o for o in st.session_state.paper_orders if o["status"]=="CLOSED"]
    if closed:
        curve = pd.DataFrame(closed)
        curve["cumulative_net"] = curve["net_pnl"].cumsum()
        pf = go.Figure(go.Scatter(x=list(range(1,len(curve)+1)),y=curve["cumulative_net"],mode="lines+markers",name="Cumulative net P&L"))
        pf.update_layout(template="plotly_dark",height=300,xaxis_title="Closed trade #",yaxis_title="Cumulative net P&L (₹)",margin=dict(l=5,r=5,t=20,b=5))
        st.plotly_chart(pf,use_container_width=True)
    st.caption("Net P&L subtracts the configured estimated charge for each entry and exit. Taxes, exchange levies, slippage, spread and fill uncertainty are not fully modeled.")

with tabs[2]:
    st.subheader("Order and trade journal")
    if st.session_state.paper_orders:
        orders = pd.DataFrame(st.session_state.paper_orders)
        st.dataframe(orders,use_container_width=True,hide_index=True)
        st.download_button("Download paper journal CSV",orders.to_csv(index=False).encode("utf-8"),"nifty_paper_journal.csv","text/csv")
    else: st.info("No simulated orders recorded yet.")
    st.caption("Paper positions and journal live in Streamlit session state; download the CSV to keep a copy. They are not saved to a database.")

st.divider()
st.caption("Practice tool only. Prices from uploaded files may be stale or incomplete. Demo trading is disabled. Verify contract expiry, lot size, quote time, spread and all charges independently.")
