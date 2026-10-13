from datetime import datetime, timedelta

import pytest

from conftest import load_fixture
from fetcher.sources.safety import SafetySource, apply_change, parse_safety
from fetcher.timeutil import JST

NOW = datetime(2026, 10, 13, 6, 0, tzinfo=JST)

NESTED_ONLY = """<?xml version="1.0" encoding="UTF-8"?>
<opendata lastModified="2026/10/13 14:00:00">
  <country countryCd="154"><cd>0044</cd></country>
  <riskLevel4>0</riskLevel4><riskLevel3>0</riskLevel3><riskLevel2>0</riskLevel2><riskLevel1>0</riskLevel1>
  <infectionLevel4>0</infectionLevel4><infectionLevel3>0</infectionLevel3>
  <infectionLevel2>0</infectionLevel2><infectionLevel1>0</infectionLevel1>
  <riskTitle/>
  <area><riskLevel4>1</riskLevel4><infectionLevel2>1</infectionLevel2></area>
</opendata>""".encode()

MISSING = """<?xml version="1.0" encoding="UTF-8"?>
<opendata lastModified="2026/10/13 14:00:00"><country countryCd="154"/></opendata>""".encode()


def test_uk_level_0():
    result = parse_safety(load_fixture("mofa_0044L.xml"))
    assert result["level"] == 0 and result["infection_level"] == 0
    assert result["title"] == ""
    assert result["mofa_updated"] == "2026/10/13 14:37:56"


def test_thailand_level_3():
    result = parse_safety(load_fixture("mofa_0066L.xml"))
    assert result["level"] == 3
    assert result["title"].startswith("タイの危険情報")


def test_url_is_country_safety_page():
    assert parse_safety(load_fixture("mofa_0044L.xml"))["url"] == (
        "https://www.anzen.mofa.go.jp/info/pcinfectionspothazardinfo_154.html"
    )
    assert parse_safety(load_fixture("mofa_0066L.xml"))["url"] == (
        "https://www.anzen.mofa.go.jp/info/pcinfectionspothazardinfo_007.html"
    )


def test_uses_top_level_only():
    result = parse_safety(NESTED_ONLY)
    assert result["level"] == 0 and result["infection_level"] == 0


def test_missing_risk_fields_raises():
    with pytest.raises(ValueError, match="外務省データの形式が想定と違います"):
        parse_safety(MISSING)


def current(level=1, infection=0):
    return {"level": level, "infection_level": infection, "title": "", "url": "", "mofa_updated": ""}


def test_first_time_not_changed():
    result = apply_change(current(), None, NOW)
    assert result["changed"] is False
    assert result["changed_at"] is None and result["previous_level"] is None
    assert result["previous_infection_level"] is None


def test_level_change_detected():
    previous = apply_change(current(level=1), None, NOW - timedelta(days=1))
    result = apply_change(current(level=2), previous, NOW)
    assert result["changed"] is True
    assert result["previous_level"] == 1
    assert result["previous_infection_level"] == 0
    assert result["changed_at"] == "2026-10-13T06:00:00+09:00"


def test_infection_level_change_detected():
    previous = apply_change(current(infection=0), None, NOW - timedelta(days=1))
    assert apply_change(current(infection=2), previous, NOW)["changed"] is True


def test_change_flag_lasts_7_days():
    first = apply_change(current(level=1), None, NOW - timedelta(days=1))
    changed = apply_change(current(level=2), first, NOW)
    day6 = apply_change(current(level=2), changed, NOW + timedelta(days=6))
    day8 = apply_change(current(level=2), day6, NOW + timedelta(days=8))
    assert day6["changed"] is True and day6["changed_at"] == changed["changed_at"]
    assert day8["changed"] is False and day8["changed_at"] == changed["changed_at"]
    assert day8["previous_level"] == 1


def test_fetch_uses_light_xml_and_previous(fake_http):
    fake_http.add("https://www.ezairyu.mofa.go.jp/opendata/country/0066L.xml", load_fixture("mofa_0066L.xml"))
    previous = apply_change(current(level=2), None, NOW - timedelta(days=1))
    data = SafetySource().fetch({"id": "bkk", "mofa_code": "0066"}, previous, NOW)
    assert data["level"] == 3 and data["changed"] is True and data["previous_level"] == 2


def test_mofa_code_change_not_reported_as_change():
    previous = apply_change({**current(level=0), "mofa_code": "0044"}, None, NOW - timedelta(days=1))
    result = apply_change({**current(level=3), "mofa_code": "0066"}, previous, NOW)
    assert result["changed"] is False and result["previous_level"] is None


def test_broken_changed_at_counts_as_not_changed():
    previous = {**current(level=1), "changed": True, "changed_at": "2026-10-10T06:00:00",
                "previous_level": 0, "previous_infection_level": 0}
    result = apply_change(current(level=1), previous, NOW)
    assert result["changed"] is False


def test_fetch_stores_mofa_code(fake_http):
    fake_http.add("https://www.ezairyu.mofa.go.jp/opendata/country/0044L.xml", load_fixture("mofa_0044L.xml"))
    data = SafetySource().fetch({"id": "london", "mofa_code": "0044"}, None, NOW)
    assert data["mofa_code"] == "0044"
