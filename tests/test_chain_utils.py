import pandas as pd
import pytest

from chain_utils import normalize_option_chain, summarize_chain, scalping_context

ALIASES = {
    "strike": ["strike", "strike price"],
    "ce_ltp": ["ce ltp", "call ltp"],
    "pe_ltp": ["pe ltp", "put ltp"],
    "ce_oi": ["ce oi", "call oi"],
    "pe_oi": ["pe oi", "put oi"],
    "ce_change_oi": ["ce change in oi", "ce chg in oi"],
    "pe_change_oi": ["pe change in oi", "pe chg in oi"],
    "ce_volume": ["ce volume", "call volume"],
    "pe_volume": ["pe volume", "put volume"],
    "timestamp": ["timestamp", "time"],
}

def test_normalizes_common_headers_and_numeric_commas():
    frame = pd.DataFrame({
        "Strike Price": ["24,500", "24550"],
        "Call LTP": ["120.5", "100"],
        "Put LTP": ["80", "105"],
        "CE OI": ["10,000", "12,000"],
        "PE OI": ["9,000", "15,000"],
        "CE Chg in OI": ["1,000", "500"],
        "PE Chg in OI": ["300", "800"],
        "CE Volume": ["2000", "2200"],
        "PE Volume": ["2100", "2300"],
    })
    result = normalize_option_chain(frame, ALIASES)
    assert list(result["strike"]) == [24500, 24550]
    assert result.loc[0, "ce_oi"] == 10000
    assert result.loc[1, "pe_change_oi"] == 800

def test_rejects_missing_strike():
    with pytest.raises(ValueError, match="strike"):
        normalize_option_chain(pd.DataFrame({"CE LTP": [10]}), ALIASES)

def test_deduplicates_strikes_using_last_row():
    frame = pd.DataFrame({"strike": [24500, 24500], "ce ltp": [100, 101]})
    result = normalize_option_chain(frame, ALIASES)
    assert len(result) == 1
    assert result.iloc[0]["ce_ltp"] == 101

def test_pcr_and_reference_strike_use_observed_spot():
    frame = pd.DataFrame({"strike": [24500, 24550, 24600], "ce oi": [100, 100, 100], "pe oi": [100, 200, 300]})
    chain = normalize_option_chain(frame, ALIASES)
    summary = summarize_chain(chain, spot=24570)
    assert summary["pcr_oi"] == pytest.approx(2.0)
    assert summary["reference_strike"] == 24550

def test_demo_never_produces_trade_bias():
    chain = normalize_option_chain(pd.DataFrame({"strike": [24500, 24550], "ce volume": [100, 1000], "pe volume": [1000, 100]}), ALIASES)
    context = scalping_context(chain, spot=None, is_demo=True)
    assert context["bias"] == "DEMO ONLY"
    assert "No market bias" in context["explanation"]

def test_missing_volume_does_not_guess_bias():
    chain = normalize_option_chain(pd.DataFrame({"strike": [24500, 24550]}), ALIASES)
    context = scalping_context(chain, spot=None)
    assert context["bias"] == "INSUFFICIENT DATA"
