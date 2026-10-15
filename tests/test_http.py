import pytest
import requests

from fetcher import http


class FakeResponse:
    def __init__(self, status_code=200, body=b"", json_value=None):
        self.status_code = status_code
        self.content = body
        self._json_value = json_value

    def json(self):
        if self._json_value is None:
            raise ValueError("not json")
        return self._json_value


@pytest.fixture
def calls(monkeypatch):
    """requests.get を偽物に差し替える。responses に積んだものを順に返す。"""
    state = {"responses": [], "calls": []}

    def fake_get(url, params=None, timeout=None, headers=None):
        state["calls"].append({"url": url, "params": params, "timeout": timeout})
        item = state["responses"].pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(http.requests, "get", fake_get)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    return state


def test_get_json_returns_parsed_body(calls):
    calls["responses"] = [FakeResponse(json_value={"a": 1})]
    assert http.get_json("https://example.com") == {"a": 1}


def test_retries_once_then_succeeds(calls):
    calls["responses"] = [requests.Timeout(), FakeResponse(json_value={"ok": True})]
    assert http.get_json("https://example.com") == {"ok": True}
    assert len(calls["calls"]) == 2


def test_raises_fetch_error_after_two_failures(calls):
    calls["responses"] = [FakeResponse(status_code=503), FakeResponse(status_code=503)]
    with pytest.raises(http.FetchError):
        http.get_json("https://example.com")
    assert len(calls["calls"]) == 2


def test_non_json_body_raises_fetch_error(calls):
    calls["responses"] = [FakeResponse(body=b"<html>")]
    with pytest.raises(http.FetchError):
        http.get_json("https://example.com")


def test_passes_timeout_20(calls):
    calls["responses"] = [FakeResponse(json_value={})]
    http.get_json("https://example.com", params={"q": "1"})
    assert calls["calls"][0]["timeout"] == 20
    assert calls["calls"][0]["params"] == {"q": "1"}


def test_client_error_is_not_retried(calls):
    calls["responses"] = [FakeResponse(status_code=404)]
    with pytest.raises(http.FetchError):
        http.get_bytes("https://example.com")
    assert len(calls["calls"]) == 1


def test_get_bytes_returns_raw_body(calls):
    calls["responses"] = [FakeResponse(body="<x>日本</x>".encode())]
    assert http.get_bytes("https://example.com") == "<x>日本</x>".encode()


def test_404_raises_not_found_error(calls):
    calls["responses"] = [FakeResponse(status_code=404)]
    with pytest.raises(http.NotFoundError):
        http.get_json("https://example.com")
    assert issubclass(http.NotFoundError, http.FetchError)


def test_user_agent_has_contact_url():
    assert "github.com/kaitoHogeHoge/destination-watcher" in http.HEADERS["User-Agent"]
