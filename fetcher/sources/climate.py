"""月ごとの気候（Open-Meteo 過去データ）。直近10年の月平均気温と月降水量（設計書 5.4）。"""

from collections import defaultdict
from statistics import mean

from fetcher import http
from fetcher.sources.base import Source

API = "https://archive-api.open-meteo.com/v1/archive"
YEARS = 10


def _round(value, digits=1):
    return None if value is None else round(value, digits)


class ClimateSource(Source):
    name = "climate"
    provider = "open-meteo"
    label = "月ごとの気候"
    refresh_days = 30
    data_version = 2  # 2：昼の長さ（daylight）を追加
    DAILY = "temperature_2m_mean,precipitation_sum,daylight_duration"

    def fetch(self, dest, previous, now):
        first_year = now.year - YEARS
        last_year = now.year - 1
        raw = http.get_json(API, params={
            "latitude": dest["lat"],
            "longitude": dest["lon"],
            "start_date": f"{first_year}-01-01",
            "end_date": f"{last_year}-12-31",
            "daily": self.DAILY,
            "timezone": "auto",
        })
        daily = raw["daily"]

        temps = defaultdict(list)          # 月 → 日平均気温の一覧
        daylights = defaultdict(list)      # 月 → 昼の長さ（時間）の一覧
        daylight_values = daily.get("daylight_duration") or [None] * len(daily["time"])
        precip_totals = defaultdict(float)  # (年, 月) → その月の合計降水量
        for day, temp, precip, light in zip(
            daily["time"], daily["temperature_2m_mean"], daily["precipitation_sum"], daylight_values
        ):
            year, month = int(day[:4]), int(day[5:7])
            if light is not None:
                daylights[month].append(light / 3600)
            if temp is not None:
                temps[month].append(temp)
            if precip is not None:
                precip_totals[(year, month)] += precip

        months = []
        for month in range(1, 13):
            yearly = [total for (_, m), total in precip_totals.items() if m == month]
            months.append({
                "month": month,
                "temp": _round(mean(temps[month])) if temps[month] else None,
                "precip": _round(mean(yearly)) if yearly else None,
                "daylight": _round(mean(daylights[month])) if daylights[month] else None,
            })
        return {"period": f"{first_year}〜{last_year}年の平均", "months": months}
