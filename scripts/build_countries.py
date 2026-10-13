"""国 → 通貨・外務省国番号の対応表（config/countries.json）を作る。一度だけ実行して、結果をリポジトリに入れる。

使い方：
  1. mledoze/countries の countries.json（5.1.0）と、外務省 海外安全情報オープンデータの
     国コード一覧 country.xlsx をダウンロードする
       https://cdn.jsdelivr.net/gh/mledoze/countries@5.1.0/countries.json
       https://www.ezairyu.mofa.go.jp/html/opendata/support/country.xlsx
  2. python -I scripts/build_countries.py countries.json country.xlsx > config/countries.json

外部ライブラリは使わない（Excel ファイルも標準ライブラリで読む）。
"""

import json
import sys
import xml.etree.ElementTree as ET
import zipfile

# 電話番号から決められない国（外務省の一覧にある番号を手で決める）
OVERRIDES = {
    "US": "1000",  # アメリカ合衆国（本土）
    "CA": "9001",  # カナダ
    "MP": "1001",  # 北マリアナ諸島
    "GU": "1002",  # グアム
    "RU": "9007",  # ロシア
    "KZ": "0007",  # カザフスタン
    "VA": "9039",  # バチカン市国
    "EH": "9212",  # 西サハラ
    "XK": "9381",  # コソボ
    "PF": "9689",  # タヒチ（仏領ポリネシア）
    # カリブ海の国（電話番号は +1 で始まるが、外務省は 0 + 下3桁）
    "GD": "0473",  # グレナダ
    "LC": "0758",  # セントルシア
    "DM": "0767",  # ドミニカ国
    "VC": "0784",  # セントビンセント及びグレナディーン諸島
    "DO": "0809",  # ドミニカ共和国
    "TT": "0868",  # トリニダード・トバゴ
    "KN": "0869",  # セントクリストファー・ネービス
    "JM": "0876",  # ジャマイカ
}

# 電話番号のデータが他の国と重なってしまい、正しく決められない地域（国番号を付けない）
NO_MOFA_CODE = {"UM"}  # 合衆国領有小離島（エスワティニの番号と重なる）

XLSX_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _calling_code(idd: dict) -> str | None:
    """国際電話番号（数字だけ）。suffix が1つのときだけ決まる。"""
    root = (idd.get("root") or "").lstrip("+")
    suffixes = idd.get("suffixes") or []
    if not root or len(suffixes) != 1:
        return None
    digits = root + suffixes[0]
    return digits if digits.isdigit() else None


def build_table(countries: list[dict], mofa_codes: set[str]) -> dict[str, dict]:
    table = {}
    for c in sorted(countries, key=lambda c: c["cca2"]):
        currencies = list(c.get("currencies") or {})
        mofa_code = OVERRIDES.get(c["cca2"])
        if c["cca2"] in NO_MOFA_CODE:
            mofa_code = None
        elif mofa_code is None:
            code = _calling_code(c.get("idd") or {})
            mofa_code = code.zfill(4) if code else None
        table[c["cca2"]] = {
            "currency": currencies[0] if currencies else None,
            "mofa_code": mofa_code if mofa_code in mofa_codes else None,
        }
    return table


def read_mofa_codes(xlsx_path: str) -> set[str]:
    """country.xlsx の「国コード」列（3列目）の4桁の番号を集める。"""
    with zipfile.ZipFile(xlsx_path) as z:
        shared = [
            "".join(t.text or "" for t in si.iter(f"{{{XLSX_NS['m']}}}t"))
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", XLSX_NS)
        ]
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    codes = set()
    for row in sheet.iter(f"{{{XLSX_NS['m']}}}row"):
        cells = row.findall("m:c", XLSX_NS)
        if len(cells) < 3:
            continue
        cell = cells[2]
        v = cell.find("m:v", XLSX_NS)
        value = v.text if v is not None else ""
        if cell.get("t") == "s" and value:
            value = shared[int(value)]
        if len(value) == 4 and value.isdigit():
            codes.add(value)
    return codes


def main(argv: list[str]) -> int:
    countries_path, xlsx_path = argv
    with open(countries_path, encoding="utf-8") as f:
        countries = json.load(f)
    table = build_table(countries, read_mofa_codes(xlsx_path))
    json.dump(table, sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
