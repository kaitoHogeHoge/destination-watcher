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
    first = {k: v for k, v in data["days"][0].items() if k not in ("sunrise", "sunset", "sunset_next_day", "daylight_h")}
    assert first == {
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
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum,precipitation_probability_max,"
                 "sunrise,sunset,daylight_duration",
        "forecast_days": 16,
        "timezone": "auto",
    }


def sun_response(sunrise, sunset, daylight):
    return {
        "timezone": "Europe/Oslo",
        "daily": {
            "time": ["2026-10-13"], "temperature_2m_max": [5.0], "temperature_2m_min": [1.0],
            "weather_code": [3], "precipitation_sum": [0.0], "precipitation_probability_max": [10],
            "sunrise": [sunrise], "sunset": [sunset], "daylight_duration": [daylight],
        },
    }


def test_parses_sun_times(fake_http):
    fake_http.add(URL, sun_response("2026-10-13T07:50", "2026-10-13T17:08", 33464.91))
    day = ForecastSource().fetch(LONDON, None, NOW)["days"][0]
    assert (day["sunrise"], day["sunset"], day["daylight_h"]) == ("07:50", "17:08", 9.3)


def test_polar_night_values(fake_http):
    fake_http.add(URL, sun_response("2026-12-20T00:00", "2026-12-20T00:00", 0.0))
    day = ForecastSource().fetch(LONDON, None, NOW)["days"][0]
    assert (day["sunrise"], day["sunset"], day["daylight_h"]) == (None, None, 0.0)


def test_midnight_sun_values(fake_http):
    fake_http.add(URL, sun_response("2026-06-20T00:00", "2026-06-21T00:00", 86400.0))
    day = ForecastSource().fetch(LONDON, None, NOW)["days"][0]
    assert (day["sunrise"], day["sunset"], day["daylight_h"]) == (None, None, 24.0)


def test_missing_sun_fields(fake_http):
    raw = sun_response(None, None, None)
    for key in ("sunrise", "sunset", "daylight_duration"):
        del raw["daily"][key]
    fake_http.add(URL, raw)
    day = ForecastSource().fetch(LONDON, None, NOW)["days"][0]
    assert (day["sunrise"], day["sunset"], day["daylight_h"]) == (None, None, None)


def test_sunset_after_midnight_marked_next_day(fake_http):
    # 白夜の始まりの頃：日の入りが翌日の0時台になる
    fake_http.add(URL, sun_response("2026-05-15T01:10", "2026-05-16T00:40", 84600.0))
    day = ForecastSource().fetch(LONDON, None, NOW)["days"][0]
    day["date"] = "2026-05-15"
    assert (day["sunrise"], day["sunset"], day["sunset_next_day"]) == ("01:10", "00:40", True)


def test_normal_sunset_not_next_day(fake_http):
    fake_http.add(URL, sun_response("2026-10-13T07:50", "2026-10-13T17:08", 33464.91))
    assert ForecastSource().fetch(LONDON, None, NOW)["days"][0]["sunset_next_day"] is False
