from datetime import datetime

import pytest

from conftest import Sequence, load_fixture
from fetcher.http import FetchError, NotFoundError
from fetcher.sources.photo import PhotoSource, file_from_url, is_photo_file, strip_html
from fetcher.timeutil import JST

NOW = datetime(2026, 10, 15, 6, 0, tzinfo=JST)
SUMMARY = "https://ja.wikipedia.org/api/rest_v1/page/summary/"
MEDIA = "https://ja.wikipedia.org/api/rest_v1/page/media-list/"
COMMONS = "https://commons.wikimedia.org/w/api.php"


def commons(file="File:London_Skyline_(125508655).jpeg"):
    raw = load_fixture("commons_london.json")
    raw["query"]["pages"][0]["title"] = file
    return raw


def test_is_photo_file():
    assert is_photo_file("File:London_Skyline_(125508655).jpeg")
    assert is_photo_file("File:Tromsø_view.JPG")
    for bad in ["File:Flag_of_Singapore.svg", "File:Singapore_flag.jpg", "File:Coat_of_arms_of_X.jpg",
                "File:Singapore_in_its_region_(zoom).svg", "File:Locator_map.png", "File:Seal_of_X.jpg",
                "File:Majulah_Singapura.ogg", "File:Emblem_of_X.jpg", "File:X_location.jpg", "File:a.gif"]:
        assert not is_photo_file(bad), bad


def test_file_from_thumb_url():
    thumb = ("https://thumb.wikimedia.org/wikipedia/commons/thumb/6/6e/Paris_-_Eiffelturm_und_Marsfeld2.jpg/"
             "3840px-Paris_-_Eiffelturm_und_Marsfeld2.jpg?utm_source=x")
    assert file_from_url(thumb) == "File:Paris_-_Eiffelturm_und_Marsfeld2.jpg"
    original = "https://upload.wikimedia.org/wikipedia/commons/6/67/London_Skyline_%28125508655%29.jpeg?utm=1"
    assert file_from_url(original) == "File:London_Skyline_(125508655).jpeg"
    assert file_from_url("https://example.com/x.jpg") is None


def test_strip_html():
    assert strip_html('<div class="fn"><a href="https://x">Ilya Grigorik</a></div>') == "Ilya Grigorik"
    assert strip_html("<script>alert(1)</script>Taro &amp; Hanako") == "Taro & Hanako"
    assert strip_html("") == ""


def test_uses_summary_image(fake_http):
    fake_http.add(SUMMARY, load_fixture("wiki_summary_london.json"))
    fake_http.add(COMMONS, commons())
    data = PhotoSource().fetch({"id": "london", "name": "ロンドン"}, None, NOW)
    assert data["file"] == "File:London_Skyline_(125508655).jpeg"
    assert data["url"].startswith("https://thumb.wikimedia.org/") and "960px" in data["url"]
    assert data["page"] == "https://commons.wikimedia.org/wiki/File:London_Skyline_(125508655).jpeg"
    assert data["artist"] == "Ilya Grigorik"
    assert data["license"] == "CC BY-SA 3.0"
    commons_call = [c for c in fake_http.calls if c["url"] == COMMONS][0]
    assert commons_call["params"]["titles"] == "File:London_Skyline_(125508655).jpeg"
    assert commons_call["params"]["iiurlwidth"] == 960


def test_skips_flag_and_uses_media_list(fake_http):
    fake_http.add(SUMMARY, load_fixture("wiki_summary_singapore.json"))  # 代表画像は国旗
    fake_http.add(MEDIA, load_fixture("wiki_media_singapore.json"))
    fake_http.add(COMMONS, commons())
    data = PhotoSource().fetch({"id": "singapore", "name": "シンガポール"}, None, NOW)
    assert data["file"] == "File:Merlion_statue,_Merlion_Park,_Singapore_-_20110723.jpg"


def test_uses_config_photo_first(fake_http):
    fake_http.add(COMMONS, commons())
    data = PhotoSource().fetch({"id": "sg", "name": "シンガポール", "photo": "File:Marina_Bay.jpg"}, None, NOW)
    assert data["file"] == "File:Marina_Bay.jpg"
    assert not [c for c in fake_http.calls if c["url"].startswith(SUMMARY)]


def test_no_article_returns_no_photo(fake_http):
    fake_http.add(SUMMARY, NotFoundError("データ元がエラーを返しました（HTTP 404）"))
    fake_http.add(MEDIA, NotFoundError("データ元がエラーを返しました（HTTP 404）"))
    assert PhotoSource().fetch({"id": "x", "name": "存在しない町"}, None, NOW) == {"url": None, "requested": None}


def test_network_failure_is_an_error(fake_http):
    fake_http.add(SUMMARY, FetchError("通信に失敗しました（タイムアウト）"))
    with pytest.raises(FetchError):
        PhotoSource().fetch({"id": "london", "name": "ロンドン"}, None, NOW)


def test_artist_missing_is_unknown(fake_http):
    raw = commons()
    del raw["query"]["pages"][0]["imageinfo"][0]["extmetadata"]["Artist"]
    fake_http.add(SUMMARY, load_fixture("wiki_summary_london.json"))
    fake_http.add(COMMONS, raw)
    assert PhotoSource().fetch({"id": "london", "name": "ロンドン"}, None, NOW)["artist"] == "不明"


def test_non_http_urls_are_dropped(fake_http):
    raw = commons()
    info = raw["query"]["pages"][0]["imageinfo"][0]
    info["thumburl"] = "javascript:alert(1)"
    fake_http.add(SUMMARY, load_fixture("wiki_summary_london.json"))
    fake_http.add(COMMONS, raw)
    assert PhotoSource().fetch({"id": "london", "name": "ロンドン"}, None, NOW) == {"url": None, "requested": None}


def test_photo_source_settings():
    s = PhotoSource()
    assert (s.name, s.provider, s.refresh_days) == ("photo", "wikimedia", 90)


def test_records_requested_override(fake_http):
    fake_http.add(COMMONS, commons())
    data = PhotoSource().fetch({"id": "sg", "name": "シンガポール", "photo": "File:Marina_Bay.jpg"}, None, NOW)
    assert data["requested"] == "File:Marina_Bay.jpg"
    fake_http.add(SUMMARY, load_fixture("wiki_summary_london.json"))
    assert PhotoSource().fetch({"id": "london", "name": "ロンドン"}, None, NOW)["requested"] is None


def test_outdated_when_override_changes():
    source = PhotoSource()
    assert source.is_outdated({"photo": "File:New.jpg"}, {"requested": "File:Old.jpg"}) is True
    assert source.is_outdated({}, {"requested": "File:Old.jpg"}) is True  # 指定を消した
    assert source.is_outdated({"photo": "File:Same.jpg"}, {"requested": "File:Same.jpg"}) is False
    assert source.is_outdated({}, {"url": None}) is False  # 古い形式（requested なし）・指定なし


def test_override_without_file_prefix(fake_http):
    fake_http.add(COMMONS, commons())
    data = PhotoSource().fetch({"id": "sg", "name": "シンガポール", "photo": "Marina_Bay.jpg"}, None, NOW)
    assert data["file"] == "File:Marina_Bay.jpg"


def test_tries_next_candidate_when_commons_has_no_file(fake_http):
    media = {"items": [
        {"type": "image", "title": "ファイル:Local_only.jpg"},
        {"type": "image", "title": "ファイル:Second_photo.jpg"},
    ]}
    missing = {"query": {"pages": [{"title": "File:Local_only.jpg", "missing": True}]}}
    fake_http.add(SUMMARY, load_fixture("wiki_summary_singapore.json"))
    fake_http.add(MEDIA, media)
    fake_http.add(COMMONS, Sequence(missing, commons()))
    data = PhotoSource().fetch({"id": "sg", "name": "シンガポール"}, None, NOW)
    assert data["file"] == "File:Second_photo.jpg"
    titles = [c["params"]["titles"] for c in fake_http.calls if c["url"] == COMMONS]
    assert titles == ["File:Local_only.jpg", "File:Second_photo.jpg"]
