from __future__ import annotations

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_candle_chart(frame, title, height=530, candle_seconds=15, volatility=1.0, scenario="Mixed market"):
    """Render the same Python-owned OHLC values used by the paper ticket."""
    records = frame.tail(100).copy()
    fig = go.Figure(go.Candlestick(
        x=records["timestamp"],
        open=records["open"],
        high=records["high"],
        low=records["low"],
        close=records["close"],
        name=title,
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
    ))
    if len(records) >= 9:
        fig.add_trace(go.Scatter(
            x=records["timestamp"],
            y=records["close"].ewm(span=9, adjust=False).mean(),
            name="EMA 9",
            line=dict(width=1.2),
        ))
    if len(records) >= 21:
        fig.add_trace(go.Scatter(
            x=records["timestamp"],
            y=records["close"].ewm(span=21, adjust=False).mean(),
            name="EMA 21",
            line=dict(width=1.2),
        ))
    fig.update_layout(
        template="plotly_dark",
        height=height,
        xaxis_rangeslider_visible=False,
        yaxis_title="Index points" if "SPOT" in title else "Premium (₹)",
        margin=dict(l=8, r=8, t=25, b=8),
        legend=dict(orientation="h", y=1.02),
        uirevision=title,
    )
    st.plotly_chart(fig, use_container_width=True, key="live_" + "".join(ch.lower() if ch.isalnum() else "_" for ch in title))


try:
    from replay_data import load_synchronized_replay
except Exception:
    load_synchronized_replay = None

st.set_page_config(page_title="NIFTY Scalper Desk", page_icon="📈", layout="wide")

@st.fragment(run_every=1)
def render_dashboard():
    st.markdown("""
    <style>
    .block-container {max-width: 1900px; padding-top: .65rem; padding-bottom: 1rem}
    [data-testid="stMetric"] {background:#101a25;border:1px solid #2a3b4c;padding:10px 12px;border-radius:10px}
    [data-testid="stMetricLabel"] {font-size:.82rem}
    div.stButton > button {min-height:2.65rem;font-weight:650}
    div[data-testid="stDataFrame"] {border:1px solid #263748;border-radius:8px}
    </style>
    """, unsafe_allow_html=True)

    st.title("NIFTY Scalper Desk")
    st.caption("Groww-inspired practice layout · PAPER ORDERS ONLY · NO BROKER ORDERS")
    st.warning("Data mode is shown explicitly below. Synthetic prices are for learning candle behaviour only; they are not live NIFTY/option quotes or a trading signal.")

    # ---------- Controls ----------
    control_cols = st.columns([1.1, 1, 1, 1, 1.2, 1.2, 1.35])
    with control_cols[0]:
        timeframe = st.selectbox("Candle timeframe", ["1 min", "2 min", "3 min", "5 min"], index=2)
    with control_cols[1]:
        option_side = st.radio("Contract", ["CE", "PE"], horizontal=True, key="desk_side")
    with control_cols[2]:
        strike = st.selectbox("Practice strike", list(range(22000, 27001, 50)), index=(25000-22000)//50, key="desk_strike_selector")
    with control_cols[3]:
        quantity = st.number_input("Quantity", min_value=1, max_value=10000, value=65, step=1)
    with control_cols[4]:
        seconds_per_candle = st.select_slider("Seconds per candle", options=[15, 20, 30, 45, 60, 90, 120], value=15)
    with control_cols[5]:
        refresh_seconds = st.select_slider("Candle movement refresh", options=[1, 2, 3, 4, 5], value=1)
    with control_cols[6]:
        scenario = st.selectbox("Price behaviour", ["Mixed market", "Uptrend with pullbacks", "Downtrend with bounces", "Range / choppy", "Breakout then retest"], index=0)

    ticks_per_candle = max(1, round(seconds_per_candle / refresh_seconds))
    run_sim = st.toggle("Animate chart", value=True)
    if st.button("Restart practice session", type="secondary"):
        for k in ["desk_bars", "desk_tick", "desk_premium", "desk_option_bars", "desk_contract_key", "desk_position", "desk_journal", "desk_realized", "desk_rng", "desk_replay_index"]:
            st.session_state.pop(k, None)
        st.rerun()

    # ---------- Data: synchronized local historical replay when present, synthetic otherwise ----------
    historical = None
    historical_strike = None
    if load_synchronized_replay:
        try:
            historical, historical_strike = load_synchronized_replay()
        except Exception as exc:
            st.caption(f"Historical replay could not be loaded: {exc}")

    if historical is not None and len(historical) > 1:
        data_mode = "KOTAK HISTORICAL REPLAY"
        if "desk_replay_index" not in st.session_state:
            st.session_state.desk_replay_index = 0
        if run_sim:
                st.session_state.desk_replay_index = (int(st.session_state.desk_replay_index) + 1) % len(historical)
        visible_idx = int(st.session_state.desk_replay_index)
        visible_hist = historical.iloc[:visible_idx + 1].tail(180).copy()
        spot_now = float(historical.iloc[visible_idx]["spot_close"])
        premium_col = f"{option_side.lower()}_close"
        premium_now = float(historical.iloc[visible_idx][premium_col])
        spot_candles = visible_hist[["timestamp", "spot_open", "spot_high", "spot_low", "spot_close", "spot_volume"]].rename(columns={"spot_open":"open","spot_high":"high","spot_low":"low","spot_close":"close","spot_volume":"volume"})
        contract_prefix = option_side.lower()
        option_candles = visible_hist[["timestamp", f"{contract_prefix}_open", f"{contract_prefix}_high", f"{contract_prefix}_low", f"{contract_prefix}_close", f"{contract_prefix}_volume"]].rename(columns={f"{contract_prefix}_open":"open",f"{contract_prefix}_high":"high",f"{contract_prefix}_low":"low",f"{contract_prefix}_close":"close",f"{contract_prefix}_volume":"volume"})
        if historical_strike is not None:
            data_note = f"Loaded local Kotak historical files; CE/PE contract strike from manifest: {historical_strike:g}. Selected UI strike {strike} is a label only for this downloaded pair."
        else:
            data_note = "Loaded local synchronized historical spot/CE/PE files."
    else:
        data_mode = "SYNTHETIC PRACTICE DATA"
        data_note = "No synchronized local history found in data/replay/. The charts and premiums below are synthetic, not real prices."
        if "desk_rng" not in st.session_state:
            st.session_state.desk_rng = np.random.default_rng(20261010)
        if "desk_bars" not in st.session_state:
            rng0 = st.session_state.desk_rng
            n = 120
            changes = rng0.normal(0, 8, n) + np.sin(np.arange(n)/11)*1.5
            close = 25000 + np.cumsum(changes)
            open_ = np.r_[close[0] - changes[0], close[:-1]]
            wick = rng0.uniform(1, 12, n)
            now = datetime.now().replace(microsecond=0)
            st.session_state.desk_bars = [{"timestamp": now-timedelta(minutes=(n-i)*int(timeframe.split()[0])), "open":float(o),"high":float(max(o,c)+w),"low":float(max(1,min(o,c)-w)),"close":float(c),"volume":int(rng0.integers(1000,30000))} for i,(o,c,w) in enumerate(zip(open_,close,wick))]
            st.session_state.desk_tick = 0
            st.session_state.desk_premium = 180.0
        bars = st.session_state.desk_bars
        tick = int(st.session_state.desk_tick)
        rng = st.session_state.desk_rng
        previous = float(bars[-1]["close"])
        tick_in_bar = tick % ticks_per_candle
        if run_sim and tick > 0 and tick_in_bar == 0:
            ts = bars[-1]["timestamp"] + timedelta(seconds=seconds_per_candle)
            bars.append({"timestamp":ts,"open":previous,"high":previous,"low":previous,"close":previous,"volume":0})
        active = bars[-1]
        # A small index-point move per refresh keeps the forming candle calm and readable.
        drift = 0.55 * np.sin((tick // ticks_per_candle) / 7)
        scenario_tick = tick // ticks_per_candle
        if scenario == "Uptrend with pullbacks":
            scenario_drift = 1.0 if (scenario_tick % 9) < 6 else -0.8
        elif scenario == "Downtrend with bounces":
            scenario_drift = -1.0 if (scenario_tick % 9) < 6 else 0.8
        elif scenario == "Range / choppy":
            scenario_drift = 0.7 * np.sin(scenario_tick / 2.5)
        elif scenario == "Breakout then retest":
            phase = scenario_tick % 24
            scenario_drift = 1.5 if phase < 10 else (-1.0 if phase < 17 else 0.25)
        else:
            scenario_drift = drift
        move = (scenario_drift / ticks_per_candle + float(rng.normal(0, 1.8 / np.sqrt(ticks_per_candle)))) if run_sim else 0.0
        spot_now = max(1000.0, float(active["close"]) + move)
        active["close"] = spot_now
        active["high"] = max(float(active["high"]), spot_now)
        active["low"] = min(float(active["low"]), spot_now)
        active["volume"] += int(rng.integers(100, 900))
        if run_sim:
            st.session_state.desk_tick = tick + 1
        st.session_state.desk_bars = bars[-300:]
        spot_candles = pd.DataFrame(st.session_state.desk_bars[-180:])
        # Synthetic option price is deliberately illustrative, not a pricing model.
        contract_key = f"{int(strike)}_{option_side}"
        if st.session_state.get("desk_contract_key") != contract_key or "desk_premium" not in st.session_state:
            # Illustrative strike-distance baseline only; this is not an option pricing model.
            st.session_state.desk_premium = max(15.0, 180.0 - abs(int(strike) - 25000) * 0.22)
            st.session_state.desk_contract_key = contract_key
            st.session_state.desk_option_bars = []
        premium_move = move * (0.32 if option_side == "CE" else -0.32) + (float(rng.normal(0, 0.55)) if run_sim else 0.0)
        st.session_state.desk_premium = max(0.05, float(st.session_state.desk_premium) + premium_move)
        premium_now = float(st.session_state.desk_premium)
        if "desk_option_bars" not in st.session_state:
            st.session_state.desk_option_bars = []
        opt_bars = st.session_state.desk_option_bars
        if not opt_bars or (run_sim and tick_in_bar == 0):
            opt_bars.append({"timestamp": active["timestamp"], "open":premium_now,"high":premium_now,"low":premium_now,"close":premium_now,"volume":0})
        opt = opt_bars[-1]
        opt["close"] = premium_now
        opt["high"] = max(float(opt["high"]), premium_now)
        opt["low"] = min(float(opt["low"]), premium_now)
        opt["volume"] += int(rng.integers(10, 400))
        st.session_state.desk_option_bars = opt_bars[-180:]
        option_candles = pd.DataFrame(st.session_state.desk_option_bars)

    st.markdown(f"**DATA MODE: {data_mode}**  ·  {data_note}")
    if data_mode == "SYNTHETIC PRACTICE DATA":
        st.caption(f"Active candle update {((int(st.session_state.get('desk_tick', 1))-1) % ticks_per_candle)+1}/{ticks_per_candle}; approximately {seconds_per_candle} seconds per candle.")
    else:
        st.caption("Historical candles are being revealed in sequence at the selected replay pace; this is replay, not live market data.")

    # ---------- Session state ----------
    for key, default in [("desk_position", None), ("desk_journal", []), ("desk_realized", 0.0)]:
        if key not in st.session_state:
            st.session_state[key] = default

    # In this educational ticket, only one long paper position can be open at a time.
    position = st.session_state.desk_position
    if position:
        position["mark"] = premium_now
        position["unrealized"] = (premium_now - position["entry"]) * position["quantity"] - position["entry_charge"] - position["exit_charge_estimate"]

    # ---------- Main single-screen workspace ----------
    left, right = st.columns([2.25, 1], gap="large")
    with left:
        m1, m2, m3 = st.columns(3)
        m1.metric("NIFTY spot (index points)", f"{spot_now:,.2f}")
        m2.metric(f"NIFTY {int(strike):,} {option_side} premium", f"₹{premium_now:,.2f}")
        m3.metric("Selected contract", f"{int(strike):,} {option_side}", "Practice only")
        tab_spot, tab_contract = st.tabs(["NIFTY SPOT", f"{option_side} PREMIUM"])
        with tab_spot:
            f = go.Figure(go.Candlestick(x=spot_candles["timestamp"],open=spot_candles["open"],high=spot_candles["high"],low=spot_candles["low"],close=spot_candles["close"],name="NIFTY spot"))
            if len(spot_candles) >= 9:
                f.add_trace(go.Scatter(x=spot_candles["timestamp"],y=spot_candles["close"].ewm(span=9,adjust=False).mean(),name="EMA 9"))
            if len(spot_candles) >= 21:
                f.add_trace(go.Scatter(x=spot_candles["timestamp"],y=spot_candles["close"].ewm(span=21,adjust=False).mean(),name="EMA 21"))
            f.update_layout(template="plotly_dark",height=530,xaxis_rangeslider_visible=False,yaxis_title="Index points",margin=dict(l=8,r=8,t=15,b=8),legend=dict(orientation="h",y=1.02),uirevision="desk-spot")
            render_candle_chart(spot_candles, "NIFTY SPOT", 530, seconds_per_candle, 0.0, scenario)
        with tab_contract:
            f2 = go.Figure(go.Candlestick(x=option_candles["timestamp"],open=option_candles["open"],high=option_candles["high"],low=option_candles["low"],close=option_candles["close"],name=f"{strike} {option_side}"))
            f2.add_hline(y=premium_now,line_dash="dot",annotation_text="Current / replay premium")
            if position:
                f2.add_hline(y=position["entry"],line_dash="dash",annotation_text="Entry")
                f2.add_hline(y=position["stop"],line_dash="dot",annotation_text="Stop")
                f2.add_hline(y=position["target"],line_dash="dot",annotation_text="Target")
            f2.update_layout(template="plotly_dark",height=530,xaxis_rangeslider_visible=False,yaxis_title="Illustrative / replay premium (₹)",margin=dict(l=8,r=8,t=15,b=8),uirevision=f"desk-contract-{option_side}")
            render_candle_chart(option_candles, f"{strike} {option_side} PREMIUM", 530, seconds_per_candle, 0.0, scenario)
        with st.expander("Practice option chain", expanded=False):
            strikes = list(range(max(22000, int(strike)-500), min(27000, int(strike)+500)+1, 50))
            rows = []
            for k in strikes:
                distance = (k-int(strike))/50
                ce = max(0.05, premium_now - distance*4.5)
                pe = max(0.05, premium_now + distance*4.5)
                rows.append({"CE LTP (illustrative)":round(ce,2),"Strike":int(k),"PE LTP (illustrative)":round(pe,2),"Selected": "◀" if int(k)==int(strike) else ""})
            st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
            st.markdown("**Jump to a strike**")
            chain_cols = st.columns([2, 1, 1])
            with chain_cols[0]:
                chain_pick = st.selectbox("Choose strike from chain", strikes, index=strikes.index(int(strike)), key="desk_chain_pick")
            with chain_cols[1]:
                if st.button("Use CE", use_container_width=True):
                    st.session_state["desk_side"] = "CE"
                    st.session_state["desk_strike_selector"] = int(chain_pick)
                    st.rerun()
            with chain_cols[2]:
                if st.button("Use PE", use_container_width=True):
                    st.session_state["desk_side"] = "PE"
                    st.session_state["desk_strike_selector"] = int(chain_pick)
                    st.rerun()
            st.caption("Illustrative chain only. Strike selection updates the practice ticket; these premiums are not live exchange quotes.")

    with right:
        st.subheader("Paper order ticket")
        st.caption("Long CE/PE practice · no broker orders")
        entry_default = round(float(premium_now), 2)
        entry = st.number_input("Entry premium (₹)",min_value=0.05,value=entry_default,step=0.05,format="%.2f",key="desk_entry")
        stop = st.number_input("Stop loss (₹)",min_value=0.05,value=round(max(0.05,entry_default*0.85),2),step=0.05,format="%.2f",key="desk_stop")
        target = st.number_input("Target (₹)",min_value=0.10,value=round(entry_default*1.20,2),step=0.05,format="%.2f",key="desk_target")
        charges_per_side = st.number_input("Estimated charges / side (₹)",min_value=0.0,value=20.0,step=1.0,key="desk_charges")
        if position:
            st.info(f"OPEN: {position['instrument']} · {position['quantity']} units · entry ₹{position['entry']:.2f} · SL ₹{position['stop']:.2f} · target ₹{position['target']:.2f}")
            p1,p2 = st.columns(2)
            p1.metric("Open net P&L",f"₹{position['unrealized']:,.2f}")
            p2.metric("Realized net P&L",f"₹{st.session_state.desk_realized:,.2f}")
        else:
            p1,p2 = st.columns(2)
            p1.metric("Open net P&L","₹0.00")
            p2.metric("Realized net P&L",f"₹{st.session_state.desk_realized:,.2f}")
        buy, close = st.columns(2)
        with buy:
            if st.button("BUY PAPER",type="primary",use_container_width=True,disabled=position is not None):
                if not (stop < entry < target):
                    st.error("For a long-option practice trade, stop loss must be below entry and target above entry.")
                else:
                    st.session_state.desk_position = {"instrument":f"NIFTY {int(strike)} {option_side}","strike":int(strike),"option_side":option_side,"entry":float(entry),"stop":float(stop),"target":float(target),"quantity":int(quantity),"entry_charge":float(charges_per_side),"exit_charge_estimate":float(charges_per_side),"opened_at":datetime.now().isoformat(timespec="seconds")}
                    st.session_state.desk_journal.append({"time":datetime.now().isoformat(timespec="seconds"),"action":"BUY PAPER","instrument":f"NIFTY {int(strike)} {option_side}","quantity":int(quantity),"price":float(entry),"charges":float(charges_per_side),"net_pnl":-float(charges_per_side)})
                    st.rerun()
        with close:
            if st.button("SELL / CLOSE",use_container_width=True,disabled=position is None):
                gross = (premium_now - position["entry"]) * position["quantity"]
                net = gross - position["entry_charge"] - float(charges_per_side)
                st.session_state.desk_realized += net
                st.session_state.desk_journal.append({"time":datetime.now().isoformat(timespec="seconds"),"action":"SELL / CLOSE","instrument":position["instrument"],"quantity":position["quantity"],"price":float(premium_now),"gross_pnl":gross,"charges":position["entry_charge"]+float(charges_per_side),"net_pnl":net})
                st.session_state.desk_position = None
                st.rerun()
        if position and (premium_now <= position["stop"] or premium_now >= position["target"]):
            st.warning("Stop or target crossed. This practice tool warns but does not auto-fill or auto-close.")
        st.divider()
        st.subheader("Session summary")
        closed = [x for x in st.session_state.desk_journal if x.get("action")=="SELL / CLOSE"]
        st.metric("Closed trades",len(closed))
        st.metric("Winning trades",sum(1 for x in closed if x.get("net_pnl",0)>0))
        st.metric("Estimated total charges",f"₹{sum(float(x.get('charges',0)) for x in st.session_state.desk_journal):,.2f}")

    st.divider()
    st.subheader("Paper trade journal")
    if st.session_state.desk_journal:
        journal_df = pd.DataFrame(st.session_state.desk_journal)
        st.dataframe(journal_df,use_container_width=True,hide_index=True)
        st.download_button("Download journal CSV",journal_df.to_csv(index=False).encode("utf-8"),"nifty_scalper_desk_journal.csv","text/csv")
    else:
        st.caption("No paper trades yet. Use BUY PAPER and SELL / CLOSE to practise entries and exits.")

    st.caption("Educational simulator only. Synthetic option premiums are not valued using Greeks, volatility surface, expiry, time decay or bid/ask spread. Historical replay uses the exact CE/PE pair saved in local files; changing strike in that mode changes the display label only. Use the scenario selector to practise trend, pullback, range and breakout/retest behaviour. No real orders are sent.")


render_dashboard()
