from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chain_utils import normalize_option_chain, summarize_chain, scalping_context

st.set_page_config(page_title="NIFTY Options Scalper", page_icon="📈", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1rem; max-width: 1700px}
[data-testid="stMetric"] {background: #111b26; border: 1px solid #293b4d; padding: 12px; border-radius: 10px}
</style>
""", unsafe_allow_html=True)

st.title("📈 NIFTY Options Scalper")
st.caption("NIFTY ONLY · OPTION-CHAIN ANALYSIS · PRACTICE / RESEARCH · NO BROKER EXECUTION")
st.warning("This dashboard does not connect to Kotak Neo or fetch live market data. Upload a current option-chain CSV to analyze real observations. Demo values are illustrative only; never trade from demo data.")

ALIASES = {
    "strike": ["strike", "strike price", "strike_price", "strikeprice"],
    "ce_ltp": ["ce ltp", "call ltp", "call last price", "ce last price", "call ltp (₹)", "ce_ltp"],
    "pe_ltp": ["pe ltp", "put ltp", "put last price", "pe last price", "put ltp (₹)", "pe_ltp"],
    "ce_oi": ["ce oi", "call oi", "call open interest", "ce open interest", "ce_oi"],
    "pe_oi": ["pe oi", "put oi", "put open interest", "pe open interest", "pe_oi"],
    "ce_change_oi": ["ce change in oi", "ce chg in oi", "call change in oi", "call chg in oi", "ce_change_oi"],
    "pe_change_oi": ["pe change in oi", "pe chg in oi", "put change in oi", "put chg in oi", "pe_change_oi"],
    "ce_volume": ["ce volume", "call volume", "ce_volume"],
    "pe_volume": ["pe volume", "put volume", "pe_volume"],
    "ce_iv": ["ce iv", "call iv", "ce_iv"],
    "pe_iv": ["pe iv", "put iv", "pe_iv"],
    "ce_delta": ["ce delta", "call delta", "ce_delta"],
    "pe_delta": ["pe delta", "put delta", "pe_delta"],
    "timestamp": ["timestamp", "time", "datetime", "date time", "snapshot time"],
}

def demo_chain() -> pd.DataFrame:
    strikes = list(range(24000, 25101, 50))
    center = 24550
    rows = []
    for k in strikes:
        dist = (k - center) / 50
        rows.append({
            "strike": k,
            "ce_ltp": round(max(1, 220 - dist * 8 + abs(dist) * 1.2), 2),
            "pe_ltp": round(max(1, 215 + dist * 8 + abs(dist) * 1.2), 2),
            "ce_oi": int(100000 + max(0, dist) * 12000 + (k % 7) * 1300),
            "pe_oi": int(90000 + max(0, -dist) * 13500 + (k % 5) * 1700),
            "ce_change_oi": int((dist + 2) * 800),
            "pe_change_oi": int((-dist + 2) * 750),
            "ce_volume": int(10000 + max(0, 5 - abs(dist)) * 2500),
            "pe_volume": int(9500 + max(0, 5 - abs(dist)) * 2600),
            "ce_iv": round(13 + abs(dist) * .35, 2),
            "pe_iv": round(13.4 + abs(dist) * .34, 2),
            "ce_delta": round(max(.05, min(.95, .5 - dist * .045)), 3),
            "pe_delta": round(max(-.95, min(-.05, -.5 - dist * .045)), 3),
        })
    return pd.DataFrame(rows)

with st.sidebar:
    st.header("Scalper controls")
    chain_file = st.file_uploader("Upload option-chain snapshot CSV", type=["csv"])
    spot = st.number_input("Observed NIFTY spot (₹)", min_value=0.0, value=0.0, step=50.0, help="Enter the observed spot from your market source. Leave 0 if unknown.")
    timeframe = st.selectbox("Entry timeframe", ["1-minute", "2-minute", "3-minute"], index=2)
    trend_file = st.file_uploader("Optional NIFTY index OHLCV CSV", type=["csv"], help="Separate underlying candles: timestamp, open, high, low, close, volume. This is not option-chain data.")
    st.caption("Live Kotak integration is not implemented. Uploaded data is analyzed as supplied; check its timestamp and source.")

if chain_file:
    try:
        chain = normalize_option_chain(pd.read_csv(chain_file), ALIASES)
        source_label = "UPLOADED OPTION-CHAIN SNAPSHOT"
    except Exception as exc:
        st.error(f"Option-chain CSV validation failed: {exc}")
        st.stop()
else:
    chain = normalize_option_chain(demo_chain(), ALIASES)
    source_label = "ILLUSTRATIVE DEMO — NOT LIVE DATA"

if chain.empty:
    st.error("No valid strike rows found.")
    st.stop()

summary = summarize_chain(chain, spot=spot if spot > 0 else None)
atm_strike = summary["reference_strike"]
nearby = chain.loc[(chain["strike"] - atm_strike).abs() <= 500].copy()
if nearby.empty:
    nearby = chain.copy()

st.info(f"**Data status: {source_label}** · {len(chain)} strikes · Reference strike {atm_strike:,.0f}" + (f" · Snapshot timestamp: {summary['timestamp']}" if summary["timestamp"] else " · Snapshot timestamp not provided"))
if source_label.startswith("ILLUSTRATIVE"):
    st.error("DEMO MODE: all prices, OI and indicators below are invented examples for layout testing. No BUY CE / BUY PE signal is produced from demo data.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("PCR (OI)", f"{summary['pcr_oi']:.2f}" if pd.notna(summary["pcr_oi"]) else "N/A")
m2.metric("CE OI", f"{summary['total_ce_oi']:,.0f}")
m3.metric("PE OI", f"{summary['total_pe_oi']:,.0f}")
m4.metric("Reference strike", f"{atm_strike:,.0f}", "Observed spot" if spot > 0 else "Strike midpoint proxy")

left, right = st.columns([1.35, 1])
with left:
    st.subheader("CE vs PE premium by strike")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=nearby["strike"], y=nearby["ce_ltp"], name="CE LTP"))
    fig.add_trace(go.Bar(x=nearby["strike"], y=nearby["pe_ltp"], name="PE LTP"))
    fig.update_layout(template="plotly_dark", barmode="group", height=420, xaxis_title="Strike", yaxis_title="Premium (₹)", legend=dict(orientation="h", y=1.08), margin=dict(l=10,r=10,t=35,b=10))
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("Open interest")
    oi = go.Figure()
    oi.add_trace(go.Bar(x=nearby["strike"], y=nearby["ce_oi"], name="CE OI"))
    oi.add_trace(go.Bar(x=nearby["strike"], y=nearby["pe_oi"], name="PE OI"))
    oi.update_layout(template="plotly_dark", barmode="group", height=420, xaxis_title="Strike", yaxis_title="Open interest", legend=dict(orientation="h", y=1.08), margin=dict(l=10,r=10,t=35,b=10))
    st.plotly_chart(oi, use_container_width=True)

st.subheader("Change in OI")
chg = go.Figure()
chg.add_trace(go.Bar(x=nearby["strike"], y=nearby["ce_change_oi"], name="CE change in OI"))
chg.add_trace(go.Bar(x=nearby["strike"], y=nearby["pe_change_oi"], name="PE change in OI"))
chg.update_layout(template="plotly_dark", barmode="group", height=300, xaxis_title="Strike", yaxis_title="Change in OI", legend=dict(orientation="h", y=1.12), margin=dict(l=10,r=10,t=35,b=10))
st.plotly_chart(chg, use_container_width=True)

st.subheader("Scalping context")
context = scalping_context(chain, spot=spot if spot > 0 else None, is_demo=source_label.startswith("ILLUSTRATIVE"))
c1, c2, c3 = st.columns(3)
c1.metric("Bias", context["bias"])
c2.metric("Nearby CE volume", f"{context['near_ce_volume']:,.0f}")
c3.metric("Nearby PE volume", f"{context['near_pe_volume']:,.0f}")
st.write(context["explanation"])
st.caption("OI/PCR and option premiums are context, not a standalone entry trigger. A credible 1–3 minute signal also needs timestamped underlying candles, price-action confirmation, liquidity/spread checks and fresh option quotes. No automated trade recommendation is generated from a single snapshot.")

with st.expander("Normalized option-chain table"):
    display_cols = [c for c in ["strike","ce_ltp","pe_ltp","ce_oi","pe_oi","ce_change_oi","pe_change_oi","ce_volume","pe_volume","ce_iv","pe_iv","ce_delta","pe_delta"] if c in chain]
    st.dataframe(chain[display_cols], use_container_width=True, hide_index=True)
    st.download_button("Download normalized chain CSV", chain[display_cols].to_csv(index=False).encode("utf-8"), "nifty_option_chain_normalized.csv", "text/csv")

if trend_file:
    try:
        raw = pd.read_csv(trend_file)
        cols = {str(c).strip().lower(): c for c in raw.columns}
        required = ["timestamp", "open", "high", "low", "close", "volume"]
        missing = [x for x in required if x not in cols]
        if missing:
            st.error("Underlying OHLCV CSV missing columns: " + ", ".join(missing))
        else:
            candles = raw.rename(columns={cols[x]: x for x in required})
            candles["timestamp"] = pd.to_datetime(candles["timestamp"], errors="coerce")
            for col in ["open","high","low","close","volume"]:
                candles[col] = pd.to_numeric(candles[col], errors="coerce")
            candles = candles.dropna(subset=required).sort_values("timestamp")
            if len(candles) < 2:
                st.warning("Upload at least two valid underlying OHLCV rows.")
            else:
                candles["ema9"] = candles["close"].ewm(span=9, adjust=False).mean()
                candles["ema21"] = candles["close"].ewm(span=21, adjust=False).mean()
                candles["vwap"] = (candles["close"] * candles["volume"]).cumsum() / candles["volume"].replace(0, pd.NA).cumsum()
                st.subheader("NIFTY underlying trend (uploaded OHLCV)")
                tf = go.Figure(data=[go.Candlestick(x=candles["timestamp"], open=candles["open"], high=candles["high"], low=candles["low"], close=candles["close"], name="NIFTY")])
                tf.add_trace(go.Scatter(x=candles["timestamp"], y=candles["ema9"], name="EMA 9"))
                tf.add_trace(go.Scatter(x=candles["timestamp"], y=candles["ema21"], name="EMA 21"))
                tf.add_trace(go.Scatter(x=candles["timestamp"], y=candles["vwap"], name="VWAP"))
                tf.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False, margin=dict(l=10,r=10,t=25,b=10))
                st.plotly_chart(tf, use_container_width=True)
                last = candles.iloc[-1]
                trend = "UP" if last["close"] > last["ema9"] > last["ema21"] else "DOWN" if last["close"] < last["ema9"] < last["ema21"] else "MIXED"
                st.metric("Last-candle trend context", trend, f"Close {last['close']:,.2f}")
                st.caption("Trend context only. EMA/VWAP values are computed from the uploaded candles, not a live feed.")
    except Exception as exc:
        st.error(f"Could not process underlying candles: {exc}")

st.divider()
st.subheader("Data requirements for genuine scalping")
st.markdown("- Option-chain snapshots show strike-wise fields at a point in time; they are not option candles. For a 1–3 minute premium chart, collect repeated timestamped snapshots or actual CE/PE contract OHLCV.\n- Use the current expiry and actual listed strikes. Validate lot size, spread, quote age, market hours and timestamp before using any signal.\n- This practice dashboard neither authenticates with Kotak Neo nor submits orders.")
