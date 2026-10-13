"""行き先を削除する。実行方法：python -m fetcher.remove --name バンコク"""

import argparse
import sys
from pathlib import Path

from fetcher.destinations import DestinationError, remove_destination, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="行き先を削除する")
    parser.add_argument("--name", required=True, help="画面に出ている都市名、または id")
    parser.add_argument("--config", default="config/destinations.json")
    parser.add_argument("--data-dir", default="site/data")
    args = parser.parse_args(argv)

    try:
        removed = remove_destination(Path(args.config), Path(args.data_dir), args.name.strip())
    except DestinationError as e:
        report(f"⚠ 削除できませんでした：{e}")
        return 1
    report(f"✅ {removed.get('name')}（{removed.get('country')}）を削除しました\n\n"
           "このあと「データ更新」が動き、数分で公開ページに反映されます。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
