"""都市の写真（Wikimedia）。日本語版 Wikipedia の記事の写真と、その撮影者・ライセンス（設計書 2026-10-15）。

選び方：設定の photo → 記事の代表画像 → 記事の画像一覧の最初の写真。
国旗・地図・紋章などは写真として使わない。
"""

import html
import re
from urllib.parse import quote, unquote, urlparse

from fetcher import http
from fetcher.sources.base import Source

SUMMARY_API = "https://ja.wikipedia.org/api/rest_v1/page/summary/{title}"
MEDIA_API = "https://ja.wikipedia.org/api/rest_v1/page/media-list/{title}"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIDTH = 960

PHOTO_EXTENSIONS = (".jpg", ".jpeg")
NOT_PHOTO_WORDS = ("flag", "map", "locator", "coat_of_arms", "emblem", "seal_of", "location")


def is_photo_file(name: str) -> bool:
    lower = name.lower()
    return lower.endswith(PHOTO_EXTENSIONS) and not any(word in lower for word in NOT_PHOTO_WORDS)


def file_from_url(url: str) -> str | None:
    """Wikimedia の画像 URL（縮小版も）→ 「File:ファイル名」。"""
    parsed = urlparse(url)
    if not parsed.netloc.endswith("wikimedia.org"):
        return None
    parts = [unquote(p) for p in parsed.path.split("/") if p]
    if "thumb" in parts:
        i = parts.index("thumb")
        name = parts[i + 3] if len(parts) > i + 3 else None  # thumb/6/6e/ファイル名/960px-…
    else:
        name = parts[-1] if parts else None
    return f"File:{name}" if name else None


def strip_html(text: str) -> str:
    text = re.sub(r"<script.*?</script>", "", text or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(html.unescape(text).split())


def _safe_url(value) -> str | None:
    return value if isinstance(value, str) and value.startswith(("https://", "http://")) else None


def _candidate_files(name: str):
    """記事の代表画像、次に画像一覧の写真を、順に返す。記事が無ければ何も返さない。"""
    title = quote(name, safe="")
    try:
        summary = http.get_json(SUMMARY_API.format(title=title))
    except http.NotFoundError:
        return
    lead = (summary.get("originalimage") or summary.get("thumbnail") or {}).get("source")
    lead_file = file_from_url(lead) if lead else None
    if lead_file and is_photo_file(lead_file):
        yield lead_file
        return
    try:
        media = http.get_json(MEDIA_API.format(title=title))
    except http.NotFoundError:
        return
    for item in media.get("items") or []:
        if item.get("type") != "image":
            continue
        file = re.sub(r"^(ファイル|File):", "File:", item.get("title") or "")
        if file.startswith("File:") and is_photo_file(file):
            yield file
            return


def _commons_info(file: str) -> dict:
    raw = http.get_json(COMMONS_API, params={
        "action": "query", "titles": file, "prop": "imageinfo",
        "iiprop": "url|extmetadata", "iiurlwidth": WIDTH, "format": "json", "formatversion": 2,
    })
    pages = (raw.get("query") or {}).get("pages") or [{}]
    info = (pages[0].get("imageinfo") or [None])[0]
    if not info:
        return {"url": None}
    meta = info.get("extmetadata") or {}
    url = _safe_url(info.get("thumburl") or info.get("url"))
    if not url:
        return {"url": None}
    return {
        "url": url,
        "page": _safe_url(info.get("descriptionurl")),
        "artist": strip_html((meta.get("Artist") or {}).get("value", "")) or "不明",
        "license": strip_html((meta.get("LicenseShortName") or {}).get("value", "")),
        "file": file,
    }


class PhotoSource(Source):
    name = "photo"
    provider = "wikimedia"
    label = "写真"
    refresh_days = 90

    def fetch(self, dest, previous, now):
        file = dest.get("photo") or next(_candidate_files(dest["name"]), None)
        if not file:
            return {"url": None}
        return _commons_info(file)
