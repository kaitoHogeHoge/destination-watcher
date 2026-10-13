"""為替レート（Frankfurter）。「1外貨 = 何円」の日ごとの履歴を保存する（設計書 5.2）。"""

import functools
from datetime import date, timedelta

from fetcher import http
from fetcher.sources.base import Source

API = "https://api.frankfurter.dev/v1"
FIRST_FETCH_DAYS = 365


@functools.cache
def supported_currencies() -> frozenset | None:
    """対応通貨の一覧。取れなかったときは None（1回の実行の中で使い回す）。"""
    try:
        return frozenset(http.get_json(f"{API}/currencies"))
    except http.FetchError:
        return None


class ExchangeSource(Source):
    name = "exchange"
    provider = "frankfurter"
    label = "為替レート"

    def supports(self, dest):
        if not dest.get("currency"):
            return False
        currencies = supported_currencies()
        return currencies is None or dest["currency"] in currencies

    def fetch(self, dest, previous, now):
        currency = dest["currency"]
        old = previous["history"] if previous and previous.get("currency") == currency else []
        if old:
            start = old[-1]["date"]
        else:
            start = (now.date() - timedelta(days=FIRST_FETCH_DAYS)).isoformat()

        raw = http.get_json(f"{API}/{start}..", params={"base": currency, "symbols": "JPY"})

        merged = {h["date"]: h["jpy"] for h in old}
        for day, rates in raw.get("rates", {}).items():
            date.fromisoformat(day)  # 日付の形でなければここで例外になる
            merged[day] = rates["JPY"]
        return {
            "currency": currency,
            "history": [{"date": d, "jpy": merged[d]} for d in sorted(merged)],
        }
