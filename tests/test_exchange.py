from datetime import datetime

import pytest

from conftest import load_fixture
from fetcher.http import FetchError
from fetcher.sources import exchange
from fetcher.sources.exchange import ExchangeSource
from fetcher.timeutil import JST

NOW = datetime(2026, 10, 13, 6, 0, tzinfo=JST)
LONDON = {"id": "london", "currency": "GBP"}
SERIES_URL = "https://api.frankfurter.dev/v1/2"
CURRENCIES_URL = "https://api.frankfurter.dev/v1/currencies"


@pytest.fixture(autouse=True)
def clear_cache():
    exchange.supported_currencies.cache_clear()
    yield
    exchange.supported_currencies.cache_clear()


def series(rates: dict) -> dict:
    return {"amount": 1.0, "base": "GBP", "rates": {d: {"JPY": v} for d, v in rates.items()}}


def history(rates: dict) -> list:
    return [{"date": d, "jpy": v} for d, v in rates.items()]


def test_first_fetch_requests_365_days(fake_http):
    fake_http.add(SERIES_URL, series({"2026-10-12": 209.91}))
    ExchangeSource().fetch(LONDON, None, NOW)
    assert fake_http.calls[0]["url"] == "https://api.frankfurter.dev/v1/2025-10-13.."
    assert fake_http.calls[0]["params"] == {"base": "GBP", "symbols": "JPY"}


def test_parses_series_into_history(fake_http):
    raw = load_fixture("frankfurter_gbp_series.json")
    fake_http.add(SERIES_URL, raw)
    data = ExchangeSource().fetch(LONDON, None, NOW)
    assert data["currency"] == "GBP"
    dates = [h["date"] for h in data["history"]]
    assert dates == sorted(raw["rates"])
    assert data["history"][-1] == {"date": "2026-10-12", "jpy": raw["rates"]["2026-10-12"]["JPY"]}


def test_incremental_fetch_starts_from_last_date(fake_http):
    fake_http.add(SERIES_URL, series({"2026-10-09": 209.22}))
    previous = {"currency": "GBP", "history": history({"2026-10-08": 209.04, "2026-10-09": 209.22})}
    ExchangeSource().fetch(LONDON, previous, NOW)
    assert fake_http.calls[0]["url"] == "https://api.frankfurter.dev/v1/2026-10-09.."


def test_merge_overwrites_same_date_and_keeps_old(fake_http):
    fake_http.add(SERIES_URL, series({"2026-10-09": 209.22, "2026-10-12": 209.91}))
    previous = {"currency": "GBP", "history": history({"2026-10-08": 209.04, "2026-10-09": 209.00})}
    data = ExchangeSource().fetch(LONDON, previous, NOW)
    assert data["history"] == history({"2026-10-08": 209.04, "2026-10-09": 209.22, "2026-10-12": 209.91})


@pytest.mark.parametrize("rates", [{"2026-10-09": 209.22}, {}])
def test_weekend_no_new_rates_keeps_history(fake_http, rates):
    fake_http.add(SERIES_URL, series(rates))
    previous = {"currency": "GBP", "history": history({"2026-10-08": 209.04, "2026-10-09": 209.22})}
    data = ExchangeSource().fetch(LONDON, previous, NOW)
    assert data["history"] == previous["history"]


def test_currency_change_starts_fresh_history(fake_http):
    fake_http.add(SERIES_URL, series({"2026-10-12": 16.58}))
    previous = {"currency": "GBP", "history": history({"2026-10-09": 209.22})}
    data = ExchangeSource().fetch({"id": "x", "currency": "NOK"}, previous, NOW)
    assert fake_http.calls[0]["url"] == "https://api.frankfurter.dev/v1/2025-10-13.."
    assert data["history"] == history({"2026-10-12": 16.58})


def test_supports_listed_currency_only(fake_http):
    fake_http.add(CURRENCIES_URL, load_fixture("frankfurter_currencies.json"))
    source = ExchangeSource()
    assert source.supports({"currency": "GBP"}) is True
    assert source.supports({"currency": "TWD"}) is False


def test_supports_true_when_currency_list_fails(fake_http):
    fake_http.add(CURRENCIES_URL, FetchError("通信に失敗しました"))
    assert ExchangeSource().supports({"currency": "TWD"}) is True


def test_supports_false_without_currency(fake_http):
    # 通貨一覧を取りに行かずに False（fake_http に経路が無いので、取りに行けば AssertionError）
    assert ExchangeSource().supports({"currency": None}) is False
    assert fake_http.calls == []
