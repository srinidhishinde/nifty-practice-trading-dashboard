from __future__ import annotations

from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chain_utils import normalize_option_chain, summarize_chain, scalping_context
from paper_trading import pnl_for_long, close_long

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
    chain_file = st.file_uploader("Option-chain CSV snapshot", type=["csv"])
    candles_file = st.file_uploader("Optional NIFTY OHLCV CSV", type=["csv"])
    spot = st.number_input("Observed NIFTY spot (₹)", min_value=0.0, value=0.0, step=50.0)
    lot_size = st.number_input("Contract quantity per lot", min_value=1, max_value=10000, value=65, step=1, help="Verify the current exchange contract specification; editable.")
    lots = st.number_input("Lots per paper trade", min_value=1, max_value=100, value=1, step=1)
    charge_per_order = st.number_input("Estimated charges per order (₹)", min_value=0.0, value=20.0, step=1.0, help="Approximation for practice; set to your chosen estimate.")
    max_loss = st.number_input("Practice daily loss limit (₹)", min_value=0.0, value=2000.0, step=100.0)
    st.caption("The app does not authenticate with Kotak Neo and cannot place live orders.")

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

if "paper_positions" not in st.session_state: st.session_state.paper_positions = []
if "paper_orders" not in st.session_state: st.session_state.paper_orders = []
if "paper_realized" not in st.session_state: st.session_state.paper_realized = 0.0
if "paper_session_date" not in st.session_state: st.session_state.paper_session_date = str(datetime.now().date())
if st.session_state.paper_session_date != str(datetime.now().date()):
    st.session_state.paper_session_date = str(datetime.now().date())
    st.session_state.paper_realized = 0.0

tabs = st.tabs(["Scalper terminal", "Positions & P&L", "Trade journal"])
with tabs[0]:
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
        st.metric("Snapshot option LTP (₹)", f"{current_ltp:,.2f}" if current_ltp > 0 else "Unavailable")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=nearby["strike"], y=nearby["ce_ltp"], name="CE premium"))
        fig.add_trace(go.Bar(x=nearby["strike"], y=nearby["pe_ltp"], name="PE premium"))
        fig.update_layout(template="plotly_dark", barmode="group", height=320, margin=dict(l=5,r=5,t=20,b=5), xaxis_title="Strike", yaxis_title="Premium (₹)", legend=dict(orientation="h",y=1.1))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("This is a strike-wise snapshot chart, not a time-series contract candle chart. Repeated timestamped snapshots or contract OHLCV are required for that.")
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
        if st.button("BUY · Open paper position", type="primary", use_container_width=True, disabled=demo or order_price <= 0):
            if max_loss > 0 and st.session_state.paper_realized <= -max_loss:
                st.error("Daily practice loss limit reached. New entries blocked.")
            else:
                pos = {"id":len(st.session_state.paper_orders)+1,"instrument":instrument,"side":"LONG","strike":float(strike),"option_side":"CE" if side.startswith("CE") else "PE","quantity":qty,"lots":int(lots),"entry":float(order_price),"mark":float(order_price),"entry_charge":float(charge_per_order),"entry_time":datetime.now().isoformat(timespec="seconds"),"gross_unrealized":0.0,"net_unrealized":-float(charge_per_order)}
                st.session_state.paper_positions.append(pos)
                st.session_state.paper_orders.append({"time":pos["entry_time"],"action":"PAPER BUY","instrument":instrument,"quantity":qty,"price":float(order_price),"gross_pnl":0.0,"charges":float(charge_per_order),"net_pnl":-float(charge_per_order),"status":"OPEN"})
                st.success("Paper position opened. No real order was sent.")
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
            if not demo and pd.notna(observed) and float(observed) > 0:
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
