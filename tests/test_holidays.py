from datetime import datetime

import pytest

from conftest import load_fixture
from fetcher.http import FetchError
from fetcher.sources import holidays
from fetcher.sources.holidays import HolidaysSource
from fetcher.timeutil import JST

NOW = datetime(2026, 10, 13, 6, 0, tzinfo=JST)
API = "https://date.nager.at/api/v3"
LONDON = {"id": "london", "country_code": "GB", "holiday_region": "GB-ENG"}

GB_2027 = [
    {"date": "2027-01-01", "localName": "New Year's Day", "name": "New Year's Day",
     "global": False, "counties": ["GB-ENG", "GB-NIR", "GB-SCT", "GB-WLS"]},
    {"date": "2027-01-04", "localName": "2 January", "name": "2 January", "global": False, "counties": ["GB-SCT"]},
    {"date": "2027-03-26", "localName": "Good Friday", "name": "Good Friday", "global": True, "counties": None},
    {"date": "2027-05-03", "localName": "Early May Bank Holiday", "name": "Early May Bank Holiday",
     "global": True, "counties": None},
]


@pytest.fixture(autouse=True)
def clear_cache():
    holidays.available_countries.cache_clear()
    yield
    holidays.available_countries.cache_clear()


@pytest.fixture
def gb(fake_http):
    fake_http.add(f"{API}/PublicHolidays/2026/GB", load_fixture("nager_gb_2026.json"))
    fake_http.add(f"{API}/PublicHolidays/2027/GB", GB_2027)
    return fake_http


def dates(data):
    return [h["date"] for h in data["holidays"]]


def test_filters_to_england_for_gb_eng(gb):
    data = HolidaysSource().fetch(LONDON, None, NOW)
    assert "2026-11-30" not in dates(data)  # Saint Andrew's Day（スコットランドのみ）
    assert "2027-01-04" not in dates(data)  # 2 January（スコットランドのみ）
    assert "2027-01-01" in dates(data)      # 元日（イングランドを含む）
    assert "2026-12-25" in dates(data)      # クリスマス（全国）


def test_without_region_only_global(gb):
    data = HolidaysSource().fetch({"id": "x", "country_code": "GB"}, None, NOW)
    assert dates(data) == ["2026-12-25", "2026-12-28", "2027-03-26"]


def test_window_is_today_to_183_days(gb):
    data = HolidaysSource().fetch(LONDON, None, NOW)
    assert dates(data) == ["2026-12-25", "2026-12-28", "2027-01-01", "2027-03-26"]
    assert "2027-05-03" not in dates(data)  # 183日より先
    assert "2026-08-31" not in dates(data)  # 過去


def test_keeps_local_and_english_names(gb):
    data = HolidaysSource().fetch(LONDON, None, NOW)
    assert data["holidays"][0] == {"date": "2026-12-25", "local_name": "Christmas Day", "name": "Christmas Day"}


def test_fetches_two_years_when_window_crosses_new_year(gb):
    HolidaysSource().fetch(LONDON, None, NOW)
    assert [c["url"] for c in gb.calls] == [f"{API}/PublicHolidays/2026/GB", f"{API}/PublicHolidays/2027/GB"]


def test_fetches_one_year_when_window_inside_year(fake_http):
    fake_http.add(f"{API}/PublicHolidays/2026/GB", load_fixture("nager_gb_2026.json"))
    HolidaysSource().fetch(LONDON, None, datetime(2026, 2, 1, 6, 0, tzinfo=JST))
    assert len(fake_http.calls) == 1


def test_supports_uses_available_countries(fake_http):
    fake_http.add(f"{API}/AvailableCountries", load_fixture("nager_available.json"))
    source = HolidaysSource()
    assert source.supports({"country_code": "GB"}) is True
    assert source.supports({"country_code": "TH"}) is False


def test_supports_true_when_list_fails(fake_http):
    fake_http.add(f"{API}/AvailableCountries", FetchError("通信に失敗しました"))
    assert HolidaysSource().supports({"country_code": "TH"}) is True
