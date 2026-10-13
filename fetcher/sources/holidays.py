"""祝日（Nager.Date）。今日から6か月（183日）先までの祝日（設計書 5.5）。"""

import functools
from datetime import date, timedelta

from fetcher import http
from fetcher.sources.base import Source

API = "https://date.nager.at/api/v3"
WINDOW_DAYS = 183


@functools.cache
def available_countries() -> frozenset | None:
    """対応国の一覧。取れなかったときは None（1回の実行の中で使い回す）。"""
    try:
        return frozenset(c["countryCode"] for c in http.get_json(f"{API}/AvailableCountries"))
    except http.FetchError:
        return None


def _applies(holiday: dict, region: str | None) -> bool:
    """全国共通の祝日か、指定した地域の祝日なら True。"""
    if holiday.get("global"):
        return True
    return region is not None and region in (holiday.get("counties") or [])


class HolidaysSource(Source):
    name = "holidays"
    provider = "nager-date"
    label = "祝日（今後6か月）"

    def supports(self, dest):
        countries = available_countries()
        return countries is None or dest["country_code"] in countries

    def fetch(self, dest, previous, now):
        start = now.date()
        end = start + timedelta(days=WINDOW_DAYS)
        region = dest.get("holiday_region")

        found = []
        for year in sorted({start.year, end.year}):
            for h in http.get_json(f"{API}/PublicHolidays/{year}/{dest['country_code']}"):
                day = date.fromisoformat(h["date"])
                if start <= day <= end and _applies(h, region):
                    found.append({"date": h["date"], "local_name": h["localName"], "name": h["name"]})
        found.sort(key=lambda h: h["date"])
        return {"holidays": found}
