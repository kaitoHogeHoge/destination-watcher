import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    path = FIXTURES / name
    if name.endswith(".json"):
        return json.loads(path.read_text(encoding="utf-8"))
    return path.read_bytes()


class FakeHttp:
    """fetcher.http の get_json / get_bytes を差し替える偽物。

    routes に「URL の先頭部分 → 返す値（または例外）」を登録する。
    呼ばれた URL と params は calls に記録する。
    """

    def __init__(self):
        self.routes = []
        self.calls = []

    def add(self, url_prefix, value):
        self.routes.append((url_prefix, value))

    def _lookup(self, url, params):
        self.calls.append({"url": url, "params": params})
        for prefix, value in self.routes:
            if url.startswith(prefix):
                if isinstance(value, Exception):
                    raise value
                return value
        raise AssertionError(f"想定していない URL: {url}")

    def get_json(self, url, params=None):
        return self._lookup(url, params)

    def get_bytes(self, url, params=None):
        return self._lookup(url, params)


@pytest.fixture
def fake_http(monkeypatch):
    from fetcher import http

    fake = FakeHttp()
    monkeypatch.setattr(http, "get_json", fake.get_json)
    monkeypatch.setattr(http, "get_bytes", fake.get_bytes)
    return fake
