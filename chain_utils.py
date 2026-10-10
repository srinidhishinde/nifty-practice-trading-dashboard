from __future__ import annotations

import pandas as pd

NUMERIC_FIELDS = [
    "strike", "ce_ltp", "pe_ltp", "ce_oi", "pe_oi",
    "ce_change_oi", "pe_change_oi", "ce_volume", "pe_volume",
    "ce_iv", "pe_iv", "ce_delta", "pe_delta",
]

def _key(value: object) -> str:
    return " ".join(str(value).strip().lower().replace("_", " ").replace("-", " ").split())

def normalize_option_chain(frame: pd.DataFrame, aliases: dict[str, list[str]]) -> pd.DataFrame:
    if frame is None or frame.empty:
        raise ValueError("CSV contains no rows.")
    alias_lookup = {}
    for canonical, names in aliases.items():
        for name in [canonical, *names]:
            alias_lookup[_key(name)] = canonical
    rename = {}
    for col in frame.columns:
        canonical = alias_lookup.get(_key(col))
        if canonical and canonical not in rename.values():
            rename[col] = canonical
    result = frame.rename(columns=rename).copy()
    if "strike" not in result:
        raise ValueError("Could not identify strike column. Expected a Strike or Strike Price column.")
    for field in NUMERIC_FIELDS:
        if field in result:
            result[field] = pd.to_numeric(
                result[field].astype(str).str.replace(",", "", regex=False).str.replace("%", "", regex=False).str.strip(),
                errors="coerce",
            )
    for field in NUMERIC_FIELDS:
        if field not in result:
            result[field] = float("nan")
    result = result.dropna(subset=["strike"])
    result = result[result["strike"] > 0]
    result = result.sort_values("strike").drop_duplicates("strike", keep="last").reset_index(drop=True)
    if result.empty:
        raise ValueError("No numeric positive strikes were found.")
    return result

def summarize_chain(chain: pd.DataFrame, spot: float | None = None) -> dict:
    ce_oi = chain["ce_oi"].fillna(0)
    pe_oi = chain["pe_oi"].fillna(0)
    total_ce = float(ce_oi.sum())
    total_pe = float(pe_oi.sum())
    pcr = total_pe / total_ce if total_ce > 0 else float("nan")
    reference = float(spot) if spot is not None and spot > 0 else float(chain["strike"].median())
    strikes = chain["strike"].dropna()
    reference_strike = float(strikes.iloc[(strikes - reference).abs().argmin()])
    timestamp = ""
    if "timestamp" in chain.columns:
        vals = chain["timestamp"].dropna().astype(str)
        if not vals.empty:
            timestamp = vals.iloc[0]
    return {
        "pcr_oi": pcr,
        "total_ce_oi": total_ce,
        "total_pe_oi": total_pe,
        "reference_strike": reference_strike,
        "timestamp": timestamp,
    }

def scalping_context(chain: pd.DataFrame, spot: float | None, is_demo: bool = False) -> dict:
    summary = summarize_chain(chain, spot)
    center = summary["reference_strike"]
    nearby = chain[(chain["strike"] - center).abs() <= 200]
    ce_volume = float(nearby["ce_volume"].fillna(0).sum())
    pe_volume = float(nearby["pe_volume"].fillna(0).sum())
    if is_demo:
        bias = "DEMO ONLY"
        explanation = "Illustrative values only. No market bias or trade signal can be inferred from this demo."
    elif ce_volume == 0 and pe_volume == 0:
        bias = "INSUFFICIENT DATA"
        explanation = "Nearby volume is missing or zero. Provide fresh CE/PE volume and verify quote timestamps."
    elif ce_volume > pe_volume * 1.2:
        bias = "CE VOLUME HIGHER"
        explanation = "Nearby CE volume exceeds PE volume by more than 20%; this is descriptive flow context, not a BUY CE signal."
    elif pe_volume > ce_volume * 1.2:
        bias = "PE VOLUME HIGHER"
        explanation = "Nearby PE volume exceeds CE volume by more than 20%; this is descriptive flow context, not a BUY PE signal."
    else:
        bias = "MIXED / BALANCED"
        explanation = "Nearby CE/PE volume is relatively balanced. Wait for underlying price-action confirmation."
    return {"bias": bias, "near_ce_volume": ce_volume, "near_pe_volume": pe_volume, "explanation": explanation}
