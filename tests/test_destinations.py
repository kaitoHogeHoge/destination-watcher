import json

import pytest

from conftest import load_fixture
from fetcher.destinations import (
    DestinationError,
    add_destination,
    make_destination,
    pick_result,
    remove_destination,
    search_city,
)

GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
COUNTRIES = {"TH": {"currency": "THB", "mofa_code": "0066"}}

PARIS_FR = {"id": 2988507, "name": "パリ", "country": "フランス", "country_code": "FR",
            "latitude": 48.85341, "longitude": 2.3488}
PARIS_US = {"id": 4717560, "name": "パリ", "country": "アメリカ合衆国", "country_code": "US",
            "latitude": 33.66094, "longitude": -95.55551}

LONDON = {
    "id": "london", "name": "ロンドン", "country": "イギリス", "country_code": "GB",
    "holiday_region": "GB-ENG", "mofa_code": "0044", "lat": 51.51, "lon": -0.13, "currency": "GBP",
}


def write_config(tmp_path, items):
    path = tmp_path / "destinations.json"
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_config(path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- 地名検索 ----------

def test_search_city_returns_results(fake_http):
    fake_http.add(GEOCODING, load_fixture("geocoding_bangkok.json"))
    results = search_city("バンコク")
    assert results[0]["country_code"] == "TH"
    assert fake_http.calls[0]["params"] == {"name": "バンコク", "count": 10, "language": "ja"}


def test_search_city_no_results_key(fake_http):
    fake_http.add(GEOCODING, {"generationtime_ms": 0.1})
    assert search_city("zzqqxx") == []


def test_pick_first_without_country():
    assert pick_result([PARIS_US, PARIS_FR], None) is PARIS_US


def test_pick_with_country_filter():
    assert pick_result([PARIS_US, PARIS_FR], "フランス") is PARIS_FR
    assert pick_result([PARIS_US, PARIS_FR], "アメリカ") is PARIS_US  # 入力が国名の一部でもよい


def test_pick_none():
    assert pick_result([], None) is None
    assert pick_result([PARIS_FR], "ドイツ") is None


# ---------- 設定の1件分 ----------

def test_make_destination_known_country():
    result = load_fixture("geocoding_bangkok.json")["results"][0]
    assert make_destination(result, COUNTRIES) == {
        "id": "th-1609350",
        "name": "バンコク",
        "country": "タイ",
        "country_code": "TH",
        "mofa_code": "0066",
        "lat": round(result["latitude"], 2),
        "lon": round(result["longitude"], 2),
        "currency": "THB",
    }


def test_make_destination_unknown_country():
    dest = make_destination(PARIS_FR, COUNTRIES)
    assert dest["id"] == "fr-2988507"
    assert dest["currency"] is None and dest["mofa_code"] is None


# ---------- 追加 ----------

def test_add_appends_and_keeps_existing_fields(tmp_path):
    path = write_config(tmp_path, [LONDON])
    new = make_destination(PARIS_FR, COUNTRIES)
    add_destination(path, new)
    assert read_config(path) == [LONDON, new]
    text = path.read_text(encoding="utf-8")
    assert "パリ" in text and "GB-ENG" in text and text.endswith("\n")


def test_add_duplicate_id(tmp_path):
    path = write_config(tmp_path, [LONDON])
    before = path.read_text(encoding="utf-8")
    with pytest.raises(DestinationError, match="すでに登録されています：ロンドン（イギリス）"):
        add_destination(path, {**LONDON, "name": "別名"})
    assert path.read_text(encoding="utf-8") == before


def test_add_duplicate_name_and_country(tmp_path):
    path = write_config(tmp_path, [LONDON])
    before = path.read_text(encoding="utf-8")
    with pytest.raises(DestinationError, match="すでに登録されています"):
        add_destination(path, {**LONDON, "id": "gb-2643743"})
    assert path.read_text(encoding="utf-8") == before


# ---------- 削除 ----------

def make_data_dir(tmp_path, *ids):
    data = tmp_path / "data"
    for dest_id in ids:
        (data / dest_id).mkdir(parents=True)
        (data / dest_id / "exchange.json").write_text("{}", encoding="utf-8")
    return data


def test_remove_by_name_deletes_data_dir(tmp_path):
    paris = make_destination(PARIS_FR, COUNTRIES)
    path = write_config(tmp_path, [LONDON, paris])
    data = make_data_dir(tmp_path, "london", paris["id"])
    removed = remove_destination(path, data, "パリ")
    assert removed["id"] == "fr-2988507"
    assert read_config(path) == [LONDON]
    assert not (data / "fr-2988507").exists()
    assert (data / "london" / "exchange.json").exists()


def test_remove_by_id(tmp_path):
    path = write_config(tmp_path, [LONDON])
    data = make_data_dir(tmp_path)
    assert remove_destination(path, data, "london")["name"] == "ロンドン"
    assert read_config(path) == []


def test_remove_unknown_lists_registered(tmp_path):
    path = write_config(tmp_path, [LONDON])
    with pytest.raises(DestinationError, match="『パリ』は登録されていません。登録中：ロンドン"):
        remove_destination(path, make_data_dir(tmp_path), "パリ")


def test_remove_ambiguous(tmp_path):
    a = make_destination(PARIS_FR, COUNTRIES)
    b = make_destination(PARIS_US, COUNTRIES)
    path = write_config(tmp_path, [a, b])
    before = path.read_text(encoding="utf-8")
    with pytest.raises(DestinationError, match="同じ名前の行き先が複数あります。id で指定してください：fr-2988507、us-4717560"):
        remove_destination(path, make_data_dir(tmp_path), "パリ")
    assert path.read_text(encoding="utf-8") == before


def test_remove_rejects_unsafe_id(tmp_path):
    evil = {**LONDON, "id": "../outside", "name": "悪い例"}
    path = write_config(tmp_path, [evil])
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(DestinationError):
        remove_destination(path, make_data_dir(tmp_path), "悪い例")
    assert outside.exists()
