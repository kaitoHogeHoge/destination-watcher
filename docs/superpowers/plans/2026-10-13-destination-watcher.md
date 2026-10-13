# 行き先ウォッチャー 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ウォッチリストの行き先ごとに、為替・天気予報・気候・祝日・安全情報を毎日自動取得し、カード形式の日本語画面で比較できるようにする。

**Architecture:** Python の取得処理（`fetcher/`）が情報ごとの部品（`fetcher/sources/`）を順に呼び、結果を `site/data/` に JSON で保存する。画面（`site/`）は JSON を読んで描画するだけの静的ページ。GitHub Actions が毎日取得とコミットを行い、GitHub Pages で `site/` を公開する。

**Tech Stack:** Python 3.12 以上、requests、pytest、素の HTML/CSS/JavaScript、Chart.js 4.4.1（jsDelivr CDN）、GitHub Actions、GitHub Pages

**Spec:** `docs/superpowers/specs/2026-10-13-destination-watcher-design.md`

## Global Constraints

- 外部ライブラリは `requests` のみ（テスト用に `pytest`）。`requirements.txt` に版を固定して書く
- 通信はすべて `fetcher/http.py` を通す。タイムアウト20秒、失敗時は1回だけ再試行
- 日時はすべて日本時間（+09:00）の ISO 8601 文字列（秒まで）で保存する
- JSON は `ensure_ascii=False, indent=2` で書き出す（日本語をそのまま読めるように）
- 1ファイルの形（spec 6.2）：`source` / `provider` / `status`（`ok`・`error`・`unsupported`）/ `updated_at` / `attempted_at` / `error` / `data`
- 画面の文字はすべて日本語。日付は「10/13（月）」、日時は「10/13 6:00」の形
- 画面はビルド作業なし。外部から読み込むのは Chart.js だけ
- 各 API を使う部品を作る前に、その API の現在の応答を curl で確認し、`tests/fixtures/` に保存してからテストを書く
- 各ステップ（spec 12）の終わりで止まり、利用者に動作確認の方法を説明してから次へ進む

## Review Focus

- 土日・祝日に為替を取得すると新しい日付が無い → 履歴が消えたり重複したりしないこと（Task 3 にテスト）
- 前回の JSON ファイルが壊れている・手で書き換えられている → 「前回なし」として扱い、処理が止まらないこと（Task 2 にテスト）
- 行き先を後から足した・消した → `index.json` には今の設定の行き先だけが並び、新しい行き先は「データがまだありません」から始まること（Task 4 にテスト）
- 通信のタイムアウト・500系エラー・JSON でない応答 → 1回だけ再試行し、だめなら `error` として記録されること（Task 1 にテスト）
- 外務省 XML の中には地域ごとの `riskLevel` も入れ子で入っている → 国全体（いちばん外側）の値だけを使うこと。国全体の値が1つも無いときは形式変更とみなしてエラーにすること（Task 9 にテスト）

---

## ステップ1：ロンドン × 為替だけを手元で表示する

### Task 1: プロジェクトの土台・通信・設定ファイル

**Files:**
- Create: `requirements.txt`, `.gitignore`, `pyproject.toml`（pytest の設定だけ：`pythonpath = ["."]`）
- Create: `fetcher/__init__.py`, `fetcher/http.py`, `fetcher/timeutil.py`, `fetcher/config.py`
- Create: `config/destinations.json`（このステップではロンドンだけ。中身は spec 4 のロンドンの項目）
- Test: `tests/test_http.py`, `tests/test_config.py`

**Interfaces:**
- Produces:
  - `fetcher.http.FetchError(Exception)`：メッセージは日本語（例：「通信に失敗しました（タイムアウト）」）
  - `fetcher.http.get_json(url: str, params: dict | None = None) -> Any`
  - `fetcher.http.get_bytes(url: str, params: dict | None = None) -> bytes`
  - `fetcher.timeutil.JST`、`fetcher.timeutil.now_jst() -> datetime`、`fetcher.timeutil.iso(dt: datetime) -> str`（秒までの ISO 文字列）
  - `fetcher.config.REQUIRED_FIELDS = ("id", "name", "country", "country_code", "mofa_code", "lat", "lon", "currency")`
  - `fetcher.config.load_destinations(path: Path) -> list[dict]`

- [ ] **Step 1: 仮想環境を作り、ライブラリを入れる**

Run: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
Expected: `Successfully installed ... requests ... pytest ...`

- [ ] **Step 2: 失敗するテストを書く**

`tests/test_http.py`（`requests.get` を monkeypatch で差し替える。`time.sleep` も差し替えて待たない）：
- `test_get_json_returns_parsed_body`：200 と `{"a": 1}` → `{"a": 1}`
- `test_retries_once_then_succeeds`：1回目 `requests.Timeout`、2回目成功 → 結果が返り、呼び出し回数が2
- `test_raises_fetch_error_after_two_failures`：2回とも HTTP 503 → `FetchError`、呼び出し回数が2
- `test_non_json_body_raises_fetch_error`：200 で本文が `<html>` → `FetchError`
- `test_passes_timeout_20`：`requests.get` に `timeout=20` が渡ること

`tests/test_config.py`（`tmp_path` に JSON を書いて読む）：
- `test_loads_valid_destination`：spec 4 のロンドン → 1件、`holiday_region == "GB-ENG"`
- `test_skips_entry_missing_required_field`：`currency` が無い項目と正しい項目 → 正しい1件だけ
- `test_skips_bad_id_and_duplicate_id`：`id` が `"London City"`（英小文字・数字・`-`・`_` 以外）の項目と、同じ `id` の2件目 → どちらも飛ばす
- `test_unreadable_file_raises`：存在しないパス → `FileNotFoundError`

- [ ] **Step 3: テストが失敗することを確かめる**

Run: `.venv/bin/pytest tests/test_http.py tests/test_config.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'fetcher.http'` など）

- [ ] **Step 4: `fetcher/http.py`・`fetcher/timeutil.py`・`fetcher/config.py` を実装する**

- 再試行は `requests.RequestException` または 500 以上・429 のときだけ、2秒待って1回。400 番台（429 を除く）は再試行せずすぐ `FetchError`
- 通信のヘッダに `User-Agent: destination-watcher` を付ける
- 設定ファイルの飛ばした項目は `logging.warning` で理由を出す

- [ ] **Step 5: テストが通ることを確かめる**

Run: `.venv/bin/pytest -v`
Expected: 9 passed

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "土台：通信・日時・設定ファイルの読み込み"
```

### Task 2: 保存処理（storage）

**Files:**
- Create: `fetcher/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: `fetcher.timeutil.iso`
- Produces:
  - `read_record(data_dir: Path, dest_id: str, name: str) -> dict | None`（ファイルが無い・壊れている → `None`。壊れているときは `logging.warning`）
  - `write_record(data_dir: Path, dest_id: str, record: dict) -> None`（`{data_dir}/{dest_id}/{record["source"]}.json`。一時ファイルに書いてから置き換える）
  - `ok_record(name: str, provider: str, data: Any, now: datetime) -> dict`
  - `error_record(name: str, provider: str | None, message: str, now: datetime, previous: dict | None) -> dict`
  - `unsupported_record(name: str, now: datetime) -> dict`
  - `write_index(data_dir: Path, destinations: list[dict], sources: list[dict], now: datetime) -> None`
    出力：`{"generated_at": ..., "destinations": [{"id", "name", "country"}], "sources": [{"name", "label"}]}`

- [ ] **Step 1: 失敗するテストを書く**

```python
NOW = datetime(2026, 10, 13, 6, 0, tzinfo=JST)
EARLIER = datetime(2026, 10, 12, 6, 0, tzinfo=JST)

def test_ok_record_shape():
    r = ok_record("exchange", "frankfurter", {"x": 1}, NOW)
    assert r == {"source": "exchange", "provider": "frankfurter", "status": "ok",
                 "updated_at": "2026-10-13T06:00:00+09:00",
                 "attempted_at": "2026-10-13T06:00:00+09:00",
                 "error": None, "data": {"x": 1}}

def test_error_record_keeps_previous_data_and_updated_at():
    prev = ok_record("exchange", "frankfurter", {"x": 1}, EARLIER)
    r = error_record("exchange", "frankfurter", "通信に失敗しました", NOW, prev)
    assert r["status"] == "error"
    assert r["data"] == {"x": 1}
    assert r["updated_at"] == "2026-10-12T06:00:00+09:00"
    assert r["attempted_at"] == "2026-10-13T06:00:00+09:00"
    assert r["error"] == "通信に失敗しました"

def test_error_record_without_previous_has_null_data():
    r = error_record("exchange", "frankfurter", "失敗", NOW, None)
    assert r["data"] is None and r["updated_at"] is None

def test_unsupported_record():
    r = unsupported_record("holidays", NOW)
    assert r["status"] == "unsupported" and r["provider"] is None and r["data"] is None
```

ほかに：
- `test_write_then_read_roundtrip`：日本語を含む record を書いて読む → 同じ dict。ファイル本文に `"ロンドン"` がそのまま入っている（`\u` に化けない）
- `test_read_missing_returns_none`
- `test_read_broken_json_returns_none`：`{` だけのファイル → `None`
- `test_write_index_lists_given_destinations_only`：`data_dir` に古い行き先 `old` のフォルダがあっても、`index.json` の `destinations` は渡した行き先だけ

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `.venv/bin/pytest tests/test_storage.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: `fetcher/storage.py` を実装する**

- [ ] **Step 4: テストが通ることを確かめる**

Run: `.venv/bin/pytest -v`
Expected: すべて passed

- [ ] **Step 5: Commit**

```bash
git add fetcher/storage.py tests/test_storage.py
git commit -m "保存処理：成功・失敗・対象外の記録と前回データの引き継ぎ"
```

### Task 3: 部品の約束と為替の部品

**Files:**
- Create: `fetcher/sources/__init__.py`, `fetcher/sources/base.py`, `fetcher/sources/exchange.py`
- Create: `tests/fixtures/frankfurter_currencies.json`, `tests/fixtures/frankfurter_gbp_series.json`
- Test: `tests/test_exchange.py`

**Interfaces:**
- Consumes: `fetcher.http.get_json`, `FetchError`
- Produces:
  - `fetcher.sources.base.Source`：属性 `name: str`, `provider: str`, `label: str`, `refresh_days: int = 0`。メソッド `supports(self, dest: dict) -> bool`（既定は `True`）、`fetch(self, dest: dict, previous: dict | None, now: datetime) -> Any`（`previous` は前回 record の `data`）
  - `fetcher.sources.exchange.ExchangeSource`（`name="exchange"`, `provider="frankfurter"`, `label="為替レート"`）
  - `data` の形：`{"currency": "GBP", "history": [{"date": "2026-10-12", "jpy": 209.91}, ...]}`（日付の昇順、日付の重複なし）
  - `fetcher.sources.SOURCES: list[Source]`（このステップでは `[ExchangeSource()]`）

- [ ] **Step 1: 実際の応答を確認して保存する**

Run:
```bash
curl -sS "https://api.frankfurter.dev/v1/currencies" > tests/fixtures/frankfurter_currencies.json
curl -sS "https://api.frankfurter.dev/v1/2026-10-01..?base=GBP&symbols=JPY" > tests/fixtures/frankfurter_gbp_series.json
```
Expected: どちらも JSON。2つ目に `"rates": {"2026-10-01": {"JPY": ...}, ...}` がある。形が違えばここで止めて設計を見直す

- [ ] **Step 2: 失敗するテストを書く**

`get_json` を monkeypatch し、渡された URL と params を記録する偽物にする。対応通貨一覧はモジュール内でキャッシュするので、各テストの前にキャッシュを消す fixture を用意する。

- `test_first_fetch_requests_365_days`：`previous=None`、`now=2026-10-13` → URL が `https://api.frankfurter.dev/v1/2025-10-13..`、params が `{"base": "GBP", "symbols": "JPY"}`
- `test_parses_series_into_history`：保存した fixture → `history` が日付の昇順、各要素が `{"date", "jpy"}`、`jpy` が fixture の値と一致
- `test_incremental_fetch_starts_from_last_date`：前回の最終日が `2026-10-09` → URL が `.../v1/2026-10-09..`
- `test_merge_overwrites_same_date_and_keeps_old`：前回 `[10-08: 209.04, 10-09: 209.00]`、今回 `[10-09: 209.22, 10-12: 209.91]` → `[10-08: 209.04, 10-09: 209.22, 10-12: 209.91]`
- `test_weekend_no_new_rates_keeps_history`：今回の応答の `rates` が前回の最終日だけ（または空）→ 前回と同じ `history`
- `test_supports_listed_currency_only`：一覧に `GBP` はあり `TWD` は無い → `True` / `False`
- `test_supports_true_when_currency_list_fails`：一覧の取得で `FetchError` → `True`

- [ ] **Step 3: テストが失敗することを確かめる**

Run: `.venv/bin/pytest tests/test_exchange.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 4: `base.py`・`exchange.py`・`sources/__init__.py` を実装する**

- [ ] **Step 5: テストが通ることを確かめる**

Run: `.venv/bin/pytest -v`
Expected: すべて passed

- [ ] **Step 6: Commit**

```bash
git add fetcher/sources tests/test_exchange.py tests/fixtures
git commit -m "為替の部品（Frankfurter）"
```

### Task 4: 司令塔（runner と main）

**Files:**
- Create: `fetcher/runner.py`, `fetcher/main.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: Task 1〜3 のすべて
- Produces:
  - `fetcher.runner.Summary`（dataclass：`ok: int`, `error: int`, `unsupported: int`, `kept: int`）。`kept` は `refresh_days` により取り直さなかった件数
  - `pick_source(candidates: list[Source], dest: dict) -> Source | None`
  - `needs_refresh(previous: dict | None, source: Source, now: datetime) -> bool`：`refresh_days == 0`、前回なし、前回が `ok` でない、前回の `provider` が違う、前回の `updated_at` から `refresh_days` 日以上経った、のどれかなら `True`
  - `run(destinations: list[dict], sources: list[Source], data_dir: Path, now: datetime) -> Summary`
  - `fetcher.main.main(argv: list[str] | None = None) -> int`：`--config`（既定 `config/destinations.json`）、`--data-dir`（既定 `site/data`）。設定ファイルが読めない → 1。`ok + kept == 0` かつ `error > 0`（全部失敗）→ 1。それ以外 → 0
  - 実行方法：`.venv/bin/python -m fetcher.main`

- [ ] **Step 1: 失敗するテストを書く**

テスト用に偽の部品を作る（`name`・`provider`・`supports` の結果・`fetch` の戻り値または例外を指定できるもの）。

- `test_one_failing_source_does_not_stop_others`：部品 A が例外、部品 B が成功 → A は `error`、B は `ok` で保存され、`Summary(ok=1, error=1, unsupported=0, kept=0)`
- `test_error_message_is_saved`：`FetchError("通信に失敗しました")` → record の `error` がその文
- `test_unsupported_when_no_candidate_supports`：`supports` が `False` → `status == "unsupported"`、`unsupported == 1`、`error == 0`
- `test_second_provider_used_when_first_unsupported`：同じ `name` の部品が2つ（1つ目は非対応）→ 2つ目の `provider` で保存
- `test_refresh_days_skips_recent_ok`：`refresh_days=30`、前回 `ok` が10日前 → `fetch` が呼ばれず、`kept == 1`、ファイルは前回のまま
- `test_refresh_days_refetches_after_error`：同じ条件で前回が `error` → `fetch` が呼ばれる
- `test_previous_data_passed_to_fetch`：前回 record の `data` が `fetch` の `previous` に渡る
- `test_index_written_with_current_destinations`：`run` 後に `index.json` があり、`destinations` が渡した行き先と同じ順
- `test_main_returns_1_when_all_failed` / `test_main_returns_0_when_partly_failed`（`SOURCES` を偽の部品に差し替える）

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `.venv/bin/pytest tests/test_runner.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: `runner.py`・`main.py` を実装する**

- 例外は `except Exception` で受け、メッセージは `FetchError` ならそのまま、それ以外は `f"{type(e).__name__}: {e}"` の先頭200文字
- 行き先 × 情報ごとに1行ログ（例：`london exchange ok`）、最後に「成功 n 件・失敗 m 件・対象外 k 件・据え置き j 件」

- [ ] **Step 4: テストが通ることを確かめる**

Run: `.venv/bin/pytest -v`
Expected: すべて passed

- [ ] **Step 5: 本物の API で動かす**

Run: `.venv/bin/python -m fetcher.main`
Expected: `london exchange ok` と表示され、`site/data/london/exchange.json` に約250日分の `history` がある。`site/data/index.json` がある

- [ ] **Step 6: Commit**

```bash
git add fetcher/runner.py fetcher/main.py tests/test_runner.py site/data
git commit -m "司令塔：全行き先×全情報の取得と、失敗の切り分け"
```

### Task 5: 画面（カードの枠と為替の表示）

**Files:**
- Create: `site/index.html`, `site/style.css`, `site/app.js`

**Interfaces:**
- Consumes: `site/data/index.json`、`site/data/{id}/{name}.json`（Task 2・4 の形）
- Produces（Task 6〜9 で表示部分を足すときの約束）：
  - `app.js` の `RENDERERS = { exchange: renderExchange }`。各関数は `(data, record) => HTMLElement` で、区切りの中身だけを作る
  - 共通の `renderSection(record, label)`：見出し、右上の「最終更新：10/13 6:00」、状態の表示（spec 8 の文言そのまま）、下の「出典：{provider}」を作り、`status` が `ok` か `error` で `data` があるときだけ `RENDERERS[name]` を呼ぶ
  - `RENDERERS` に無い情報は「この情報の表示はまだ用意されていません」と出す
  - 提供者の表示名 `PROVIDER_NAMES = { frankfurter: "Frankfurter" }`
  - 書式の関数 `fmtDate("2026-10-13") -> "10/13（火）"`、`fmtDateTime(iso) -> "10/13 6:00"`

- [ ] **Step 1: 画面を作る**

- `index.html`：`<html lang="ja">`、viewport の meta、Chart.js `https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js`
- レイアウト：カードの並びを CSS Grid で。幅 640px 未満は1列、1024px 未満は2列、それ以上は3列
- 為替の区切り（spec 8）：「1 GBP = 209.91 円」、前日比・30日前比（円と％、上がったら赤・下がったら青）、折れ線グラフと「30日／90日／1年」の切り替えボタン（初期は90日）
- 個別ファイルが 404 のときは、その区切りだけ「データがまだありません」

- [ ] **Step 2: 手元で表示して確かめる**

`site/` を配信する手元のサーバーを起動し（`python3 -m http.server 8000 -d site`。Claude はプレビュー機能の起動設定から起動する）、ブラウザで `http://localhost:8000` を開く。
Expected: ロンドンのカードに為替の値・前日比・グラフ・「最終更新」「出典：Frankfurter」が出る。開発者ツールのコンソールにエラーが無い。スマホ幅（375px）で1列になり、横にはみ出さない

- [ ] **Step 3: 失敗表示を確かめる**

`site/data/london/exchange.json` の `status` を一時的に `"error"`、`error` を `"テスト"` に書き換えて再読み込み → 「⚠ 取得に失敗しました（10/13 6:00 時点のデータを表示中）」とグラフが出る。確認後 `git checkout site/data` で戻す

- [ ] **Step 4: Commit**

```bash
git add site/index.html site/style.css site/app.js
git commit -m "画面：カードの枠と為替の表示"
```

- [ ] **Step 5: ここで止める（ステップ1の終わり）**

利用者に、自分で確認する方法（取得コマンド・サーバーの起動・ブラウザで見る場所・失敗表示の試し方）を説明し、OK をもらってから次へ進む

---

## ステップ2：情報と行き先を増やす

Task 6〜9 はどれも同じ流れで進める：①実際の応答を curl で確かめて `tests/fixtures/` に保存 → ②失敗するテストを書く → ③失敗を確かめる → ④部品を実装して `SOURCES` に足す → ⑤テストが通るのを確かめる → ⑥`app.js` に表示部分を足し、`PROVIDER_NAMES` を足す → ⑦`python -m fetcher.main` を実行してブラウザで確かめる → ⑧Commit。各 Task には、決めておくべきことだけを書く。

### Task 6: 天気予報（Open-Meteo）

**Files:** Create `fetcher/sources/forecast.py`, `tests/test_forecast.py`, `tests/fixtures/openmeteo_forecast_london.json` / Modify `fetcher/sources/__init__.py`, `site/app.js`, `site/style.css`

**Interfaces:**
- Produces：`ForecastSource`（`name="forecast"`, `provider="open-meteo"`, `label="天気予報（16日間）"`）
- 取得：`https://api.open-meteo.com/v1/forecast`、params `latitude`, `longitude`, `daily="temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum,precipitation_probability_max"`, `forecast_days=16`, `timezone="auto"`
- `data`：`{"timezone": "Europe/London", "days": [{"date", "tmax", "tmin", "code", "precip", "precip_prob"}]}`

テスト：
- `test_parses_16_days`：fixture → `len(days) == 16`、1日目の各値が fixture の `daily` の先頭と一致
- `test_null_values_kept_as_none`：`precipitation_probability_max` の一部が `null` → `None` のまま（落ちない）
- `test_requests_expected_params`：上の params が渡る

画面：横スクロールの列（日付・天気の絵文字と短い名前・最高／最低気温・降水確率）。WMO コードの対応表を `app.js` に置く（0 ☀ 快晴、1 🌤 晴れ、2 ⛅ 晴れ時々曇り、3 ☁ 曇り、45/48 🌫 霧、51/53/55/56/57 🌦 霧雨、61/63/65/66/67/80/81/82 🌧 雨、71/73/75/77/85/86 ❄ 雪、95/96/99 ⛈ 雷雨。対応表に無いコードは「—」）

Commit: `天気予報の部品と表示`

### Task 7: 月ごとの気候（Open-Meteo 過去データ）

**Files:** Create `fetcher/sources/climate.py`, `tests/test_climate.py`, `tests/fixtures/openmeteo_archive_small.json`（手で作る小さな応答：2年 × 1月・2月の数日分） / Modify `fetcher/sources/__init__.py`, `site/app.js`, `site/style.css`

**Interfaces:**
- Produces：`ClimateSource`（`name="climate"`, `provider="open-meteo"`, `label="月ごとの気候"`, `refresh_days=30`）
- 取得：`https://archive-api.open-meteo.com/v1/archive`、params `latitude`, `longitude`, `start_date=f"{now.year - 10}-01-01"`, `end_date=f"{now.year - 1}-12-31"`, `daily="temperature_2m_mean,precipitation_sum"`, `timezone="auto"`
- `data`：`{"period": "2016〜2025年の平均", "months": [{"month": 1, "temp": -3.2, "precip": 105.0}, ... 12件]}`
  - `temp`：その月の日平均気温の平均（小数1桁）
  - `precip`：年ごとの月合計の平均（小数1桁）
  - `null` の日は計算から外す。値が1つも無い月は `None`

テスト：
- `test_monthly_temperature_mean`：手で作った fixture → 1月の `temp` が手計算の値
- `test_monthly_precip_is_mean_of_yearly_totals`：2年分の1月合計が 10 と 20 → `precip == 15.0`
- `test_null_days_ignored`
- `test_requests_last_10_full_years`：`now=2026-10-13` → `start_date="2016-01-01"`, `end_date="2025-12-31"`
- `test_always_12_months`

本物の応答の確認（Step ①）は10年分で大きいので、fixture には保存せず、件数（約3650日）と項目名だけ確かめる。

画面：12か月の表（月・平均気温・降水量）。スマホでは横スクロール。今月の列に背景色

Commit: `月ごとの気候の部品と表示`

### Task 8: 祝日（Nager.Date）

**Files:** Create `fetcher/sources/holidays.py`, `tests/test_holidays.py`, `tests/fixtures/nager_gb_2026.json`, `tests/fixtures/nager_available.json` / Modify `fetcher/sources/__init__.py`, `site/app.js`

**Interfaces:**
- Produces：`HolidaysSource`（`name="holidays"`, `provider="nager-date"`, `label="祝日（今後6か月）"`）
- 対応国：`https://date.nager.at/api/v3/AvailableCountries` の `countryCode` にあるか（1回の実行でキャッシュ。一覧の取得に失敗したら `True`）
- 取得：`https://date.nager.at/api/v3/PublicHolidays/{年}/{country_code}` を、今日の年と「今日 + 183日」の年について（同じなら1回）
- 絞り込み：今日 〜 今日 + 183日。`global` が真のもの、または `holiday_region` が設定されていて `counties` にそれを含むもの
- `data`：`{"holidays": [{"date", "local_name", "name"}]}`（日付の昇順）

テスト：
- `test_filters_to_england_for_gb_eng`：GB の fixture、`holiday_region="GB-ENG"` → スコットランドだけの祝日（`counties` が `["GB-SCT"]` のもの）が入らず、イングランドを含む祝日は入る
- `test_without_region_only_global`：`holiday_region` 無し → `global: true` だけ
- `test_window_is_today_to_183_days`：範囲外の日付が入らない
- `test_fetches_two_years_when_window_crosses_new_year`：`now=2026-10-13` → 2026 と 2027 の両方を取得
- `test_supports_uses_available_countries`：`GB` → `True`、`TH` → `False`

画面：一覧（「12/25（金） Christmas Day」。`local_name` と `name` が違えば両方を出す）。0件なら「今後6か月の祝日はありません」

Commit: `祝日の部品と表示`

### Task 9: 海外安全情報（外務省）と変化の検出

**Files:** Create `fetcher/sources/safety.py`, `tests/test_safety.py`, `tests/fixtures/mofa_0044L.xml`, `tests/fixtures/mofa_0066L.xml` / Modify `fetcher/sources/__init__.py`, `site/app.js`, `site/style.css`

**Interfaces:**
- Consumes：`fetcher.http.get_bytes`
- Produces：
  - `SafetySource`（`name="safety"`, `provider="mofa"`, `label="海外安全情報"`）
  - `parse_safety(xml_bytes: bytes) -> dict`：`{"level", "infection_level", "title", "url", "mofa_updated"}`
  - `apply_change(current: dict, previous: dict | None, now: datetime) -> dict`：`current` に `changed`, `changed_at`, `previous_level`, `previous_infection_level` を足して返す
- 取得：`https://www.ezairyu.mofa.go.jp/opendata/country/{mofa_code}L.xml`
- `level`：ルート要素の**直下**の `riskLevel1`〜`riskLevel4` のうち、値が `1` の最大の数字。無ければ 0。直下に `riskLevel1`〜`4` が1つも無ければ `ValueError("外務省データの形式が想定と違います")`
- `infection_level`：同様に `infectionLevel1`〜`4`
- `title`：`riskTitle`（空なら `""`）、`mofa_updated`：ルートの `lastModified` 属性
- `url`：`riskUrl` が空でなければそれ、空なら `infoUrl`（Step ①で、どちらのページが利用者に役立つかを開いて確かめ、違えばここを直す）
- 変化の扱い：
  - 前回なし → `changed=False`、他は `None`
  - 前回とどちらかのレベルが違う → `changed=True`、`changed_at=now`、`previous_*` に前回の値
  - 同じ → 前回の `changed_at`・`previous_*` を引き継ぎ、`changed` は `changed_at` から7日以内なら `True`

テスト：
- `test_uk_level_0`：`mofa_0044L.xml` → `level == 0`, `infection_level == 0`
- `test_thailand_level_3`：`mofa_0066L.xml` → `level == 3`、`title` が「タイの危険情報」で始まる
- `test_uses_top_level_only`：手で作った XML（直下は全部0、入れ子の地域要素に `riskLevel4=1`）→ `level == 0`
- `test_missing_risk_fields_raises`：`riskLevel` の無い XML → `ValueError`
- `test_first_time_not_changed`
- `test_level_change_detected`：前回 1、今回 2 → `changed=True`, `previous_level=1`, `changed_at` が now
- `test_change_flag_lasts_7_days`：変化を検出して6日後は `True`、8日後は `False`（`changed_at` はそのまま）

画面：危険レベルを色付きの札で（0 灰色「危険情報なし」、1 黄 `#f5d000`「レベル1：十分注意してください」、2 橙 `#f39800`「レベル2：不要不急の渡航は止めてください」、3 赤 `#e60012`「レベル3：渡航は止めてください（渡航中止勧告）」、4 濃赤 `#7b0000`「レベル4：退避してください。渡航は止めてください（退避勧告）」）。感染症危険レベルも同じ形で小さく。`title` と外務省ページへのリンク。`changed` が真ならカード全体の枠を太い赤にし、区切りの先頭に「⚠ 変化あり：レベル1→2（10/13 検出）」

Commit: `海外安全情報の部品と変化の表示`

### Task 10: 行き先を3都市にして、全体を確かめる

**Files:** Modify `config/destinations.json`（spec 4 の3都市すべて）, `site/data/`

- [ ] **Step 1: 3都市にして取得する**

Run: `.venv/bin/python -m fetcher.main`
Expected: 最後の行が「成功 15 件・失敗 0 件・対象外 0 件・据え置き 0 件」

- [ ] **Step 2: もう一度取得して、気候が据え置かれることを確かめる**

Run: `.venv/bin/python -m fetcher.main`
Expected: 「成功 12 件・失敗 0 件・対象外 0 件・据え置き 3 件」

- [ ] **Step 3: 対象外の表示を確かめる**

一時的にバンコク（`country_code: "TH"`, `mofa_code: "0066"`, `currency: "THB"`, `lat: 13.75`, `lon: 100.50`）を足して取得 → 祝日だけ「対象外」、他は表示される。確認後、設定と `site/data/bangkok/` を元に戻す

- [ ] **Step 4: わざと1つ失敗させる**

一時的に `exchange.py` の URL を存在しないものに変えて取得 → 3都市とも為替だけ「⚠ 取得に失敗しました（… 時点のデータを表示中）」、他の4種類は更新される。確認後 `git checkout fetcher site/data` で戻す

- [ ] **Step 5: 画面全体を確かめる**

ブラウザで、パソコン幅で3列・スマホ幅（375px）で1列、横はみ出しなし、コンソールエラーなし

- [ ] **Step 6: Commit**

```bash
git add config site/data
git commit -m "行き先を3都市に"
```

- [ ] **Step 7: ここで止める（ステップ2の終わり）**

利用者に確認方法（行き先の足し方、失敗表示・対象外表示の見方）を説明し、OK をもらってから次へ

---

## ステップ3：GitHub Actions で毎日自動取得する

### Task 11: GitHub に置き、毎日の取得を設定する

**Files:** Create `.github/workflows/update.yml`, `README.md`（行き先の足し方と手元での動かし方を短く）

- [ ] **Step 1: 使う Actions の現在の版を確かめる**

`actions/checkout`・`actions/setup-python` の最新の主要版を公式リポジトリで確かめ、その版を書く

- [ ] **Step 2: `update.yml` を書く**

- `on`：`schedule: cron "0 21 * * *"`（日本時間 6:00）、`workflow_dispatch`
- `permissions: contents: write`
- `concurrency: group: update, cancel-in-progress: false`
- job `update`（ubuntu-latest）：checkout → setup-python 3.12 → `pip install -r requirements.txt` → `python -m fetcher.main` → `site/data` に差分があるときだけ `github-actions[bot]` としてコミット（メッセージ `データ更新 YYYY-MM-DD`）して push

- [ ] **Step 3: Commit**

```bash
git add .github README.md
git commit -m "毎日の自動取得（GitHub Actions）"
```

- [ ] **Step 4: GitHub に公開リポジトリを作って push する**

**利用者の確認を取ってから**実行する（外部に公開される操作のため）：`gh repo create destination-watcher --public --source . --push`

- [ ] **Step 5: 手動で実行して確かめる**

Run: `gh workflow run update.yml` → `gh run watch`
Expected: 成功。リポジトリに `データ更新 …` のコミットが増えている（その日のデータが既に最新なら差分なしでコミットされないこともある。その場合はログに「成功 … 件」が出ていればよい）

- [ ] **Step 6: ここで止める（ステップ3の終わり）**

利用者に、GitHub の Actions タブでの実行結果の見方、手動実行のボタン、失敗時の見方を説明する。あわせて、公開リポジトリで60日間活動が無いと定期実行が止まることがあり、その場合は Actions タブから再開できることを伝える

---

## ステップ4：GitHub Pages で公開する

### Task 12: Pages への公開を自動化する

**Files:** Modify `.github/workflows/update.yml`, `README.md`（公開 URL を書く）

- [ ] **Step 1: 使う Actions の現在の版を確かめる**

`actions/configure-pages`・`actions/upload-pages-artifact`・`actions/deploy-pages` の最新の主要版を確かめる

- [ ] **Step 2: `update.yml` に公開の job を足す**

- `on` に `push: branches: [main]` を追加（画面の修正も公開されるように）
- `permissions` に `pages: write`, `id-token: write`
- job `deploy`（`needs: update`）：`ref: main` で最新を checkout → configure-pages → `site/` を upload-pages-artifact → deploy-pages（`environment: github-pages`）

- [ ] **Step 3: Pages を「Actions から公開」に設定する**

**利用者の確認を取ってから**実行：`gh api repos/{owner}/destination-watcher/pages -X POST -f build_type=workflow`

- [ ] **Step 4: Commit して push し、公開を確かめる**

```bash
git add .github README.md
git commit -m "GitHub Pages への公開"
git push
```
Run: `gh run watch`
Expected: `update` と `deploy` が成功。`https://<ユーザー名>.github.io/destination-watcher/` で3都市のカードが出る。ブラウザでスマホ幅にして確かめる

- [ ] **Step 5: ここで止める（ステップ4の終わり）**

利用者に公開 URL を伝え、スマホで開いて確かめてもらう。行き先の足し方（`config/destinations.json` を編集して push → 自動で取得・公開）を説明する
