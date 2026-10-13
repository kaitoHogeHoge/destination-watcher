"""取得する情報の一覧。新しい情報を足すときは、部品を作ってここに1行足す。

同じ情報の種類（name）の部品が複数あるときは、上にあるものから順に
「その行き先に対応しているか」を確かめ、最初に対応したものが使われる。
"""

from fetcher.sources.climate import ClimateSource
from fetcher.sources.exchange import ExchangeSource
from fetcher.sources.forecast import ForecastSource
from fetcher.sources.holidays import HolidaysSource
from fetcher.sources.safety import SafetySource

SOURCES = [
    ExchangeSource(),
    ForecastSource(),
    ClimateSource(),
    HolidaysSource(),
    SafetySource(),
]
