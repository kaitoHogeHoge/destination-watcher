import json
from datetime import datetime

from fetcher.storage import (
    error_record,
    ok_record,
    read_record,
    unsupported_record,
    write_index,
    write_record,
)
from fetcher.timeutil import JST

NOW = datetime(2026, 10, 13, 6, 0, tzinfo=JST)
EARLIER = datetime(2026, 10, 12, 6, 0, tzinfo=JST)


def test_ok_record_shape():
    r = ok_record("exchange", "frankfurter", {"x": 1}, NOW)
    assert r == {
        "source": "exchange",
        "provider": "frankfurter",
        "status": "ok",
        "updated_at": "2026-10-13T06:00:00+09:00",
        "attempted_at": "2026-10-13T06:00:00+09:00",
        "error": None,
        "data": {"x": 1},
        "data_version": 1,
    }


def test_error_record_keeps_previous_data_and_updated_at():
    prev = ok_record("exchange", "frankfurter", {"x": 1}, EARLIER)
    r = error_record("exchange", "frankfurter", "通信に失敗しました", NOW, prev)
    assert r["status"] == "error"
    assert r["data"] == {"x": 1}
    assert r["updated_at"] == "2026-10-12T06:00:00+09:00"
    assert r["attempted_at"] == "2026-10-13T06:00:00+09:00"
    assert r["error"] == "通信に失敗しました"


def test_error_record_without_previous_has_null_data():
    r = error_record("exchange", "frankfurter", "失敗", NOW, None)
    assert r["data"] is None and r["updated_at"] is None


def test_unsupported_record():
    r = unsupported_record("holidays", NOW)
    assert r["status"] == "unsupported" and r["provider"] is None and r["data"] is None
    assert r["source"] == "holidays"


def test_write_then_read_roundtrip(tmp_path):
    record = ok_record("exchange", "frankfurter", {"city": "ロンドン"}, NOW)
    write_record(tmp_path, "london", record)
    assert read_record(tmp_path, "london", "exchange") == record
    text = (tmp_path / "london" / "exchange.json").read_text(encoding="utf-8")
    assert "ロンドン" in text


def test_read_missing_returns_none(tmp_path):
    assert read_record(tmp_path, "london", "exchange") is None


def test_read_broken_json_returns_none(tmp_path):
    (tmp_path / "london").mkdir()
    (tmp_path / "london" / "exchange.json").write_text("{", encoding="utf-8")
    assert read_record(tmp_path, "london", "exchange") is None


def test_write_index_lists_given_destinations_only(tmp_path):
    (tmp_path / "old").mkdir()
    dests = [
        {"id": "london", "name": "ロンドン", "country": "イギリス", "country_code": "GB", "lat": 1, "lon": 10, "currency": "GBP"},
        {"id": "tromso", "name": "トロムソ", "country": "ノルウェー", "country_code": "NO", "lat": 2, "lon": 20, "currency": "NOK"},
    ]
    sources = [{"name": "exchange", "label": "為替レート"}]
    write_index(tmp_path, dests, sources, NOW)
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert index == {
        "generated_at": "2026-10-13T06:00:00+09:00",
        "destinations": [
            {"id": "london", "name": "ロンドン", "country": "イギリス", "country_code": "GB", "lat": 1, "lon": 10},
            {"id": "tromso", "name": "トロムソ", "country": "ノルウェー", "country_code": "NO", "lat": 2, "lon": 20},
        ],
        "sources": [{"name": "exchange", "label": "為替レート"}],
    }


def test_ok_record_has_data_version():
    assert ok_record("climate", "open-meteo", {}, NOW, data_version=2)["data_version"] == 2
    assert ok_record("climate", "open-meteo", {}, NOW)["data_version"] == 1


def test_error_record_keeps_previous_data_version():
    prev = ok_record("climate", "open-meteo", {"x": 1}, EARLIER, data_version=2)
    assert error_record("climate", "open-meteo", "失敗", NOW, prev)["data_version"] == 2
