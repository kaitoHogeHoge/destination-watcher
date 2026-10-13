"""取得の入口。実行方法：python -m fetcher.main"""

import argparse
import logging
import sys
from pathlib import Path

from fetcher.config import load_destinations
from fetcher.runner import run
from fetcher.sources import SOURCES
from fetcher.timeutil import now_jst

log = logging.getLogger("fetcher")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="行き先ウォッチャーのデータを取得する")
    parser.add_argument("--config", default="config/destinations.json", help="行き先の設定ファイル")
    parser.add_argument("--data-dir", default="site/data", help="データの保存先")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        destinations = load_destinations(Path(args.config))
    except (OSError, ValueError) as e:
        log.error("設定ファイルが読めません：%s（%s）", args.config, e)
        return 1

    summary = run(destinations, SOURCES, Path(args.data_dir), now_jst())
    log.info(
        "成功 %d 件・失敗 %d 件・対象外 %d 件・据え置き %d 件",
        summary.ok, summary.error, summary.unsupported, summary.kept,
    )
    if summary.ok + summary.kept == 0 and summary.error > 0:
        log.error("すべての取得に失敗しました")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
