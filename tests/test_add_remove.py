import json

import pytest

from conftest import load_fixture
from fetcher import add as add_module
from fetcher import remove as remove_module
from fetcher.sources import exchange, holidays

GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"


@pytest.fixture(autouse=True)
def clear_caches():
    exchange.supported_currencies.cache_clear()
    holidays.available_countries.cache_clear()
    yield
    exchange.supported_currencies.cache_clear()
    holidays.available_countries.cache_clear()


@pytest.fixture
def files(tmp_path, monkeypatch):
    config = tmp_path / "destinations.json"
    config.write_text("[]\n", encoding="utf-8")
    countries = tmp_path / "countries.json"
    countries.write_text(json.dumps({"TH": {"currency": "THB", "mofa_code": "0066"}}), encoding="utf-8")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    return {"config": config, "countries": countries, "summary": summary, "data": tmp_path / "data"}


def run_add(files, *args):
    return add_module.main(["--config", str(files["config"]), "--countries", str(files["countries"]), *args])


def lists(fake_http):
    fake_http.add("https://api.frankfurter.dev/v1/currencies", load_fixture("frankfurter_currencies.json"))
    fake_http.add("https://date.nager.at/api/v3/AvailableCountries", load_fixture("nager_available.json"))


def test_add_success_writes_config_and_summary(fake_http, files):
    fake_http.add(GEOCODING, load_fixture("geocoding_bangkok.json"))
    lists(fake_http)
    assert run_add(files, "--city", "バンコク") == 0
    config = json.loads(files["config"].read_text(encoding="utf-8"))
    assert [d["id"] for d in config] == ["th-1609350"]
    assert "バンコク（タイ）を追加しました" in files["summary"].read_text(encoding="utf-8")


def test_add_reports_unsupported(fake_http, files):
    fake_http.add(GEOCODING, load_fixture("geocoding_bangkok.json"))
    lists(fake_http)  # Nager.Date の一覧に TH は無い
    run_add(files, "--city", "バンコク")
    assert "対象外の情報：祝日（今後6か月）" in files["summary"].read_text(encoding="utf-8")


def test_add_all_supported_message(fake_http, files):
    paris = {"results": [{"id": 2988507, "name": "パリ", "country": "フランス", "country_code": "FR",
                          "latitude": 48.85, "longitude": 2.35}]}
    fake_http.add(GEOCODING, paris)
    lists(fake_http)
    files["countries"].write_text(json.dumps({"FR": {"currency": "EUR", "mofa_code": "0033"}}), encoding="utf-8")
    run_add(files, "--city", "パリ", "--country", "フランス")
    assert "すべての情報が表示されます" in files["summary"].read_text(encoding="utf-8")


def test_add_not_found_returns_1_and_keeps_file(fake_http, files):
    fake_http.add(GEOCODING, {"generationtime_ms": 0.1})
    assert run_add(files, "--city", "レイキャビク") == 1
    assert files["config"].read_text(encoding="utf-8") == "[]\n"
    summary = files["summary"].read_text(encoding="utf-8")
    assert "『レイキャビク』が見つかりませんでした。英語名（例：Reykjavik）でも試してください" in summary


def test_add_not_found_with_country_mentions_country(fake_http, files):
    fake_http.add(GEOCODING, load_fixture("geocoding_bangkok.json"))
    assert run_add(files, "--city", "バンコク", "--country", "ドイツ") == 1
    assert "『バンコク』（ドイツ）が見つかりませんでした" in files["summary"].read_text(encoding="utf-8")


def test_add_duplicate_returns_1(fake_http, files):
    fake_http.add(GEOCODING, load_fixture("geocoding_bangkok.json"))
    lists(fake_http)
    run_add(files, "--city", "バンコク")
    assert run_add(files, "--city", "バンコク") == 1
    assert "すでに登録されています：バンコク（タイ）" in files["summary"].read_text(encoding="utf-8")


def test_remove_success(files):
    files["config"].write_text(json.dumps([{"id": "th-1609350", "name": "バンコク", "country": "タイ"}]), encoding="utf-8")
    code = remove_module.main(["--name", "バンコク", "--config", str(files["config"]), "--data-dir", str(files["data"])])
    assert code == 0
    assert json.loads(files["config"].read_text(encoding="utf-8")) == []
    assert "バンコク（タイ）を削除しました" in files["summary"].read_text(encoding="utf-8")


def test_remove_not_found_returns_1(files):
    code = remove_module.main(["--name", "バンコク", "--config", str(files["config"]), "--data-dir", str(files["data"])])
    assert code == 1
    assert "『バンコク』は登録されていません" in files["summary"].read_text(encoding="utf-8")
