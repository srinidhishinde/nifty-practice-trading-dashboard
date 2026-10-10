from __future__ import annotations

def pnl_for_long(entry: float, mark: float, quantity: int) -> float:
    if entry < 0 or mark < 0 or quantity < 0:
        raise ValueError("Entry, mark and quantity must be non-negative.")
    return (mark - entry) * quantity

def close_long(entry: float, exit_price: float, quantity: int, entry_charge: float = 0.0, exit_charge: float = 0.0) -> dict:
    if min(entry, exit_price, quantity, entry_charge, exit_charge) < 0:
        raise ValueError("Prices, quantity and charges must be non-negative.")
    gross = pnl_for_long(entry, exit_price, quantity)
    charges = entry_charge + exit_charge
    return {"gross_pnl": gross, "charges": charges, "net_pnl": gross - charges}
