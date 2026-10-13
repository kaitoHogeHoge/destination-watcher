"""行き先を追加する。実行方法：python -m fetcher.add --city バンコク [--country タイ]"""

import argparse
import json
import sys
from pathlib import Path

from fetcher.destinations import DestinationError, add_destination, make_destination, pick_result, report, search_city
from fetcher.http import FetchError
from fetcher.runner import _group_by_name, pick_source
from fetcher.sources import SOURCES


def unsupported_labels(dest: dict) -> list[str]:
    """この行き先で「対象外」になる情報の見出し。"""
    return [c[0].label for c in _group_by_name(SOURCES).values() if pick_source(c, dest) is None]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="行き先を追加する")
    parser.add_argument("--city", required=True, help="都市名（例：バンコク）")
    parser.add_argument("--country", default="", help="国名（同じ名前の都市が他の国にあるとき）")
    parser.add_argument("--config", default="config/destinations.json")
    parser.add_argument("--countries", default="config/countries.json")
    args = parser.parse_args(argv)
    city, country = args.city.strip(), args.country.strip() or None

    try:
        if not city:
            raise DestinationError("都市名を入力してください")
        result = pick_result(search_city(city), country)
        if result is None:
            where = f"『{city}』（{country}）" if country else f"『{city}』"
            raise DestinationError(f"{where}が見つかりませんでした。英語名（例：Reykjavik）でも試してください")
        countries = json.loads(Path(args.countries).read_text(encoding="utf-8"))
        dest = make_destination(result, countries)
        add_destination(Path(args.config), dest)
    except (DestinationError, FetchError) as e:
        report(f"⚠ 追加できませんでした：{e}")
        return 1

    lines = [f"✅ {dest['name']}（{dest['country']}）を追加しました（id：{dest['id']}）"]
    labels = unsupported_labels(dest)
    lines.append(f"対象外の情報：{'、'.join(labels)}" if labels else "すべての情報が表示されます")
    lines.append("このあと「データ更新」が動き、数分で公開ページに反映されます。")
    report("\n\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
