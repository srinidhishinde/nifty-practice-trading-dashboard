from __future__ import annotations

import time
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from replay import add_indicators, normalize_ohlcv, resample_ohlcv, visible_bar_count

st.set_page_config(page_title="NIFTY Practice Desk", page_icon="📈", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.2rem; max-width: 1600px}
[data-testid="stMetric"] {background: #101923; border: 1px solid #263747; padding: 12px; border-radius: 10px}
h1,h2,h3 {letter-spacing: -.02em}
</style>
""", unsafe_allow_html=True)
st.title("📈 NIFTY Practice Trading Desk")
st.caption("HISTORICAL REPLAY · SIMULATED ORDERS ONLY · NO BROKER EXECUTION")
st.warning("Off-hours practice uses uploaded historical candles. This is not a live market feed. Never upload option-chain snapshots as OHLCV candles.")

with st.sidebar:
    st.header("Replay controls")
    uploaded = st.file_uploader("Upload historical OHLCV CSV", type=["csv"])
    timeframe = st.selectbox("Chart timeframe", [1, 3, 5, 10, 15], index=2, format_func=lambda x: f"{x} minute")
    speed = st.select_slider("Replay speed", options=[1, 2, 5, 10], value=1, format_func=lambda x: f"{x}×")
    st.caption("1× = one simulated second per real second. Bars appear at their selected timeframe interval.")
    st.divider()
    st.header("Virtual account")
    if "starting_capital" not in st.session_state:
        st.session_state.starting_capital = 50000.0
    st.session_state.starting_capital = st.number_input("Starting capital (₹)", min_value=1000.0, max_value=100000000.0, value=float(st.session_state.starting_capital), step=5000.0)
    st.caption("Capital is a practice setting, not connected to your broker.")

def sample_data() -> pd.DataFrame:
    # Static, clearly-labelled illustrative data only; never presented as market data.
    ts = pd.date_range("2025-01-02 09:15", periods=120, freq="min")
    close = [23500.0]
    for i in range(1, len(ts)):
        close.append(close[-1] + (0.8 if i % 7 < 4 else -1.1) + ((i % 5) - 2) * 0.45)
    return pd.DataFrame({"timestamp": ts, "open": close, "high": [x+4 for x in close],
                         "low": [x-4 for x in close], "close": close,
                         "volume": [1000 + (i*137)%1700 for i in range(len(close))]})

if uploaded:
    try:
        raw = normalize_ohlcv(pd.read_csv(uploaded))
        source_label = "UPLOADED HISTORICAL DATA"
    except Exception as exc:
        st.error(f"CSV validation failed: {exc}")
        st.stop()
else:
    raw = sample_data()
    source_label = "ILLUSTRATIVE DEMO DATA — NOT REAL NIFTY PRICES"

try:
    bars = resample_ohlcv(raw, timeframe)
except Exception as exc:
    st.error(str(exc))
    st.stop()

if "replay_started_at" not in st.session_state: st.session_state.replay_started_at = None
if "elapsed_before_pause" not in st.session_state: st.session_state.elapsed_before_pause = 0.0
if "is_playing" not in st.session_state: st.session_state.is_playing = False
if "trades" not in st.session_state: st.session_state.trades = []
if "journal" not in st.session_state: st.session_state.journal = []
if "active_trade" not in st.session_state: st.session_state.active_trade = None
if "replay_key" not in st.session_state: st.session_state.replay_key = None

data_key = (source_label, len(bars), str(bars["timestamp"].iloc[0]), timeframe)
if st.session_state.replay_key != data_key:
    st.session_state.replay_key = data_key
    st.session_state.replay_started_at = None
    st.session_state.elapsed_before_pause = 0.0
    st.session_state.is_playing = False
    st.session_state.trades = []
    st.session_state.journal = []
    st.session_state.active_trade = None

c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
with c1:
    if st.button("▶ Play", use_container_width=True):
        st.session_state.replay_started_at = time.monotonic()
        st.session_state.is_playing = True
with c2:
    if st.button("⏸ Pause", use_container_width=True):
        if st.session_state.is_playing and st.session_state.replay_started_at is not None:
            st.session_state.elapsed_before_pause += (time.monotonic() - st.session_state.replay_started_at) * speed
        st.session_state.is_playing = False
        st.session_state.replay_started_at = None
with c3:
    if st.button("↺ Reset", use_container_width=True):
        st.session_state.replay_started_at = None
        st.session_state.elapsed_before_pause = 0.0
        st.session_state.is_playing = False
        st.session_state.trades = []
        st.session_state.journal = []
        st.session_state.active_trade = None
with c4:
    st.info(f"**{source_label}** · {len(raw):,} source rows · {len(bars):,} chart bars")

elapsed = st.session_state.elapsed_before_pause
if st.session_state.is_playing and st.session_state.replay_started_at is not None:
    elapsed += (time.monotonic() - st.session_state.replay_started_at) * speed
visible = visible_bar_count(elapsed, timeframe, len(bars))
shown = add_indicators(bars.iloc[:visible].copy())
done = visible >= len(bars)
if done and st.session_state.is_playing:
    st.session_state.is_playing = False
    st.session_state.replay_started_at = None
    st.session_state.elapsed_before_pause = max(0, (len(bars)-1) * timeframe * 60)

if visible:
    last = shown.iloc[-1]
    previous = shown.iloc[-2]["close"] if len(shown) > 1 else last["open"]
    change = float(last["close"] - previous)
    a,b,c,d,e = st.columns(5)
    a.metric("Replay close", f"{last['close']:,.2f}", f"{change:+.2f}")
    b.metric("Bars revealed", f"{visible}/{len(bars)}")
    c.metric("RSI (14)", f"{last['RSI 14']:.1f}")
    d.metric("EMA 9 / 21", f"{last['EMA 9']:.2f} / {last['EMA 21']:.2f}")
    e.metric("VWAP", f"{last['VWAP']:.2f}")

    fig = go.Figure(data=[go.Candlestick(x=shown["timestamp"], open=shown["open"], high=shown["high"], low=shown["low"], close=shown["close"], name="NIFTY replay")])
    fig.add_trace(go.Scatter(x=shown["timestamp"], y=shown["EMA 9"], name="EMA 9", line=dict(width=1.5)))
    fig.add_trace(go.Scatter(x=shown["timestamp"], y=shown["EMA 21"], name="EMA 21", line=dict(width=1.5)))
    fig.add_trace(go.Scatter(x=shown["timestamp"], y=shown["VWAP"], name="VWAP", line=dict(width=1.5, dash="dot")))
    fig.update_layout(template="plotly_dark", height=560, margin=dict(l=10,r=10,t=25,b=10), xaxis_rangeslider_visible=False, legend=dict(orientation="h", y=1.02), uirevision="practice")
    st.plotly_chart(fig, use_container_width=True)
    vfig = go.Figure(go.Bar(x=shown["timestamp"], y=shown["volume"], name="Volume"))
    vfig.update_layout(template="plotly_dark", height=170, margin=dict(l=10,r=10,t=10,b=10), showlegend=False)
    st.plotly_chart(vfig, use_container_width=True)
    rfig = go.Figure()
    rfig.add_trace(go.Scatter(x=shown["timestamp"], y=shown["RSI 14"], name="RSI 14"))
    rfig.add_hline(y=70, line_dash="dash")
    rfig.add_hline(y=30, line_dash="dash")
    rfig.update_layout(template="plotly_dark", height=210, yaxis=dict(range=[0,100]), margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(rfig, use_container_width=True)
else:
    st.info("Press Play to start the replay clock.")

st.divider()
st.subheader("Practice order ticket")
left, right = st.columns([1, 1])
with left:
    side = st.radio("Practice action", ["BUY CE", "BUY PE", "WAIT"], horizontal=True)
    instrument = st.selectbox("Practice instrument", ["NIFTY CE", "NIFTY PE"])
    strike = st.number_input("Option strike (manual practice label)", min_value=1, value=23500, step=50)
    qty = st.number_input("Quantity / lots multiplier", min_value=1, max_value=100, value=1)
    entry_default = float(shown.iloc[-1]["close"]) if visible else 0.0
    entry = st.number_input("Simulated entry premium (₹)", min_value=0.0, value=max(0.05, entry_default if entry_default > 0 else 100.0), step=0.5)
    stop = st.number_input("Stop-loss premium (₹)", min_value=0.0, value=max(0.0, round(entry * 0.8, 2)), step=0.5)
    target = st.number_input("Target premium (₹)", min_value=0.0, value=round(entry * 1.3, 2), step=0.5)
    if st.button("Record practice decision", type="primary", use_container_width=True):
        ts = str(shown.iloc[-1]["timestamp"]) if visible else "Replay not started"
        row = {"time": ts, "decision": side, "instrument": instrument, "strike": int(strike), "quantity": int(qty), "entry": float(entry), "stop": float(stop), "target": float(target), "status": "PRACTICE ONLY"}
        st.session_state.journal.append(row)
        if side != "WAIT":
            st.session_state.active_trade = row
        st.success("Decision recorded in this browser session.")
with right:
    st.markdown("**Practice guardrails**")
    st.write("- Orders never reach Kotak Neo or any broker.")
    st.write("- Option premium is manually entered; NIFTY index candles do not imply an option premium.")
    st.write("- Historical option-chain/option OHLCV data is needed for realistic option P&L.")
    st.write("- This starter does not fabricate option-chain prices or auto-fill trades.")
    st.write("- A target/stop is a journal plan until you enter an observed exit premium.")

if st.session_state.journal:
    st.subheader("Decision journal")
    journal = pd.DataFrame(st.session_state.journal)
    st.dataframe(journal, use_container_width=True, hide_index=True)
    st.download_button("Download journal CSV", journal.to_csv(index=False).encode("utf-8"), "practice_journal.csv", "text/csv")
else:
    st.caption("No practice decisions recorded yet.")

if st.session_state.is_playing and not done:
    time.sleep(1)
    st.rerun()
