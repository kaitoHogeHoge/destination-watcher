"""取得結果の保存と読み込み。

保存先：{data_dir}/{行き先id}/{情報の種類}.json
1ファイルの形は設計書 6.2 を参照。
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fetcher.timeutil import iso

log = logging.getLogger(__name__)


def record_path(data_dir: Path, dest_id: str, name: str) -> Path:
    return Path(data_dir) / dest_id / f"{name}.json"


def _write_json(path: Path, value: Any) -> None:
    """一時ファイルに書いてから置き換える（途中で止まっても壊れたファイルを残さない）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_record(data_dir: Path, dest_id: str, name: str) -> dict | None:
    path = record_path(data_dir, dest_id, name)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.warning("%s が読めないため、前回のデータは無いものとして扱います", path)
        return None
    if not isinstance(value, dict):
        log.warning("%s の形が想定と違うため、前回のデータは無いものとして扱います", path)
        return None
    return value


def write_record(data_dir: Path, dest_id: str, record: dict) -> None:
    _write_json(record_path(data_dir, dest_id, record["source"]), record)


def ok_record(name: str, provider: str, data: Any, now: datetime, data_version: int = 1) -> dict:
    return {
        "source": name,
        "provider": provider,
        "status": "ok",
        "updated_at": iso(now),
        "attempted_at": iso(now),
        "error": None,
        "data": data,
        "data_version": data_version,
    }


def error_record(name: str, provider: str | None, message: str, now: datetime, previous: dict | None) -> dict:
    previous = previous or {}
    return {
        "source": name,
        "provider": provider,
        "status": "error",
        "updated_at": previous.get("updated_at"),
        "attempted_at": iso(now),
        "error": message,
        "data": previous.get("data"),
        "data_version": previous.get("data_version", 1),
    }


def unsupported_record(name: str, now: datetime) -> dict:
    return {
        "source": name,
        "provider": None,
        "status": "unsupported",
        "updated_at": None,
        "attempted_at": iso(now),
        "error": None,
        "data": None,
    }


def write_index(data_dir: Path, destinations: list[dict], sources: list[dict], now: datetime) -> None:
    _write_json(
        Path(data_dir) / "index.json",
        {
            "generated_at": iso(now),
            "destinations": [{"id": d["id"], "name": d["name"], "country": d["country"]} for d in destinations],
            "sources": [{"name": s["name"], "label": s["label"]} for s in sources],
        },
    )
