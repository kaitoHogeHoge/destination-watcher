import json
from datetime import datetime, timedelta

import pytest

from fetcher import main as main_module
from fetcher.http import FetchError
from fetcher.runner import Summary, run
from fetcher.sources.base import Source
from fetcher.storage import ok_record, read_record, write_record
from fetcher.timeutil import JST

NOW = datetime(2026, 10, 13, 6, 0, tzinfo=JST)
LONDON = {"id": "london", "name": "ロンドン", "country": "イギリス"}
TROMSO = {"id": "tromso", "name": "トロムソ", "country": "ノルウェー"}


class FakeSource(Source):
    def __init__(self, name, provider="fake", result=None, error=None, supported=True, refresh_days=0):
        self.name = name
        self.provider = provider
        self.label = name
        self.refresh_days = refresh_days
        self.result = result
        self.error = error
        self.supported = supported
        self.calls = []

    def supports(self, dest):
        return self.supported

    def fetch(self, dest, previous, now):
        self.calls.append({"dest": dest["id"], "previous": previous})
        if self.error:
            raise self.error
        return self.result


def test_one_failing_source_does_not_stop_others(tmp_path):
    a = FakeSource("a", error=RuntimeError("壊れた"))
    b = FakeSource("b", result={"v": 1})
    summary = run([LONDON], [a, b], tmp_path, NOW)
    assert read_record(tmp_path, "london", "a")["status"] == "error"
    assert read_record(tmp_path, "london", "b")["status"] == "ok"
    assert summary == Summary(ok=1, error=1, unsupported=0, kept=0)


def test_error_message_is_saved(tmp_path):
    run([LONDON], [FakeSource("a", error=FetchError("通信に失敗しました"))], tmp_path, NOW)
    assert read_record(tmp_path, "london", "a")["error"] == "通信に失敗しました"


def test_unexpected_error_message_includes_type(tmp_path):
    run([LONDON], [FakeSource("a", error=KeyError("rates"))], tmp_path, NOW)
    assert read_record(tmp_path, "london", "a")["error"] == "KeyError: 'rates'"


def test_unsupported_when_no_candidate_supports(tmp_path):
    summary = run([LONDON], [FakeSource("a", supported=False)], tmp_path, NOW)
    assert read_record(tmp_path, "london", "a")["status"] == "unsupported"
    assert summary == Summary(ok=0, error=0, unsupported=1, kept=0)


def test_second_provider_used_when_first_unsupported(tmp_path):
    first = FakeSource("a", provider="first", supported=False, result={"v": 1})
    second = FakeSource("a", provider="second", result={"v": 2})
    run([LONDON], [first, second], tmp_path, NOW)
    record = read_record(tmp_path, "london", "a")
    assert record["provider"] == "second" and record["data"] == {"v": 2}
    assert first.calls == []


def test_refresh_days_skips_recent_ok(tmp_path):
    write_record(tmp_path, "london", ok_record("a", "fake", {"old": True}, NOW - timedelta(days=10)))
    source = FakeSource("a", result={"new": True}, refresh_days=30)
    summary = run([LONDON], [source], tmp_path, NOW)
    assert source.calls == []
    assert summary.kept == 1
    assert read_record(tmp_path, "london", "a")["data"] == {"old": True}


def test_refresh_days_refetches_when_old_enough(tmp_path):
    write_record(tmp_path, "london", ok_record("a", "fake", {"old": True}, NOW - timedelta(days=30)))
    source = FakeSource("a", result={"new": True}, refresh_days=30)
    run([LONDON], [source], tmp_path, NOW)
    assert len(source.calls) == 1


def test_refresh_days_refetches_after_error(tmp_path):
    prev = ok_record("a", "fake", {"old": True}, NOW - timedelta(days=10))
    prev["status"] = "error"
    write_record(tmp_path, "london", prev)
    source = FakeSource("a", result={"new": True}, refresh_days=30)
    run([LONDON], [source], tmp_path, NOW)
    assert len(source.calls) == 1


def test_previous_data_passed_to_fetch(tmp_path):
    write_record(tmp_path, "london", ok_record("a", "fake", {"old": True}, NOW - timedelta(days=1)))
    source = FakeSource("a", result={"new": True})
    run([LONDON], [source], tmp_path, NOW)
    assert source.calls[0]["previous"] == {"old": True}


def test_index_written_with_current_destinations(tmp_path):
    run([TROMSO, LONDON], [FakeSource("a", result={})], tmp_path, NOW)
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert [d["id"] for d in index["destinations"]] == ["tromso", "london"]
    assert index["sources"] == [{"name": "a", "label": "a"}]


def test_index_lists_each_source_name_once(tmp_path):
    sources = [FakeSource("a", provider="p1", supported=False), FakeSource("a", provider="p2", result={})]
    run([LONDON], sources, tmp_path, NOW)
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert index["sources"] == [{"name": "a", "label": "a"}]


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "destinations.json"
    dest = {**LONDON, "country_code": "GB", "mofa_code": "0044", "lat": 1, "lon": 2, "currency": "GBP"}
    path.write_text(json.dumps([dest]), encoding="utf-8")
    return path


def test_main_returns_1_when_all_failed(monkeypatch, tmp_path, config_file):
    monkeypatch.setattr(main_module, "SOURCES", [FakeSource("a", error=RuntimeError("x"))])
    assert main_module.main(["--config", str(config_file), "--data-dir", str(tmp_path / "data")]) == 1


def test_main_returns_0_when_partly_failed(monkeypatch, tmp_path, config_file):
    sources = [FakeSource("a", error=RuntimeError("x")), FakeSource("b", result={})]
    monkeypatch.setattr(main_module, "SOURCES", sources)
    assert main_module.main(["--config", str(config_file), "--data-dir", str(tmp_path / "data")]) == 0


def test_main_returns_1_when_config_missing(tmp_path):
    assert main_module.main(["--config", str(tmp_path / "none.json"), "--data-dir", str(tmp_path)]) == 1


class BrokenSupportsSource(FakeSource):
    def supports(self, dest):
        raise RuntimeError("一覧が壊れている")


def test_broken_supports_check_still_fetches(tmp_path):
    source = BrokenSupportsSource("a", result={"v": 1})
    summary = run([LONDON], [source, FakeSource("b", result={})], tmp_path, NOW)
    assert read_record(tmp_path, "london", "a")["status"] == "ok"
    assert summary.ok == 2
