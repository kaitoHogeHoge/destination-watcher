"""日時の扱い。保存する日時はすべて日本時間にそろえる。"""

from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def now_jst() -> datetime:
    return datetime.now(JST)


def iso(dt: datetime) -> str:
    """秒までの ISO 8601 文字列（例：2026-10-13T06:00:00+09:00）。"""
    return dt.astimezone(JST).isoformat(timespec="seconds")
