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
