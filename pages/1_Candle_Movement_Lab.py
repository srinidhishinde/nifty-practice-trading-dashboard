from __future__ import annotations

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Candle Movement Lab | NIFTY", page_icon="📈", layout="wide")
st.markdown("""
<style>
.block-container {max-width: 1800px; padding-top: .7rem}
[data-testid="stMetric"] {background:#111b26;border:1px solid #293b4d;padding:10px;border-radius:9px}
</style>
""", unsafe_allow_html=True)

st.title("NIFTY Candle Movement Lab")
st.caption("SIMULATED MARKET · PAPER PRACTICE ONLY · NOT LIVE PRICES OR A FORECAST")
st.warning("This lab generates synthetic price paths so you can practise reading candles when the market is closed. It does not reproduce actual NIFTY prices. Use historical replay for a faithful replay of past market behaviour.")

with st.sidebar:
    st.header("Simulation controls")
    timeframe = st.selectbox("Candle timeframe", ["1 minute", "2 minutes", "3 minutes", "5 minutes"], index=0)
    seconds_per_candle = st.slider("Real-time seconds to form one candle", 15, 120, 60, step=5, help="Slower settings let you watch the current candle develop instead of rapidly cycling through candles.")
    speed = st.slider("Chart refresh (seconds)", 1, 5, 2, help="How often the active candle updates. Choose 2–5 seconds for calmer movement.")
    ticks_per_candle = max(2, round(seconds_per_candle / speed))
    scenario = st.selectbox("Price-action scenario", ["Mixed market", "Uptrend with pullbacks", "Downtrend with bounces", "Range / choppy", "Breakout then retest"])
    option_side = st.radio("Practice contract", ["CE", "PE"], horizontal=True)
    strike = st.number_input("Practice strike (illustrative)", min_value=1000, max_value=100000, value=25000, step=50)
    quantity = st.number_input("Paper quantity", min_value=1, max_value=10000, value=65, step=1)
    if st.button("Restart simulation", use_container_width=True):
        for key in ["sim_tick", "sim_bars", "sim_rng", "sim_position", "sim_realized", "sim_journal", "sim_last_scenario"]:
            st.session_state.pop(key, None)
        st.rerun()

if "sim_last_scenario" not in st.session_state or st.session_state.sim_last_scenario != scenario:
    st.session_state.sim_last_scenario = scenario
    st.session_state.sim_tick = 0
    st.session_state.sim_bars = []
    st.session_state.sim_position = None
    st.session_state.sim_realized = 0.0
    st.session_state.sim_journal = []
    st.session_state.sim_rng = np.random.default_rng()
if "sim_tick" not in st.session_state: st.session_state.sim_tick = 0
if "sim_bars" not in st.session_state: st.session_state.sim_bars = []
if "sim_position" not in st.session_state: st.session_state.sim_position = None
if "sim_realized" not in st.session_state: st.session_state.sim_realized = 0.0
if "sim_journal" not in st.session_state: st.session_state.sim_journal = []
if "sim_rng" not in st.session_state: st.session_state.sim_rng = np.random.default_rng()

# Synthetic underlying path: each refresh is an intrabar tick. Only the active candle changes;
# the candle is finalized after ticks_per_candle refreshes.
st_autorefresh(interval=speed * 1000, key="candle_lab_refresh")
rng = st.session_state.sim_rng
bars = st.session_state.sim_bars
tick = int(st.session_state.sim_tick)
start_spot = 25000.0
if bars:
    previous_close = float(bars[-1]["close"])
else:
    previous_close = start_spot
bar_number = tick // ticks_per_candle
tick_in_bar = tick % ticks_per_candle
if not bars or tick_in_bar == 0:
    if scenario == "Uptrend with pullbacks": drift = 0.45 if (bar_number // 8) % 3 else -0.25
    elif scenario == "Downtrend with bounces": drift = -0.45 if (bar_number // 8) % 3 else 0.25
    elif scenario == "Range / choppy": drift = 0.0
    elif scenario == "Breakout then retest": drift = 0.75 if bar_number % 12 < 7 else (-0.45 if bar_number % 12 < 10 else 0.1)
    else: drift = [0.25, -0.1, 0.0, -0.3, 0.4, 0.1][(bar_number // 5) % 6]
    open_price = previous_close
    bars.append({"timestamp": datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=bar_number * int(timeframe.split()[0])), "open": open_price, "high": open_price, "low": open_price, "close": open_price, "volume": 0})
active = bars[-1]
if scenario == "Uptrend with pullbacks": drift_tick = 0.055 if (bar_number // 8) % 3 else -0.035
elif scenario == "Downtrend with bounces": drift_tick = -0.055 if (bar_number // 8) % 3 else 0.035
elif scenario == "Range / choppy": drift_tick = 0.0
elif scenario == "Breakout then retest": drift_tick = 0.09 if bar_number % 12 < 7 else (-0.06 if bar_number % 12 < 10 else 0.015)
else: drift_tick = [0.03, -0.01, 0.0, -0.035, 0.045, 0.01][(bar_number // 5) % 6]
move = (drift_tick * (10 / ticks_per_candle)) + float(rng.normal(0, 0.10 * (10 / ticks_per_candle) ** 0.5))
new_price = max(100.0, float(active["close"]) + move)
active["close"] = new_price
active["high"] = max(float(active["high"]), new_price)
active["low"] = min(float(active["low"]), new_price)
active["volume"] = int(active["volume"]) + int(rng.integers(1, 150))
st.session_state.sim_tick = tick + 1
# Bound memory while keeping enough chart history.
if len(bars) > 500:
    del bars[:-500]
st.session_state.sim_bars = bars

underlying_move = new_price - start_spot
# Illustrative premium path: a small delta-like response plus random volatility.
base_premium = 180.0
if "sim_premium" not in st.session_state: st.session_state.sim_premium = base_premium
premium_change = (move * (0.30 if option_side == "CE" else -0.30)) + float(rng.normal(0, 0.08))
st.session_state.sim_premium = max(0.05, float(st.session_state.sim_premium) + premium_change)
premium = float(st.session_state.sim_premium)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Simulated NIFTY", f"₹{new_price:,.2f}", f"{move:+.2f} this tick")
col2.metric(f"Illustrative {option_side} premium", f"₹{premium:,.2f}", help="Synthetic premium; not an actual option quote.")
col3.metric("Realized paper P&L", f"₹{st.session_state.sim_realized:,.2f}")
pos = st.session_state.sim_position
unrealized = ((premium - pos["entry"]) * quantity) if pos else 0.0
col4.metric("Open paper P&L", f"₹{unrealized:,.2f}")

st.subheader("Underlying candle forming now")
frame = pd.DataFrame(bars[-100:])
fig = go.Figure(data=[go.Candlestick(x=frame["timestamp"], open=frame["open"], high=frame["high"], low=frame["low"], close=frame["close"], name="Simulated NIFTY")])
if len(frame) >= 9:
    fig.add_trace(go.Scatter(x=frame["timestamp"], y=frame["close"].ewm(span=9, adjust=False).mean(), name="EMA 9"))
if len(frame) >= 21:
    fig.add_trace(go.Scatter(x=frame["timestamp"], y=frame["close"].ewm(span=21, adjust=False).mean(), name="EMA 21"))
fig.update_layout(template="plotly_dark", height=560, xaxis_rangeslider_visible=False, yaxis_title="Simulated index points", margin=dict(l=8,r=8,t=18,b=8), uirevision="candle-lab")
st.plotly_chart(fig, use_container_width=True)
st.caption(f"Active {timeframe} candle · update {tick_in_bar + 1}/{ticks_per_candle} · refresh every {speed}s · one candle forms over about {seconds_per_candle}s · simulated only.")

st.subheader(f"{option_side} premium practice chart")
premium_history = st.session_state.get("sim_premium_history", [])
premium_history.append({"timestamp": datetime.now(), "premium": premium})
st.session_state.sim_premium_history = premium_history[-200:]
pframe = pd.DataFrame(st.session_state.sim_premium_history)
pfig = go.Figure()
pfig.add_trace(go.Scatter(x=pframe["timestamp"], y=pframe["premium"], mode="lines", name=f"Illustrative {option_side} premium"))
if pos:
    pfig.add_hline(y=pos["entry"], line_dash="dash", annotation_text="Entry")
    pfig.add_hline(y=pos["stop"], line_dash="dot", annotation_text="Stop")
    pfig.add_hline(y=pos["target"], line_dash="dot", annotation_text="Target")
pfig.update_layout(template="plotly_dark", height=300, yaxis_title="Synthetic option premium (₹)", margin=dict(l=8,r=8,t=18,b=8), uirevision=f"premium-{option_side}")
st.plotly_chart(pfig, use_container_width=True)

st.subheader("Paper order ticket")
a, b, c, d = st.columns(4)
entry = a.number_input("Entry premium", min_value=0.05, value=round(premium, 2), step=0.05, key="lab_entry")
stop = b.number_input("Stop-loss premium", min_value=0.05, value=round(max(0.05, premium * 0.85), 2), step=0.05, key="lab_stop")
target = c.number_input("Target premium", min_value=0.10, value=round(premium * 1.20, 2), step=0.05, key="lab_target")
charges = d.number_input("Estimated round-trip charges (₹)", min_value=0.0, value=40.0, step=5.0, key="lab_charges")
buy_col, close_col, flat_col = st.columns([1,1,3])
with buy_col:
    if st.button("BUY PAPER", type="primary", disabled=pos is not None, use_container_width=True):
        if not stop < entry < target:
            st.error("For a long option, stop-loss < entry < target.")
        else:
            st.session_state.sim_position = {"entry": float(entry), "stop": float(stop), "target": float(target), "quantity": int(quantity), "time": datetime.now().isoformat(timespec="seconds"), "side": option_side}
            st.session_state.sim_journal.append({"time": datetime.now().isoformat(timespec="seconds"), "action": "BUY", "contract": f"NIFTY {int(strike)} {option_side}", "qty": int(quantity), "price": float(entry), "net_pnl": -charges/2})
            st.rerun()
with close_col:
    if st.button("SELL / CLOSE", disabled=pos is None, use_container_width=True):
        pnl = (premium - pos["entry"]) * pos["quantity"] - charges
        st.session_state.sim_realized += pnl
        st.session_state.sim_journal.append({"time": datetime.now().isoformat(timespec="seconds"), "action": "SELL / CLOSE", "contract": f"NIFTY {int(strike)} {pos['side']}", "qty": pos["quantity"], "price": premium, "net_pnl": pnl})
        st.session_state.sim_position = None
        st.rerun()
with flat_col:
    st.caption("Practice orders only. Charges are estimates. No broker orders are sent.")

if pos:
    if premium <= pos["stop"] or premium >= pos["target"]:
        st.warning("Stop-loss or target has been crossed. This lab does not auto-close; use SELL / CLOSE to record your exit.")
    st.info(f"Open: NIFTY {int(strike)} {pos['side']} · entry ₹{pos['entry']:.2f} · SL ₹{pos['stop']:.2f} · target ₹{pos['target']:.2f} · quantity {pos['quantity']}")

with st.expander("Paper trade journal"):
    if st.session_state.sim_journal:
        st.dataframe(pd.DataFrame(st.session_state.sim_journal), use_container_width=True)
        st.download_button("Download journal CSV", pd.DataFrame(st.session_state.sim_journal).to_csv(index=False), "nifty_candle_lab_journal.csv", "text/csv")
    else:
        st.caption("No paper trades yet.")
