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


def load_destinations(path: Path) -> list[dict]:
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    destinations = []
    seen_ids = set()
    for index, item in enumerate(items):
        missing = [f for f in REQUIRED_FIELDS if f not in item]
        if missing:
            log.warning("行き先 %d 番目を飛ばします：必須項目がありません（%s）", index + 1, ", ".join(missing))
            continue
        if not ID_PATTERN.match(str(item["id"])):
            log.warning("行き先 %r を飛ばします：id は英小文字・数字・-・_ だけにしてください", item["id"])
            continue
        if item["id"] in seen_ids:
            log.warning("行き先 %r を飛ばします：id が重複しています", item["id"])
            continue
        seen_ids.add(item["id"])
        destinations.append(item)
    return destinations
