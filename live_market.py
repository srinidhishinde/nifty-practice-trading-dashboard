from __future__ import annotations

from datetime import datetime
from typing import Any

def extract_quote(response: Any, token: str) -> dict:
    """Normalize the common Kotak Neo quotes response shapes without guessing prices."""
    candidates = []
    if isinstance(response, list):
        candidates = response
    elif isinstance(response, dict):
        for key in ("data", "result", "quotes"):
            value = response.get(key)
            if isinstance(value, list):
                candidates = value
                break
            if isinstance(value, dict):
                candidates = list(value.values())
                break
        if not candidates and any(k in response for k in ("ltp", "last_traded_price")):
            candidates = [response]
    for item in candidates:
        if not isinstance(item, dict):
            continue
        item_token = str(item.get("exchange_token", item.get("instrument_token", item.get("token", ""))))
        if item_token and item_token != str(token):
            continue
        raw = item.get("ltp", item.get("last_traded_price", item.get("lastTradedPrice")))
        try:
            price = float(raw)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        return {
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "price": price,
            "symbol": str(item.get("display_symbol", item.get("trading_symbol", item.get("symbol", token)))),
            "change": item.get("change", item.get("net_change")),
            "volume": item.get("last_volume", item.get("volume_traded_today")),
            "raw": item,
        }
    raise ValueError("Kotak Neo response contained no valid LTP for the requested token.")
