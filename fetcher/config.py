"""行き先の設定ファイル（config/destinations.json）の読み込み。

おかしな項目があっても、その行き先だけ飛ばして他は読み込む。
"""

import json
import logging
import re
from pathlib import Path

REQUIRED_FIELDS = ("id", "name", "country", "country_code", "mofa_code", "lat", "lon", "currency")
ID_PATTERN = re.compile(r"^[a-z0-9_-]+$")

log = logging.getLogger(__name__)


STRING_FIELDS = ("id", "name", "country", "country_code")
NUMBER_FIELDS = ("lat", "lon")
NULLABLE_STRING_FIELDS = ("mofa_code", "currency")  # null なら、その情報は「対象外」になる


def _type_problem(item: dict) -> str | None:
    for f in STRING_FIELDS:
        if not isinstance(item[f], str):
            return f"{f} は文字列で書いてください"
    for f in NUMBER_FIELDS:
        if isinstance(item[f], bool) or not isinstance(item[f], (int, float)):
            return f"{f} は数値で書いてください"
    for f in NULLABLE_STRING_FIELDS:
        if item[f] is not None and not isinstance(item[f], str):
            return f"{f} は文字列（\"0044\" のように引用符付き）か null で書いてください"
    return None


def load_destinations(path: Path) -> list[dict]:
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise ValueError("設定ファイルは [ ... ] の形（行き先の並び）で書いてください")
    destinations = []
    seen_ids = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            log.warning("行き先 %d 番目を飛ばします：{ ... } の形になっていません", index + 1)
            continue
        missing = [f for f in REQUIRED_FIELDS if f not in item]
        if missing:
            log.warning("行き先 %d 番目を飛ばします：必須項目がありません（%s）", index + 1, ", ".join(missing))
            continue
        problem = _type_problem(item)
        if problem:
            log.warning("行き先 %d 番目を飛ばします：%s", index + 1, problem)
            continue
        if not ID_PATTERN.match(item["id"]):
            log.warning("行き先 %r を飛ばします：id は英小文字・数字・-・_ だけにしてください", item["id"])
            continue
        if item["id"] in seen_ids:
            log.warning("行き先 %r を飛ばします：id が重複しています", item["id"])
            continue
        seen_ids.add(item["id"])
        destinations.append(item)
    return destinations
