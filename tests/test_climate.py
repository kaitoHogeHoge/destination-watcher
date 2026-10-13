from datetime import datetime

from conftest import load_fixture
from fetcher.sources.climate import ClimateSource
from fetcher.timeutil import JST

NOW = datetime(2026, 10, 13, 6, 0, tzinfo=JST)
LONDON = {"id": "london", "lat": 51.51, "lon": -0.13}
URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch(fake_http):
    fake_http.add(URL, load_fixture("openmeteo_archive_small.json"))
    return ClimateSource().fetch(LONDON, None, NOW)


def month(data, n):
    return next(m for m in data["months"] if m["month"] == n)


def test_monthly_temperature_mean(fake_http):
    # 1月の日平均気温：2.0, 4.0, 1.0, 3.0（null は除く）→ 2.5
    assert month(fetch(fake_http), 1)["temp"] == 2.5


def test_monthly_precip_is_mean_of_yearly_totals(fake_http):
    # 1月の合計：2016年 = 10.0、2017年 = 15.0（null は除く）→ 平均 12.5
    assert month(fetch(fake_http), 1)["precip"] == 12.5


def test_null_days_ignored(fake_http):
    data = fetch(fake_http)
    assert month(data, 2) == {"month": 2, "temp": 6.0, "precip": 1.5}


def test_month_without_data_is_none(fake_http):
    assert month(fetch(fake_http), 7) == {"month": 7, "temp": None, "precip": None}


def test_always_12_months(fake_http):
    assert [m["month"] for m in fetch(fake_http)["months"]] == list(range(1, 13))


def test_period_label(fake_http):
    assert fetch(fake_http)["period"] == "2016〜2025年の平均"


def test_requests_last_10_full_years(fake_http):
    fetch(fake_http)
    params = fake_http.calls[0]["params"]
    assert params["start_date"] == "2016-01-01"
    assert params["end_date"] == "2025-12-31"
    assert params["daily"] == "temperature_2m_mean,precipitation_sum"
    assert params["latitude"] == 51.51 and params["longitude"] == -0.13
    assert params["timezone"] == "auto"


def test_refreshes_every_30_days():
    assert ClimateSource().refresh_days == 30
