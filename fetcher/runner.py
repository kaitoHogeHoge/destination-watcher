"""司令塔の中身：全行き先 × 全情報を順に取得して保存する（設計書 5.1.1・7）。

1つの取得が失敗しても、他の取得はそのまま続ける。
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from fetcher import storage
from fetcher.http import FetchError
from fetcher.sources.base import Source

log = logging.getLogger(__name__)


@dataclass
class Summary:
    ok: int = 0
    error: int = 0
    unsupported: int = 0
    kept: int = 0  # refresh_days により取り直さなかった件数


def pick_source(candidates: list[Source], dest: dict) -> Source | None:
    for source in candidates:
        if source.supports(dest):
            return source
    return None


def needs_refresh(previous: dict | None, source: Source, now: datetime) -> bool:
    if source.refresh_days == 0 or previous is None:
        return True
    if previous.get("status") != "ok" or previous.get("provider") != source.provider:
        return True
    try:
        updated_at = datetime.fromisoformat(previous["updated_at"])
        return now - updated_at >= timedelta(days=source.refresh_days)
    except (KeyError, TypeError, ValueError):  # 日時が壊れている・時間帯が無い → 取り直す
        return True


def _error_message(e: Exception) -> str:
    if isinstance(e, FetchError):
        return str(e)
    return f"{type(e).__name__}: {e}"[:200]


def _fetch(source: Source, dest: dict, previous_data, now: datetime):
    """取得する。通信以外の理由で失敗し、前回のデータがあるときは、
    前回のデータが壊れている可能性があるので「前回なし」でもう一度だけ試す。"""
    try:
        return source.fetch(dest, previous_data, now)
    except FetchError:
        raise
    except Exception as e:
        if previous_data is None:
            raise
        log.warning("%s %s：前回のデータを使わずに取り直します（%s）", dest["id"], source.name, _error_message(e))
        return source.fetch(dest, None, now)


def _group_by_name(sources: list[Source]) -> dict[str, list[Source]]:
    groups: dict[str, list[Source]] = {}
    for source in sources:
        groups.setdefault(source.name, []).append(source)
    return groups


def run(destinations: list[dict], sources: list[Source], data_dir: Path, now: datetime) -> Summary:
    summary = Summary()
    groups = _group_by_name(sources)

    for dest in destinations:
        for name, candidates in groups.items():
            previous = storage.read_record(data_dir, dest["id"], name)
            try:
                source = pick_source(candidates, dest)
            except Exception as e:  # 対応確認そのものが壊れていても他は止めない
                source = candidates[0]
                log.warning("%s %s：対応の確認に失敗（%s）", dest["id"], name, _error_message(e))

            if source is None:
                storage.write_record(data_dir, dest["id"], storage.unsupported_record(name, now))
                summary.unsupported += 1
                log.info("%s %s unsupported", dest["id"], name)
                continue

            if not needs_refresh(previous, source, now):
                summary.kept += 1
                log.info("%s %s kept", dest["id"], name)
                continue

            previous_data = previous.get("data") if previous else None
            try:
                data = _fetch(source, dest, previous_data, now)
            except Exception as e:
                message = _error_message(e)
                storage.write_record(
                    data_dir, dest["id"], storage.error_record(name, source.provider, message, now, previous)
                )
                summary.error += 1
                log.warning("%s %s error: %s", dest["id"], name, message)
                continue

            storage.write_record(data_dir, dest["id"], storage.ok_record(name, source.provider, data, now))
            summary.ok += 1
            log.info("%s %s ok", dest["id"], name)

    index_sources = [{"name": name, "label": c[0].label} for name, c in groups.items()]
    storage.write_index(data_dir, destinations, index_sources, now)
    return summary
