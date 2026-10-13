"""行き先の追加・削除（設計書 2026-10-13-add-destination-design.md）。

- 都市名から地名検索（Open-Meteo Geocoding）で場所を調べ、設定の1件分を作る
- 設定ファイル（config/destinations.json）への書き足し・削除
"""

import json
import shutil
from pathlib import Path

from fetcher import http
from fetcher.config import ID_PATTERN

GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"


class DestinationError(Exception):
    """追加・削除できなかったことを表す。メッセージは画面にそのまま出せる日本語。"""


# ---------- 地名検索 ----------

def search_city(city: str) -> list[dict]:
    raw = http.get_json(GEOCODING_API, params={"name": city, "count": 10, "language": "ja"})
    return raw.get("results") or []


def pick_result(results: list[dict], country: str | None) -> dict | None:
    if not country:
        return results[0] if results else None
    for r in results:
        name = r.get("country") or ""
        if name and (country in name or name in country):
            return r
    return None


def make_destination(result: dict, countries: dict) -> dict:
    code = result["country_code"]
    info = countries.get(code, {})
    return {
        "id": f"{code.lower()}-{result['id']}",
        "name": result["name"],
        "country": result.get("country") or code,
        "country_code": code,
        "mofa_code": info.get("mofa_code"),
        "lat": round(result["latitude"], 2),
        "lon": round(result["longitude"], 2),
        "currency": info.get("currency"),
    }


# ---------- 設定ファイルの読み書き ----------
# 検証済みの値ではなく生の JSON を読み書きする（手で書いた項目をそのまま残すため）

def _read(config_path: Path) -> list:
    items = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise DestinationError("設定ファイルの形が正しくありません（[ ... ] の形にしてください）")
    return items


def _write(config_path: Path, items: list) -> None:
    Path(config_path).write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _label(item: dict) -> str:
    return f"{item.get('name')}（{item.get('country')}）"


def add_destination(config_path: Path, dest: dict) -> None:
    items = _read(config_path)
    for item in items:
        if not isinstance(item, dict):
            continue
        same_id = item.get("id") == dest["id"]
        same_place = item.get("name") == dest["name"] and item.get("country") == dest["country"]
        if same_id or same_place:
            raise DestinationError(f"すでに登録されています：{_label(item)}")
    items.append(dest)
    _write(config_path, items)


def remove_destination(config_path: Path, data_dir: Path, key: str) -> dict:
    items = _read(config_path)
    matches = [i for i in items if isinstance(i, dict) and key in (i.get("name"), i.get("id"))]
    if not matches:
        names = "、".join(str(i.get("name")) for i in items if isinstance(i, dict)) or "（なし）"
        raise DestinationError(f"『{key}』は登録されていません。登録中：{names}")
    if len(matches) > 1:
        ids = "、".join(str(i.get("id")) for i in matches)
        raise DestinationError(f"同じ名前の行き先が複数あります。id で指定してください：{ids}")

    target = matches[0]
    dest_id = str(target.get("id"))
    data_root = Path(data_dir).resolve()
    folder = (data_root / dest_id).resolve()
    # id がおかしいと site/data の外を消してしまうので、必ず確かめる
    if not ID_PATTERN.match(dest_id) or folder.parent != data_root:
        raise DestinationError(f"id「{dest_id}」が正しくないため削除できません。設定ファイルを手で直してください")

    items.remove(target)
    _write(config_path, items)
    if folder.exists():
        shutil.rmtree(folder)
    return target
