"""海外安全情報（外務省 海外安全情報オープンデータ）。危険レベルと、その変化（設計書 5.6）。"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from fetcher import http
from fetcher.sources.base import Source
from fetcher.timeutil import iso

API = "https://www.ezairyu.mofa.go.jp/opendata/country"
COUNTRY_PAGE = "https://www.anzen.mofa.go.jp/info/pcinfectionspothazardinfo_{code}.html"
CHANGED_DAYS = 7


def _max_level(root: ET.Element, prefix: str) -> int:
    """ルート直下の {prefix}1〜4 のうち、値が 1 の最大の数字（無ければ 0）。

    XML の中には地域ごとの値も入れ子で入っているため、ルート直下だけを見る。
    """
    found = [root.find(f"{prefix}{n}") for n in range(1, 5)]
    if all(e is None for e in found):
        raise ValueError("外務省データの形式が想定と違います")
    levels = [n for n, e in zip(range(1, 5), found) if e is not None and (e.text or "").strip() == "1"]
    return max(levels, default=0)


def parse_safety(xml_bytes: bytes) -> dict:
    root = ET.fromstring(xml_bytes)
    country = root.find("country")
    country_cd = country.get("countryCd") if country is not None else None
    url = COUNTRY_PAGE.format(code=country_cd.zfill(3)) if country_cd else (root.findtext("infoUrl") or "")
    return {
        "level": _max_level(root, "riskLevel"),
        "infection_level": _max_level(root, "infectionLevel"),
        "title": (root.findtext("riskTitle") or "").strip(),
        "url": url,
        "mofa_updated": root.get("lastModified", ""),
    }


def apply_change(current: dict, previous: dict | None, now: datetime) -> dict:
    """前回と比べて、変化の情報（changed / changed_at / previous_*）を足して返す。"""
    result = dict(current)
    if not previous:
        result.update(changed=False, changed_at=None, previous_level=None, previous_infection_level=None)
        return result

    if (previous.get("level"), previous.get("infection_level")) != (current["level"], current["infection_level"]):
        result.update(
            changed=True,
            changed_at=iso(now),
            previous_level=previous.get("level"),
            previous_infection_level=previous.get("infection_level"),
        )
        return result

    changed_at = previous.get("changed_at")
    result.update(
        changed_at=changed_at,
        previous_level=previous.get("previous_level"),
        previous_infection_level=previous.get("previous_infection_level"),
        changed=bool(changed_at) and now - datetime.fromisoformat(changed_at) <= timedelta(days=CHANGED_DAYS),
    )
    return result


class SafetySource(Source):
    name = "safety"
    provider = "mofa"
    label = "海外安全情報"

    def fetch(self, dest, previous, now):
        current = parse_safety(http.get_bytes(f"{API}/{dest['mofa_code']}L.xml"))
        return apply_change(current, previous, now)
