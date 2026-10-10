import pytest
from live_market import extract_quote

def test_extracts_list_quote():
    q = extract_quote([{"exchange_token":"26000","display_symbol":"NIFTY 50","ltp":"25123.4"}], "26000")
    assert q["price"] == 25123.4
    assert q["symbol"] == "NIFTY 50"

def test_extracts_nested_response():
    q = extract_quote({"data":[{"instrument_token":"123","ltp":100}]}, "123")
    assert q["price"] == 100

def test_rejects_missing_or_invalid_ltp():
    with pytest.raises(ValueError):
        extract_quote([{"exchange_token":"26000","ltp":"0"}], "26000")
