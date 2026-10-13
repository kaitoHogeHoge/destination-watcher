from datetime import datetime

from conftest import load_fixture
from fetcher.sources.forecast import ForecastSource
from fetcher.timeutil import JST

NOW = datetime(2026, 10, 13, 6, 0, tzinfo=JST)
LONDON = {"id": "london", "lat": 51.51, "lon": -0.13}
URL = "https://api.open-meteo.com/v1/forecast"


def test_parses_16_days(fake_http):
    raw = load_fixture("openmeteo_forecast_london.json")
    fake_http.add(URL, raw)
    data = ForecastSource().fetch(LONDON, None, NOW)
    assert data["timezone"] == "Europe/London"
    assert len(data["days"]) == 16
    daily = raw["daily"]
    assert data["days"][0] == {
        "date": daily["time"][0],
        "tmax": daily["temperature_2m_max"][0],
        "tmin": daily["temperature_2m_min"][0],
        "code": daily["weather_code"][0],
        "precip": daily["precipitation_sum"][0],
        "precip_prob": daily["precipitation_probability_max"][0],
    }


def test_null_values_kept_as_none(fake_http):
    fake_http.add(URL, {
        "timezone": "Europe/London",
        "daily": {
            "time": ["2026-10-13"],
            "temperature_2m_max": [None],
            "temperature_2m_min": [10.0],
            "weather_code": [None],
            "precipitation_sum": [0.0],
            "precipitation_probability_max": [None],
        },
    })
    day = ForecastSource().fetch(LONDON, None, NOW)["days"][0]
    assert day["tmax"] is None and day["code"] is None and day["precip_prob"] is None
    assert day["tmin"] == 10.0


def test_requests_expected_params(fake_http):
    fake_http.add(URL, load_fixture("openmeteo_forecast_london.json"))
    ForecastSource().fetch(LONDON, None, NOW)
    assert fake_http.calls[0]["params"] == {
        "latitude": 51.51,
        "longitude": -0.13,
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum,precipitation_probability_max",
        "forecast_days": 16,
        "timezone": "auto",
    }
