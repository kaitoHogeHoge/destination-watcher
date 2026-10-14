"""海外安全情報（外務省 海外安全情報オープンデータ）。危険レベルと、その変化（設計書 5.6）。"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from fetcher import http
from fetcher.sources.base import Source
from fetcher.timeutil import JST, iso

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


NOTICE_DAYS = 30
NOTICE_LIMIT = 5
MAIL_PAGE = "https://www.anzen.mofa.go.jp/od/ryojiMailDetail.html?keyCd={key}"
LINKS = [
    ("safetyMeasureUrl", "安全対策基礎データ"),
    ("medicalSituationUrl", "医療事情"),
    ("terroKidnapUrl", "テロ・誘拐情勢"),
]


def _safe_url(value: str | None) -> str | None:
    """外部データの URL は http/https のものだけ使う（javascript: などは使わない）。"""
    url = (value or "").strip()
    return url if url.startswith(("https://", "http://")) else None


def _leave_date(text: str | None) -> datetime | None:
    """「2026/10/05 20:26:12」→ 日本時間の日時。読めなければ None。"""
    try:
        return datetime.strptime((text or "").strip(), "%Y/%m/%d %H:%M:%S").replace(tzinfo=JST)
    except ValueError:
        return None


def parse_notices(root: ET.Element, now: datetime) -> list[dict]:
    """ルート直下の領事メールと広域・スポット情報から、30日以内のものを新しい順に最大5件。"""
    found = []
    for element, kind in [(e, "領事メール") for e in root.findall("mail")] + [
        (e, "広域・スポット情報") for e in root.findall("wideareaSpot")
    ]:
        title = (element.findtext("title") or "").strip()
        when = _leave_date(element.findtext("leaveDate"))
        if not title or when is None or now - when > timedelta(days=NOTICE_DAYS):
            continue
        if element.tag == "mail":
            key = (element.findtext("keyCd") or "").strip()
            url = MAIL_PAGE.format(key=key) if key.isdigit() else _safe_url(element.findtext("infoUrl"))
        else:
            url = _safe_url(element.findtext("url"))
        found.append((when, {"date": when.date().isoformat(), "title": title, "url": url, "kind": kind}))
    found.sort(key=lambda pair: pair[0], reverse=True)
    return [notice for _, notice in found[:NOTICE_LIMIT]]


def parse_links(root: ET.Element) -> list[dict]:
    links = []
    for tag, label in LINKS:
        url = _safe_url(root.findtext(tag))
        if url:
            links.append({"label": label, "url": url})
    return links


def apply_change(current: dict, previous: dict | None, now: datetime) -> dict:
    """前回と比べて、変化の情報（changed / changed_at / previous_*）を足して返す。"""
    result = dict(current)
    if previous and previous.get("mofa_code") and previous.get("mofa_code") != current.get("mofa_code"):
        previous = None  # 国が変わったときは比べない
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
        changed=_within_days(changed_at, now, CHANGED_DAYS),
    )
    return result


def _within_days(value, now: datetime, days: int) -> bool:
    """value（ISO 日時の文字列）が now から days 日以内なら True。読めない値は False。"""
    try:
        return now - datetime.fromisoformat(value) <= timedelta(days=days)
    except (TypeError, ValueError):
        return False


class SafetySource(Source):
    name = "safety"
    provider = "mofa"
    label = "海外安全情報"

    def supports(self, dest):
        return bool(dest.get("mofa_code"))

    def fetch(self, dest, previous, now):
        xml_bytes = http.get_bytes(f"{API}/{dest['mofa_code']}L.xml")
        current = parse_safety(xml_bytes)
        current["mofa_code"] = dest["mofa_code"]
        root = ET.fromstring(xml_bytes)
        current["notices"] = parse_notices(root, now)
        current["links"] = parse_links(root)
        return apply_change(current, previous, now)
