"""天気予報（Open-Meteo）。今日から16日分の日ごとの予報（設計書 5.3）。"""

from fetcher import http
from fetcher.sources.base import Source

API = "https://api.open-meteo.com/v1/forecast"

# 保存する名前 → Open-Meteo の項目名
FIELDS = {
    "tmax": "temperature_2m_max",
    "tmin": "temperature_2m_min",
    "code": "weather_code",
    "precip": "precipitation_sum",
    "precip_prob": "precipitation_probability_max",
}
SUN_FIELDS = ["sunrise", "sunset", "daylight_duration"]


def _sun(sunrise: str | None, sunset: str | None, daylight_seconds) -> dict:
    """日の出・日の入り（現地の HH:MM）と昼の長さ（時間）。

    極夜（昼の長さ 0）・白夜（24時間）の日は、API が 00:00 を返すので時刻は None にする。
    """
    hours = round(daylight_seconds / 3600, 1) if isinstance(daylight_seconds, (int, float)) else None
    polar = hours is not None and (hours <= 0 or hours >= 24)

    def hhmm(value):
        return value[11:16] if isinstance(value, str) and len(value) >= 16 and not polar else None

    return {"sunrise": hhmm(sunrise), "sunset": hhmm(sunset), "daylight_h": hours}


class ForecastSource(Source):
    name = "forecast"
    provider = "open-meteo"
    label = "天気予報（16日間）"

    def fetch(self, dest, previous, now):
        raw = http.get_json(API, params={
            "latitude": dest["lat"],
            "longitude": dest["lon"],
            "daily": ",".join([*FIELDS.values(), *SUN_FIELDS]),
            "forecast_days": 16,
            "timezone": "auto",
        })
        daily = raw["daily"]
        days = []
        for i, day in enumerate(daily["time"]):
            item = {"date": day}
            for key, field in FIELDS.items():
                item[key] = daily[field][i]
            sun = [daily.get(f, [None] * len(daily["time"]))[i] for f in SUN_FIELDS]
            item.update(_sun(*sun))
            days.append(item)
        return {"timezone": raw.get("timezone"), "days": days}
