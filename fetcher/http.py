"""外部 API との通信。すべての通信はここを通す。

- タイムアウトは20秒
- 通信エラー・サーバー側のエラー（500番台・429）のときだけ、2秒待って1回再試行する
- 失敗したら日本語のメッセージ付きの FetchError を投げる
"""

import time
from typing import Any

import requests

TIMEOUT_SECONDS = 20
RETRY_WAIT_SECONDS = 2
HEADERS = {"User-Agent": "destination-watcher"}


class FetchError(Exception):
    """取得に失敗したことを表す。メッセージは画面にそのまま出せる日本語。"""


def _is_retryable_status(status: int) -> bool:
    return status >= 500 or status == 429


def _get(url: str, params: dict | None) -> requests.Response:
    last_error = "不明なエラー"
    for attempt in range(2):
        if attempt > 0:
            time.sleep(RETRY_WAIT_SECONDS)
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS, headers=HEADERS)
        except requests.Timeout:
            last_error = "通信に失敗しました（タイムアウト）"
            continue
        except requests.RequestException as e:
            last_error = f"通信に失敗しました（{type(e).__name__}）"
            continue
        if response.status_code < 400:
            return response
        last_error = f"データ元がエラーを返しました（HTTP {response.status_code}）"
        if not _is_retryable_status(response.status_code):
            break
    raise FetchError(last_error)


def get_json(url: str, params: dict | None = None) -> Any:
    response = _get(url, params)
    try:
        return response.json()
    except ValueError:
        raise FetchError("データ元の応答が JSON ではありません") from None


def get_bytes(url: str, params: dict | None = None) -> bytes:
    return _get(url, params).content
