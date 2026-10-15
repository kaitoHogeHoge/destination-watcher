# 行き先ウォッチャー

気になる旅行先の為替・天気予報・気候・祝日・海外安全情報を毎日自動で集めて、カードで並べて比べるための画面です。

- 公開ページ：https://kaitohogehoge.github.io/destination-watcher/
- データの取得：GitHub Actions が毎日 日本時間 6:00 ごろに実行（`.github/workflows/update.yml`）
- 自動テストが通らないときは、取得も公開も行わず、Actions のページに ❌ が出ます（公開ページは前の版のまま）
- 設計書：`docs/superpowers/specs/2026-10-13-destination-watcher-design.md`

## 行き先を足す・消す（おすすめ：GitHub のボタンから）

スマホのブラウザからもできます。

**追加**
1. https://github.com/kaitoHogeHoge/destination-watcher/actions を開く
2. 左の一覧から「行き先を追加」を選び、右の「Run workflow」を押す
3. 「都市名」を入れて「Run workflow」で実行する（例：バンコク）
   - 見つからないときは英語名で（例：Reykjavik）
   - 同じ名前の都市が他の国にもあるときは「国名」も入れる（例：フランス）
4. 実行結果を開くと「バンコク（タイ）を追加しました」と、対象外になる情報が出る
5. 続けて「データ更新」が自動で動き、数分で公開ページにカードが増える

**削除**
1. 同じページで「行き先を削除」を選び、画面に出ている都市名を入れて実行する
2. 設定とその都市のデータが消え、数分で公開ページから消える

追加・削除は**1つずつ**、前の実行が ✅ になってから次を実行してください。続けて実行してぶつかると ❌ になります（そのときは、もう一度実行すれば直ります）。

## 行き先を手で足す

`config/destinations.json` を直接編集することもできます。GitHub の自動実行が毎朝データを保存しているので、編集を始める前に必ず最新を取り込みます。

```bash
git pull
```

1件分を足して GitHub に push すると、自動で取得と公開が行われます。

```json
{
  "id": "bangkok",
  "name": "バンコク",
  "country": "タイ",
  "country_code": "TH",
  "mofa_code": "0066",
  "lat": 13.75,
  "lon": 100.50,
  "currency": "THB"
}
```

| 項目 | 意味 |
|---|---|
| `id` | 英小文字・数字・`-`・`_` だけの識別名 |
| `name` / `country` | 画面に出す名前 |
| `country_code` | 2文字の国コード（例：GB、NO、SG） |
| `holiday_region` | 省略可。地域ごとに祝日が違う国で、その地域だけに絞る（例：`GB-ENG`） |
| `mofa_code` | 外務省の国番号（`config/countries.json` で調べられる）。`null` なら安全情報は対象外 |
| `lat` / `lon` | 緯度・経度 |
| `currency` | 3文字の通貨コード（例：GBP）。`null` なら為替は対象外 |

データ元が対応していない国・通貨は、その情報だけ「対象外」と表示されます。

## 手元で動かす

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m fetcher.main      # データを取得する
.venv/bin/pytest                      # 自動テスト（取得）
node --test tests/js/*.test.js        # 自動テスト（画面の計算）
python3 -m http.server 8000 -d site   # 画面を http://localhost:8000 で見る
```

手元で取得すると `site/data` が書き換わります。データは GitHub の自動実行が保存するので、手元の分は送らずに元に戻してください。

```bash
git restore site/data
```

## データ元

- 為替：[Frankfurter](https://frankfurter.dev/)（欧州中央銀行の参考レート。平日のみ更新）
- 天気予報・気候：[Open-Meteo](https://open-meteo.com/)
- 祝日：[Nager.Date](https://date.nager.at/)
- 海外安全情報：[外務省 海外安全情報オープンデータ](https://www.ezairyu.mofa.go.jp/html/opendata/)
- 地名検索：[Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api)
- 国と通貨の対応表（`config/countries.json`）：[mledoze/countries](https://github.com/mledoze/countries) 5.1.0（ODbL-1.0）と外務省の国コード一覧から `scripts/build_countries.py` で作成
