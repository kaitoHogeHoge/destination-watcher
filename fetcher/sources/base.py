"""情報ごとの取得部品の共通の約束（設計書 5.1）。"""

from datetime import datetime
from typing import Any


class Source:
    name: str = ""          # 情報の種類（保存ファイル名に使う）
    provider: str = ""      # データ元の名前（画面の出典表示に使う）
    label: str = ""         # 画面の見出し
    refresh_days: int = 0   # 何日ごとに取り直すか（0 = 毎回）
    data_version: int = 1   # 保存する data の形を変えたら上げる（上がると refresh_days に関係なく取り直す）

    def supports(self, dest: dict) -> bool:
        """この行き先に対応しているか。"""
        return True

    def is_outdated(self, dest: dict, previous: Any) -> bool:
        """設定が変わったなどで、refresh_days を待たずに取り直すべきなら True。"""
        return False

    def fetch(self, dest: dict, previous: Any, now: datetime) -> Any:
        """行き先1つ分の情報を取得して返す。previous は前回保存した data（無ければ None）。
        失敗したら例外を投げる（司令塔が受け止める）。"""
        raise NotImplementedError
