import json

import pytest

from fetcher.config import load_destinations

LONDON = {
    "id": "london",
    "name": "ロンドン",
    "country": "イギリス",
    "country_code": "GB",
    "holiday_region": "GB-ENG",
    "mofa_code": "0044",
    "lat": 51.51,
    "lon": -0.13,
    "currency": "GBP",
}


def write(tmp_path, items):
    path = tmp_path / "destinations.json"
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return path


def test_loads_valid_destination(tmp_path):
    dests = load_destinations(write(tmp_path, [LONDON]))
    assert len(dests) == 1
    assert dests[0]["holiday_region"] == "GB-ENG"


def test_skips_entry_missing_required_field(tmp_path):
    broken = {k: v for k, v in LONDON.items() if k != "currency"}
    broken["id"] = "broken"
    dests = load_destinations(write(tmp_path, [broken, LONDON]))
    assert [d["id"] for d in dests] == ["london"]


def test_skips_bad_id_and_duplicate_id(tmp_path):
    bad = {**LONDON, "id": "London City"}
    dup = {**LONDON, "name": "ロンドン2"}
    dests = load_destinations(write(tmp_path, [bad, LONDON, dup]))
    assert [d["name"] for d in dests] == ["ロンドン"]


def test_unreadable_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_destinations(tmp_path / "missing.json")


def test_null_mofa_code_and_currency_allowed(tmp_path):
    dest = {**LONDON, "mofa_code": None, "currency": None}
    assert len(load_destinations(write(tmp_path, [dest]))) == 1


def test_numeric_mofa_code_skipped(tmp_path):
    dest = {**LONDON, "mofa_code": 44}
    assert load_destinations(write(tmp_path, [dest])) == []


def test_non_string_name_or_number_lat_skipped(tmp_path):
    bad_name = {**LONDON, "id": "a", "name": 1}
    bad_lat = {**LONDON, "id": "b", "lat": "51.5"}
    assert load_destinations(write(tmp_path, [bad_name, bad_lat])) == []


def test_non_dict_entry_skipped(tmp_path):
    assert [d["id"] for d in load_destinations(write(tmp_path, ["london", LONDON]))] == ["london"]


def test_top_level_not_list_raises(tmp_path):
    with pytest.raises(ValueError):
        load_destinations(write(tmp_path, {"london": LONDON}))


def test_photo_must_be_string_if_present(tmp_path):
    ok = {**LONDON, "id": "a", "photo": "File:London.jpg"}
    bad = {**LONDON, "id": "b", "photo": 123}
    assert [d["id"] for d in load_destinations(write(tmp_path, [ok, bad]))] == ["a"]
