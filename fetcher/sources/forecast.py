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


class ForecastSource(Source):
    name = "forecast"
    provider = "open-meteo"
    label = "天気予報（16日間）"

    def fetch(self, dest, previous, now):
        raw = http.get_json(API, params={
            "latitude": dest["lat"],
            "longitude": dest["lon"],
            "daily": ",".join(FIELDS.values()),
            "forecast_days": 16,
            "timezone": "auto",
        })
        daily = raw["daily"]
        days = []
        for i, day in enumerate(daily["time"]):
            item = {"date": day}
            for key, field in FIELDS.items():
                item[key] = daily[field][i]
            days.append(item)
        return {"timezone": raw.get("timezone"), "days": days}
