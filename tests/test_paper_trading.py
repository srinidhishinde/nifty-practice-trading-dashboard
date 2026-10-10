import pytest
from paper_trading import pnl_for_long, close_long

def test_long_profit():
    assert pnl_for_long(100, 110, 65) == 650

def test_long_loss():
    assert pnl_for_long(100, 90, 65) == -650

def test_net_pnl_deducts_entry_and_exit_charges():
    assert close_long(100, 110, 65, 20, 20) == {"gross_pnl": 650, "charges": 40, "net_pnl": 610}

def test_rejects_negative_values():
    with pytest.raises(ValueError):
        pnl_for_long(100, -1, 1)
