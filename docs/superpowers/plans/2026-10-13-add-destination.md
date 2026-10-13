# 行き先の追加・削除ボタン 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GitHub の Actions ページで都市名を入れるだけで、行き先を追加・削除できるようにする。

**Architecture:** `fetcher/destinations.py` が地名検索と設定ファイルの読み書きを行い、`fetcher/add.py`・`fetcher/remove.py` がその入口になる。国→通貨・外務省国番号は `config/countries.json`（`scripts/build_countries.py` で一度だけ生成）から引く。2つの workflow が入口を実行してコミットし、既存の「データ更新」を呼び出す。

**Tech Stack:** Python 3.12 以上、requests、pytest、GitHub Actions（workflow_dispatch・gh CLI）

**Spec:** `docs/superpowers/specs/2026-10-13-add-destination-design.md`（元の設計書 `2026-10-13-destination-watcher-design.md` も前提）

## Global Constraints

- 通信は `fetcher/http.py` を通す（タイムアウト20秒・1回だけ再試行）
- 設定ファイルは `ensure_ascii=False, indent=2` で書き、末尾に改行
- 利用者向けのメッセージはすべて日本語。spec の文言をそのまま使う
- workflow の入力は環境変数経由で渡す。`run:` の中に `${{ inputs.* }}` を書かない
- 見つからない・登録済み・削除対象なしのときは、ファイルを一切変えずに終了コード1
- 既存の 78 + 15 個のテストを壊さない

## Review Focus

- 都市名に `"`・`$(...)`・改行などの記号が入る → コマンドとして実行されず、ただの文字列として検索されること（Task 5：workflow が環境変数経由であることを確認）
- 同じ都市を2回追加する → 2回目は何も変えずに「すでに登録されています」（Task 3 にテスト）
- 地名検索が結果0件（`results` キー自体が無い応答）→ 例外ではなく「見つかりませんでした」（Task 3 にテスト）
- 手で書いた古い行き先（`holiday_region` 付きなど）が追加・削除の書き戻しで消えたり形が変わったりしない（Task 3 にテスト）
- 削除で `site/data` の外を消さない（id に `..` などが入っていても、設定の読み込みで弾かれていること。Task 3 にテスト）

---

### Task 1: 設定の型チェックと、null の対象外扱い

**Files:** Modify `fetcher/config.py`, `fetcher/sources/safety.py`, `fetcher/sources/exchange.py` / Test `tests/test_config.py`, `tests/test_safety.py`, `tests/test_exchange.py`

**Interfaces:**
- Produces：`load_destinations` は `mofa_code`・`currency` の `null` を許す。値があれば文字列必須。`country_code`・`id`・`name`・`country` は文字列必須。`lat`・`lon` は数値必須。トップが配列でない・要素が辞書でないものは飛ばす（トップが配列でなければ `ValueError`）
- `SafetySource.supports(dest)`：`dest.get("mofa_code")` が空でなければ True
- `ExchangeSource.supports(dest)`：`currency` が空なら False、それ以外は今までどおり

テスト：
- `test_null_mofa_code_and_currency_allowed`
- `test_numeric_mofa_code_skipped`（`"mofa_code": 44` → 飛ばす）
- `test_non_dict_entry_skipped`、`test_top_level_not_list_raises`（`ValueError`）
- `test_supports_false_without_mofa_code`（safety）
- `test_supports_false_without_currency`（exchange、通貨一覧の取得なしで False）

Commit: `設定の型チェックと、国番号・通貨が無い行き先の対象外扱い`

### Task 2: 国の対応表

**Files:** Create `scripts/build_countries.py`, `config/countries.json`, `tests/test_build_countries.py`

**Interfaces:**
- `build_table(countries: list[dict], mofa_codes: set[str]) -> dict[str, dict]`：mledoze 形式の国一覧と外務省国番号の集合から `{ISO2: {"currency", "mofa_code"}}` を作る（spec 3.3 の規則。例外 `US`→`1000`、`CA`→`9001` は外務省一覧にあるときだけ使う）
- `read_mofa_codes(xlsx_path) -> set[str]`：`country.xlsx` の「国コード」列（3列目、4桁）を読む。標準ライブラリ（zipfile・xml）だけで読む
- CLI：`python -I scripts/build_countries.py <countries.json> <country.xlsx> > config/countries.json`

テスト（`build_table` に小さな手作りデータを渡す）：
- `test_single_suffix_calling_code`（`+6`/`["6"]` → `0066`）
- `test_multi_digit_suffix`（`+3`/`["54"]` → `0354`。一覧に無ければ `null`）
- `test_us_and_canada_overrides`
- `test_no_currency_is_null`
- `test_calling_code_not_in_mofa_list_is_null`

Step：mledoze 5.1.0 の `countries.json` と外務省の `country.xlsx` をスクラッチ領域にダウンロードし、生成して中身を確かめる（GB→GBP/0044、NO→NOK/0047、SG→SGD/0065、TH→THB/0066、US→USD/1000、VN→VND/0084）

Commit: `国→通貨・外務省国番号の対応表`

### Task 3: 地名検索と設定の書き換え

**Files:** Create `fetcher/destinations.py`, `tests/test_destinations.py`, `tests/fixtures/geocoding_bangkok.json`, `tests/fixtures/geocoding_paris.json`

**Interfaces:**
- `class DestinationError(Exception)`（メッセージは spec の日本語文言）
- `search_city(city: str) -> list[dict]`：spec 3.1 の params。`results` が無ければ `[]`
- `pick_result(results: list[dict], country: str | None) -> dict | None`
- `make_destination(result: dict, countries: dict) -> dict`（spec 3.2）
- `add_destination(config_path: Path, dest: dict) -> None`：重複なら `DestinationError`
- `remove_destination(config_path: Path, data_dir: Path, key: str) -> dict`：消した1件を返す。0件・複数なら `DestinationError`
- 書き戻しは元の項目をすべてそのまま残す（読み込みは生の JSON で行い、`load_destinations` の検証結果では書き戻さない）

テスト：
- `test_pick_first_without_country` / `test_pick_with_country_filter`（パリ：フランス指定でフランスのパリ） / `test_pick_none`
- `test_search_city_no_results_key`（`{"generationtime_ms": 0.1}` → `[]`）
- `test_make_destination_known_country` / `test_make_destination_unknown_country`（currency・mofa_code が `None`）
- `test_add_appends_and_keeps_existing_fields`（`holiday_region` 付きの既存項目がそのまま残る、日本語がそのまま）
- `test_add_duplicate_id` / `test_add_duplicate_name_and_country`（ファイルが変わらない）
- `test_remove_by_name_deletes_data_dir` / `test_remove_by_id`
- `test_remove_unknown_lists_registered` / `test_remove_ambiguous`
- `test_remove_rejects_unsafe_id`（id が `../x` の項目は削除対象にしない）

Commit: `地名検索と、行き先の追加・削除`

### Task 4: 入口（add / remove）

**Files:** Create `fetcher/add.py`, `fetcher/remove.py`, `tests/test_add_remove.py`

**Interfaces:**
- `fetcher.add.main(argv) -> int`：`--city`（必須）、`--country`、`--config`（既定 `config/destinations.json`）、`--countries`（既定 `config/countries.json`）
  - 成功：「{name}（{country}）を追加しました」＋ 対象外になる情報の一覧（`SOURCES` の `supports` で判定し、`label` を並べる。無ければ「すべての情報が表示されます」）
  - 失敗：理由を出して 1
  - 出力は標準出力と、環境変数 `GITHUB_STEP_SUMMARY` があればそのファイルにも追記
- `fetcher.remove.main(argv) -> int`：`--name`（必須）、`--config`、`--data-dir`（既定 `site/data`）。成功：「{name}（{country}）を削除しました」

テスト（`fake_http` と `tmp_path` を使う）：
- `test_add_success_writes_config_and_summary`（`GITHUB_STEP_SUMMARY` に文言）
- `test_add_reports_unsupported`（祝日が対象外の国 → 「対象外の情報：祝日（今後6か月）」）
- `test_add_not_found_returns_1_and_keeps_file`
- `test_remove_success` / `test_remove_not_found_returns_1`

Commit: `行き先の追加・削除の入口`

### Task 5: 自動実行と公開

**Files:** Create `.github/workflows/add-destination.yml`, `.github/workflows/remove-destination.yml` / Modify `README.md`

- spec 6 のとおり。入力は `env:` で `CITY`・`COUNTRY`・`NAME` に入れて `"$CITY"` で渡す
- コミット後 `git pull --rebase origin main` → `git push` → `gh workflow run update.yml`（`GH_TOKEN: ${{ github.token }}`）
- README：「行き先を足す」を Actions ボタンの手順に書き換え（手で編集する方法も残す）、mledoze/countries（ODbL-1.0）の出典を追記
- **利用者の確認を取ってから** push し、Actions から「バンコク」を追加 → 公開ページで確認 → 「バンコク」を削除 → 消えたことを確認

Commit: `行き先の追加・削除ボタン（GitHub Actions）`
