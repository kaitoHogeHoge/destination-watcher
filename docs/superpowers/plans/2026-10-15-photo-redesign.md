# 都市の写真とカードのデザイン刷新 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 各都市のカードに Wikimedia の写真の帯と要点タイルを付け、旅行誌風のデザインにする。

**Architecture:** 写真は新しい部品 `fetcher/sources/photo.py` が毎朝の取得で（90日に1回）探して保存する。画面は `site/app.js` のカードの組み立てを変え、タイルの中身は `site/summary.js` の `summarize` を使って計算する。

**Tech Stack:** Python 3.12 以上、pytest、素の JavaScript、Node.js のテスト機能

**Spec:** `docs/superpowers/specs/2026-10-15-photo-redesign-design.md`

## Global Constraints

- 文言・寸法・色は spec のものを使う
- 既存のテスト（Python 139・JS 41）を壊さない
- 外部の文字（撮影者名など）は必ず `textContent` で入れる。リンクは http/https のものだけ
- 写真が無くても画面が崩れないこと

## Review Focus

- 代表画像が国旗・地図・紋章（シンガポールなど）→ 写真に回ること（Task 1 にテスト）
- 撮影者の HTML に `<script>` やリンクが入っている → 文字だけになること（Task 1 にテスト）
- 記事名が都市名と違う（例：「ホーチミン市」）・記事が無い → 写真なしで、エラーにしないこと（Task 1 にテスト）
- 写真の URL が読み込めない（削除・通信不可）→ 色の帯に切り替わること（Task 3 で確認）
- 長い都市名・長い撮影者名 → スマホ幅で重ならない・はみ出さないこと（Task 3 で確認）

---

### Task 1: 写真の部品

**Files:** Create `fetcher/sources/photo.py`, `tests/test_photo.py`, `tests/fixtures/wiki_summary_london.json`, `tests/fixtures/wiki_summary_singapore.json`, `tests/fixtures/wiki_media_singapore.json`, `tests/fixtures/commons_london.json` / Modify `fetcher/sources/__init__.py`, `fetcher/http.py`（User-Agent）, `fetcher/config.py`（`photo` の型）, `tests/test_config.py`, `README.md`

**Interfaces:**
- `is_photo_file(name: str) -> bool`
- `file_from_url(url: str) -> str | None`（Commons の URL → `File:…`。thumb の URL にも対応）
- `strip_html(text: str) -> str`
- `PhotoSource.fetch(dest, previous, now) -> dict`（spec 2 の保存形）

テスト：`test_uses_config_photo_first`、`test_uses_summary_image`、`test_skips_flag_and_uses_media_list`、`test_no_article_returns_no_photo`、`test_artist_html_stripped`、`test_artist_missing_is_unknown`、`test_is_photo_file`、`test_file_from_thumb_url`、`test_config_photo_must_be_string`

### Task 2: タイルの中身（summary.js）

**Files:** Modify `site/summary.js` / Test `tests/js/summary.test.js`

**Interfaces:**
- `formatMonths(months: number[]) -> string`（`[6,7,8]`→`6〜8月`、`[2,3,7]`→`2・3・7月`、`[12,1,2]`→`12〜2月`、`[]`→`—`）
- `summarize` の `safety` に `notices`（件数）・`changed` を足す。`forecast` は今のまま（`tmax`・`tmin`・`rainyDays`）

### Task 3: カードの組み立てと見た目

**Files:** Modify `site/app.js`, `site/style.css`

- 写真の帯（spec 3.1）、タイル（3.2）、区切りの一覧化とアイコン、初回はすべて閉じる（3.3）、配色・カード・比較表の写真（3.4）
- 確認：4都市、写真が読み込めないとき（一時的に URL を壊す）、写真なしのデータ、スマホ幅、暗い表示・明るい表示

### Task 4: 公開

- 見本 `site/mockup.html` を削除
- 全テスト → 別の担当のチェック → 指摘の修正 → **利用者の確認を取ってから** push → 公開ページで確認
