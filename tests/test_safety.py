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


def test_supports_false_without_mofa_code():
    assert SafetySource().supports({"mofa_code": None}) is False
    assert SafetySource().supports({"mofa_code": "0044"}) is True


# ---------- 最近のお知らせと関連ページ ----------

import xml.etree.ElementTree as ET  # noqa: E402

from fetcher.sources.safety import parse_links, parse_notices  # noqa: E402


def notices_xml(items: str) -> ET.Element:
    return ET.fromstring(f"<opendata>{items}</opendata>".encode())


def mail(key, date, title):
    return f"<mail><keyCd>{key}</keyCd><leaveDate>{date}</leaveDate><title>{title}</title></mail>"


def spot(date, title, url):
    return f"<wideareaSpot><leaveDate>{date}</leaveDate><title>{title}</title><url>{url}</url></wideareaSpot>"


def test_notices_from_mail_and_spot():
    root = ET.fromstring(load_fixture("mofa_0066L.xml"))
    notices = parse_notices(root, datetime(2026, 10, 13, 6, 0, tzinfo=JST))
    assert notices == [
        {"date": "2026-10-05", "title": "【注意喚起】タイ国内における気象状況について",
         "url": "https://www.anzen.mofa.go.jp/od/ryojiMailDetail.html?keyCd=168122", "kind": "領事メール"},
        {"date": "2026-09-29", "title": "パスポート(旅券)の取扱いにご注意ください（交付に１ヶ月程度かかります）",
         "url": "https://www.anzen.mofa.go.jp/od/ryojiMailDetail.html?keyCd=167944", "kind": "領事メール"},
    ]  # 7/21 の広域情報は30日より前なので入らない


def test_spot_notice_uses_its_url():
    root = notices_xml(spot("2026/10/10 00:00:00", "広域情報", "https://example.jp/spot"))
    assert parse_notices(root, NOW) == [
        {"date": "2026-10-10", "title": "広域情報", "url": "https://example.jp/spot", "kind": "広域・スポット情報"}
    ]


def test_notices_within_30_days_newest_first_max_5():
    items = "".join(mail(i, f"2026/10/{d:02d} 10:00:00", f"t{d}") for i, d in enumerate([1, 9, 3, 12, 5, 7, 11]))
    items += mail(99, "2026/09/12 10:00:00", "old")  # 31日前
    titles = [n["title"] for n in parse_notices(notices_xml(items), NOW)]
    assert titles == ["t12", "t11", "t9", "t7", "t5"]


def test_notice_with_bad_date_or_empty_title_skipped():
    items = mail(1, "不明", "日付なし") + mail(2, "2026/10/10 10:00:00", "") + mail(3, "2026/10/10 10:00:00", "ok")
    assert [n["title"] for n in parse_notices(notices_xml(items), NOW)] == ["ok"]


def test_links_in_order_and_skip_empty():
    root = ET.fromstring(load_fixture("mofa_0066L.xml"))
    assert parse_links(root) == [
        {"label": "安全対策基礎データ", "url": "https://www.anzen.mofa.go.jp/info/pcsafetymeasure_007.html"},
        {"label": "医療事情", "url": "http://www.mofa.go.jp/mofaj/toko/medi/asia/thailand.html"},
        {"label": "テロ・誘拐情勢", "url": "https://www.anzen.mofa.go.jp/info/pcterror_007.html"},
    ]
    assert parse_links(notices_xml("<safetyMeasureUrl/><medicalSituationUrl>https://m</medicalSituationUrl>")) == [
        {"label": "医療事情", "url": "https://m"}
    ]


def test_fetch_includes_notices_and_links(fake_http):
    fake_http.add("https://www.ezairyu.mofa.go.jp/opendata/country/0066L.xml", load_fixture("mofa_0066L.xml"))
    data = SafetySource().fetch({"id": "bkk", "mofa_code": "0066"}, None, NOW)
    assert len(data["notices"]) == 2 and len(data["links"]) == 3
