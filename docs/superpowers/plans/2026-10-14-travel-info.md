# 旅行前・旅行中の情報の追加 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 外務省のお知らせ・関連リンク、日の出・日の入り・昼の長さ、ベストシーズン、現地時刻、1時間ごとの天気を画面に足す。

**Architecture:** 取得側は既存の部品（safety・forecast・climate）の出力に項目を足し、部品に `data_version` を持たせて気候を取り直させる。画面側は計算を `site/summary.js` に置いてテストし、描画は `site/app.js`。1時間ごとの天気だけは画面から Open-Meteo に直接問い合わせる。

**Tech Stack:** Python 3.12 以上、pytest、素の JavaScript、Node.js のテスト機能

**Spec:** `docs/superpowers/specs/2026-10-14-travel-info-design.md`

## Global Constraints

- 文言は spec のものをそのまま使う
- 既存のテスト（Python 118・JS 15）を壊さない
- 新しい外部ライブラリは使わない
- 画面の新しい部分も、失敗したら「—」や説明の文を出し、他の表示を止めない

## Review Focus

- 極夜・白夜の日（トロムソの12月・6月）に、Open-Meteo の `sunrise`/`sunset` が欠ける・おかしな値になる → 落ちずに「極夜」「白夜」と出ること（Task 2 にテスト）
- 古い形式の保存データ（`notices`・`links`・`sunrise`・`daylight` が無い）→ 画面が落ちず、その部分だけ出ないこと（Task 5 で確認）
- 端末の時間帯が日本以外（海外で開いた）→ 時差は「日本との差」で正しく出ること（Task 4 にテスト）
- 1時間ごとの天気の取得が遅い・失敗・形が違う → 10秒で諦めて説明を出し、他は表示されること（Task 4・5）
- 外務省のお知らせの日付が読めない・見出しが空 → その項目だけ除くこと（Task 1 にテスト）

---

### Task 1: 外務省のお知らせと関連ページ

**Files:** Modify `fetcher/sources/safety.py` / Test `tests/test_safety.py`, `tests/fixtures/mofa_0066L.xml`（`mail` 2件・`wideareaSpot` 1件・関連 URL を含む形に作り直す）

**Interfaces:**
- `parse_notices(root: ET.Element, now: datetime) -> list[dict]`（spec 2.1）
- `parse_links(root: ET.Element) -> list[dict]`（spec 2.2）
- `parse_safety(xml_bytes, now)` の戻り値に `notices`・`links` を足す（`now` を引数に足す。呼び出し元を直す）

テスト：`test_notices_from_mail_and_spot`、`test_notices_within_30_days_newest_first_max_5`、`test_notice_with_bad_date_or_empty_title_skipped`、`test_mail_url_uses_keycd`、`test_links_in_order_and_skip_empty`

### Task 2: 日の出・日の入り・昼の長さ

**Files:** Modify `fetcher/sources/forecast.py`, `fetcher/sources/climate.py`, `fetcher/sources/base.py`, `fetcher/storage.py`, `fetcher/runner.py` / Test `tests/test_forecast.py`, `tests/test_climate.py`, `tests/test_runner.py`, `tests/test_storage.py`

**Interfaces:**
- `Source.data_version: int = 1`、`ClimateSource.data_version = 2`
- `ok_record(name, provider, data, now, data_version=1)` が `data_version` を書く。`error_record` は前回の `data_version` を引き継ぐ
- `needs_refresh` は前回の `data_version`（無ければ 1）が部品と違えば True
- forecast の各日に `sunrise`・`sunset`（"HH:MM" か None）、`daylight_h`
- climate の各月に `daylight`

テスト：`test_parses_sun_times`、`test_polar_night_values`（`daylight_duration` 0 と `sunrise` が欠ける応答）、`test_monthly_daylight`、`test_data_version_change_forces_refresh`、`test_ok_record_has_data_version`

Step：極夜・白夜の実際の応答をトロムソで確かめる（12月・6月の日付を archive で取得）

### Task 3: index.json の緯度経度

**Files:** Modify `fetcher/storage.py` / Test `tests/test_storage.py`

- `write_index` の各行き先に `lat`・`lon` を足す。テスト：既存の `test_write_index_lists_given_destinations_only` を更新

### Task 4: 画面の計算（summary.js）

**Files:** Modify `site/summary.js` / Test `tests/js/summary.test.js`

**Interfaces:**
- `bestSeason(months) -> number[]`（月の番号、昇順。spec 4）
- `timeDiffText(timeZone, nowMs) -> {local: "8:15", diff: "日本より−8時間"} | null`（不正な時間帯は null）
- `parseHourly(raw) -> [{time: "16:00", code, temp, prob}] | null`（形が違えば null）
- `summarize` の `climate` に `best: number[]` を足す

テスト：ロンドン型（夏3か月）、シンガポール型（雨の少ない月）、欠けた月、3か月未満、時差（+9 の地域で「日本と同じ時刻」、−8、+5:30 → 「日本より−3時間30分」）、`parseHourly` の正常・欠け・形違い

### Task 5: 画面の描画（app.js / style.css）

**Files:** Modify `site/app.js`, `site/style.css`

- 安全情報：お知らせ一覧と関連リンク（spec 2.3）
- 天気予報：各日に日の出・日の入り、上に今日の昼の長さ
- 気候：昼の長さの行、★、目安の文
- 比較の一覧：今月の気候に目安
- カード見出し：現地時刻と時差（1分ごと更新）
- これから12時間の天気：直接取得、10秒で打ち切り、失敗時の文言

確認：手元のサーバーで、4都市（パリ含む）の表示、スマホ幅、1時間ごとの天気の失敗（問い合わせ先を一時的に壊す）、古い形式のデータでも落ちないこと

### Task 6: 公開

- 全テスト → 別の担当のチェック → 指摘の修正 → **利用者の確認を取ってから** push → 公開ページで確認
