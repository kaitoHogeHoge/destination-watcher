// 実行方法：node --test tests/js/
const test = require("node:test");
const assert = require("node:assert/strict");
const {
  isStale, ageText, summarize, daysBefore, bestSeason, timeDiffText, parseHourly,
  parseAmount, currencyDigits, toYen, fromYen, formatAmount, fxPosition, sortRows, formatMonths,
} = require("../../site/summary.js");

const HOUR = 60 * 60 * 1000;
const GENERATED = "2026-10-13T06:00:00+09:00";
const GENERATED_MS = Date.parse(GENERATED);

// ---------- 古いデータの警告 ----------

test("36時間以内なら古くない", () => {
  assert.equal(isStale(GENERATED, GENERATED_MS + 35 * HOUR), false);
});

test("36時間を過ぎたら古い", () => {
  assert.equal(isStale(GENERATED, GENERATED_MS + 37 * HOUR), true);
});

test("読めない日時は古いとみなす", () => {
  assert.equal(isStale("2026-10-13", GENERATED_MS), true);
  assert.equal(isStale(undefined, GENERATED_MS), true);
});

test("経過時間の表示", () => {
  assert.equal(ageText(GENERATED, GENERATED_MS + 5 * HOUR), "5時間前");
  assert.equal(ageText(GENERATED, GENERATED_MS + 50 * HOUR), "2日前");
  assert.equal(ageText("壊れた値", GENERATED_MS), "");
});

// ---------- 比較の一覧 ----------

function ok(data) {
  return { status: "ok", data };
}

const TODAY = "2026-10-13";

test("daysBefore は日付をさかのぼる", () => {
  assert.equal(daysBefore("2026-10-13", 30), "2026-09-13");
});

test("為替：30日前比の％と円安・円高", () => {
  const history = [
    { date: "2026-09-11", jpy: 200 },
    { date: "2026-09-14", jpy: 204 },
    { date: "2026-10-13", jpy: 210 },
  ];
  const s = summarize({ exchange: ok({ currency: "GBP", history }) }, TODAY);
  // 30日前（9/13）以前で最も新しいのは 9/11 の 200 → +5%
  assert.deepEqual(s.exchange, { status: "ok", pct: 5, word: "円安", position: null });
});

test("為替：30日前の値が無ければ pct は null", () => {
  const history = [{ date: "2026-10-12", jpy: 210 }];
  const s = summarize({ exchange: ok({ currency: "GBP", history }) }, TODAY);
  assert.deepEqual(s.exchange, { status: "ok", pct: null, word: null, position: null });
});

test("天気：今日から7日の平均と雨の日数（降水確率50%以上）", () => {
  const days = [
    { date: "2026-10-12", tmax: 99, tmin: 99, precip_prob: 100 }, // 過去の日は使わない
    ...[0, 1, 2, 3, 4, 5, 6, 7].map((i) => ({
      date: `2026-10-${13 + i}`,
      tmax: 20 + i,
      tmin: 10,
      precip_prob: [50, 49, 80, null, 0, 100, 10, 100][i], // 8日目は範囲外
    })),
  ];
  const s = summarize({ forecast: ok({ days }) }, TODAY);
  assert.deepEqual(s.forecast, { status: "ok", tmax: 23, tmin: 10, rainyDays: 3, days: 7 });
});

test("天気：値が null の日は平均から外す", () => {
  const days = [
    { date: "2026-10-13", tmax: 20, tmin: null, precip_prob: null },
    { date: "2026-10-14", tmax: null, tmin: null, precip_prob: null },
  ];
  const s = summarize({ forecast: ok({ days }) }, TODAY);
  assert.deepEqual(s.forecast, { status: "ok", tmax: 20, tmin: null, rainyDays: 0, days: 2 });
});

test("気候：今月の値", () => {
  const months = Array.from({ length: 12 }, (_, i) => ({ month: i + 1, temp: i, precip: i * 10 }));
  const s = summarize({ climate: ok({ months }) }, TODAY);
  assert.deepEqual(s.climate, { status: "ok", temp: 9, precip: 90, best: bestSeason(months) });
});

test("祝日：今日以降で最も近いもの", () => {
  const holidays = [
    { date: "2026-10-12", local_name: "昨日", name: "Yesterday" },
    { date: "2026-12-25", local_name: "Christmas Day", name: "Christmas Day" },
  ];
  const s = summarize({ holidays: ok({ holidays }) }, TODAY);
  assert.deepEqual(s.holidays, { status: "ok", date: "2026-12-25", name: "Christmas Day" });
});

test("祝日：無ければ date は null", () => {
  const s = summarize({ holidays: ok({ holidays: [] }) }, TODAY);
  assert.deepEqual(s.holidays, { status: "ok", date: null, name: null });
});

test("安全情報：危険レベル", () => {
  const s = summarize({ safety: ok({ level: 3, infection_level: 0 }) }, TODAY);
  assert.deepEqual(s.safety, { status: "ok", level: 3, notices: null, changed: false });
});

test("記録が無い・対象外・失敗の扱い", () => {
  const s = summarize(
    {
      exchange: null,
      holidays: { status: "unsupported", data: null },
      safety: { status: "error", data: { level: 1 } },
      forecast: { status: "error", data: null },
    },
    TODAY,
  );
  assert.deepEqual(s.exchange, { status: "missing" });
  assert.deepEqual(s.holidays, { status: "unsupported" });
  assert.deepEqual(s.safety, { status: "error", level: 1, notices: null, changed: false }); // 前回のデータで計算し、失敗の印を残す
  assert.deepEqual(s.forecast, { status: "missing" });
  assert.deepEqual(s.climate, { status: "missing" });
});

test("データの形が壊れていても例外にしない", () => {
  const s = summarize({ exchange: ok({ history: "壊れた" }), forecast: ok({}) }, TODAY);
  assert.deepEqual(s.exchange, { status: "broken" });
  assert.deepEqual(s.forecast, { status: "broken" });
});

// ---------- ベストシーズン ----------

function monthsOf(temps, precips) {
  return temps.map((t, i) => ({ month: i + 1, temp: t, precip: precips[i] }));
}

test("ベストシーズン：ロンドン型は夏の3か月", () => {
  const months = monthsOf(
    [4.7, 6.1, 7.5, 9.6, 13.3, 16.8, 18.7, 18.2, 15.7, 12.2, 8.1, 6.5],
    [62.9, 54.2, 56.9, 40.1, 54.9, 62.5, 60.0, 49.3, 64.0, 78.3, 68.5, 67.0],
  );
  assert.deepEqual(bestSeason(months), [6, 7, 8]);
});

test("ベストシーズン：気温が同じなら雨の少ない月", () => {
  const months = monthsOf(Array(12).fill(27), [240, 110, 160, 170, 170, 130, 150, 150, 140, 160, 250, 300]);
  assert.deepEqual(bestSeason(months), [2, 6, 9]);
});

test("ベストシーズン：値の欠けた月は対象外、3か月未満ならある分だけ", () => {
  const months = monthsOf([22, null, 21, null, null, null, null, null, null, null, null, null], Array(12).fill(10));
  assert.deepEqual(bestSeason(months), [1, 3]);
  assert.deepEqual(bestSeason([]), []);
  assert.deepEqual(bestSeason(undefined), []);
});

// ---------- 現地時刻と時差 ----------

const NOW_UTC = Date.UTC(2026, 9, 13, 23, 15); // 日本時間 10/14 8:15

test("時差：ロンドン（夏時間）は日本より−8時間", () => {
  assert.deepEqual(timeDiffText("Europe/London", NOW_UTC), { local: "0:15", diff: "日本より−8時間" });
});

test("時差：日本と同じ時間帯", () => {
  assert.deepEqual(timeDiffText("Asia/Seoul", NOW_UTC), { local: "8:15", diff: "日本と同じ時刻" });
});

test("時差：30分単位と、日本より進んでいる地域", () => {
  assert.deepEqual(timeDiffText("Asia/Kolkata", NOW_UTC), { local: "4:45", diff: "日本より−3時間30分" });
  assert.deepEqual(timeDiffText("Pacific/Auckland", NOW_UTC), { local: "12:15", diff: "日本より+4時間" });
});

test("時差：読めない時間帯は null", () => {
  assert.equal(timeDiffText("Mars/Olympus", NOW_UTC), null);
  assert.equal(timeDiffText(undefined, NOW_UTC), null);
});

// ---------- 1時間ごとの天気 ----------

test("1時間ごとの天気の読み取り", () => {
  const raw = {
    hourly: {
      time: ["2026-10-14T07:00", "2026-10-14T08:00"],
      temperature_2m: [5.2, null],
      precipitation_probability: [80, 20],
      weather_code: [61, 3],
    },
  };
  assert.deepEqual(parseHourly(raw), [
    { time: "7:00", temp: 5.2, prob: 80, code: 61, night: false },
    { time: "8:00", temp: null, prob: 20, code: 3, night: false },
  ]);
});

test("1時間ごとの天気：形が違えば null", () => {
  assert.equal(parseHourly({}), null);
  assert.equal(parseHourly({ hourly: { time: "x" } }), null);
  assert.equal(parseHourly(null), null);
});

test("1時間ごとの天気：昼か夜か（is_day）も読む", () => {
  const raw = { hourly: { time: ["2026-10-14T05:00"], temperature_2m: [9], precipitation_probability: [0], weather_code: [0], is_day: [0] } };
  assert.equal(parseHourly(raw)[0].night, true);
  const noFlag = { hourly: { time: ["2026-10-14T05:00"], weather_code: [0] } };
  assert.equal(parseHourly(noFlag)[0].night, false);
});

// ---------- 円換算 ----------

test("金額の読み取り：半角・全角・カンマ・空白", () => {
  assert.equal(parseAmount("25"), 25);
  assert.equal(parseAmount("２５"), 25);
  assert.equal(parseAmount("1,234.5"), 1234.5);
  assert.equal(parseAmount("１，２３４．５"), 1234.5);
  assert.equal(parseAmount(" 10 000 "), 10000);
});

test("金額の読み取り：空欄・おかしな入力は null", () => {
  for (const bad of ["", "   ", "abc", "1.2.3", "-5", "1e3", null, undefined]) {
    assert.equal(parseAmount(bad), null, String(bad));
  }
});

test("通貨の普段の桁", () => {
  assert.equal(currencyDigits("GBP"), 2);
  assert.equal(currencyDigits("KRW"), 0);
  assert.equal(currencyDigits("ZZZ"), 2); // 知らない通貨は2桁
});

test("換算：外貨→円は整数、円→外貨は通貨の桁", () => {
  assert.equal(toYen(25, 209.91), 5248);
  assert.equal(fromYen(10000, 209.91, 2), 47.64);
  assert.equal(fromYen(10000, 0.1077, 0), 92851);
});

test("換算の表示はカンマ区切り", () => {
  assert.equal(formatAmount(5248, 0), "5,248");
  assert.equal(formatAmount(47.6, 2), "47.60");
  assert.equal(formatAmount(1234567.891, 2), "1,234,567.89");
});

// ---------- 為替の「今の位置」 ----------

function dailyHistory(values, lastDate = "2026-10-13") {
  return values.map((jpy, i) => ({ date: daysBefore(lastDate, values.length - 1 - i), jpy }));
}

test("為替の位置：1年で最も高い → 円安寄り（割高）", () => {
  const values = Array.from({ length: 100 }, (_, i) => 100 + i); // 最後が最高値
  assert.deepEqual(fxPosition(dailyHistory(values)), { min: 100, max: 199, pct: 99, level: "high", label: "円安寄り（割高）" });
});

test("為替の位置：1年で最も安い → 円高寄り（割安）", () => {
  const values = Array.from({ length: 100 }, (_, i) => 199 - i);
  assert.equal(fxPosition(dailyHistory(values)).level, "low");
  assert.equal(fxPosition(dailyHistory(values)).label, "円高寄り（割安）");
});

test("為替の位置：真ん中 → 平均的", () => {
  const values = Array.from({ length: 101 }, (_, i) => 100 + i);
  values.push(150);
  const p = fxPosition(dailyHistory(values));
  assert.equal(p.level, "mid");
  assert.equal(p.label, "平均的");
});

test("為替の位置：境目は20%と80%", () => {
  // 自分より安い日の割合（自分も含めた日数で割る）。20% 以下は割安、80% 以上は割高
  const base = Array.from({ length: 100 }, (_, i) => i + 1);
  assert.equal(fxPosition(dailyHistory([...base, 20.5])).pct, 20);
  assert.equal(fxPosition(dailyHistory([...base, 20.5])).level, "low");
  assert.equal(fxPosition(dailyHistory([...base, 81.5])).pct, 80);
  assert.equal(fxPosition(dailyHistory([...base, 81.5])).level, "high");
});

test("為替の位置：1年より前の値は使わない、60日分未満なら null", () => {
  const old = dailyHistory([999], "2025-01-01");
  const recent = dailyHistory(Array.from({ length: 70 }, (_, i) => 100 + i));
  assert.equal(fxPosition([...old, ...recent]).max, 169);
  assert.equal(fxPosition(dailyHistory(Array.from({ length: 59 }, (_, i) => i))), null);
  assert.equal(fxPosition([]), null);
});

test("比較表の要約に為替の位置が入る", () => {
  const history = dailyHistory(Array.from({ length: 100 }, (_, i) => 100 + i));
  const s = summarize({ exchange: ok({ currency: "GBP", history }) }, "2026-10-13");
  assert.equal(s.exchange.position.level, "high");
});

// ---------- 比較表の並べ替え ----------

function row(id, cells) {
  return { id, summary: cells };
}
const ROWS = [
  row("a", { exchange: { status: "ok", pct: 1.5 }, forecast: { status: "ok", tmax: 10 }, safety: { status: "ok", level: 2 } }),
  row("b", { exchange: { status: "ok", pct: -0.5 }, forecast: { status: "ok", tmax: 30 }, safety: { status: "ok", level: 0 } }),
  row("c", { exchange: { status: "unsupported" }, forecast: { status: "error", tmax: 20 }, safety: { status: "ok", level: 0 } }),
  row("d", { exchange: { status: "ok", pct: null }, forecast: { status: "missing" }, safety: { status: "missing" } }),
];
const ids = (rows) => rows.map((r) => r.id);

test("並べ替え：為替は円高（割安）が上、値の無いものは下", () => {
  assert.deepEqual(ids(sortRows(ROWS, "exchange", "natural")), ["b", "a", "c", "d"]);
  assert.deepEqual(ids(sortRows(ROWS, "exchange", "reverse")), ["a", "b", "c", "d"]);
});

test("並べ替え：天気は暖かい順、前回のデータ（error）も並べる", () => {
  assert.deepEqual(ids(sortRows(ROWS, "forecast", "natural")), ["b", "c", "a", "d"]);
});

test("並べ替え：危険レベルは低い順、同じなら元の順", () => {
  assert.deepEqual(ids(sortRows(ROWS, "safety", "natural")), ["b", "c", "a", "d"]);
});

test("並べ替え：気候・祝日", () => {
  const rows = [
    row("x", { climate: { status: "ok", temp: 5 }, holidays: { status: "ok", date: "2026-12-25" } }),
    row("y", { climate: { status: "ok", temp: 25 }, holidays: { status: "ok", date: "2026-11-09" } }),
    row("z", { climate: { status: "ok", temp: null }, holidays: { status: "ok", date: null } }),
  ];
  assert.deepEqual(ids(sortRows(rows, "climate", "natural")), ["y", "x", "z"]);
  assert.deepEqual(ids(sortRows(rows, "holidays", "natural")), ["y", "x", "z"]);
});

test("並べ替え：知らない列や指定なしは元の順のまま、元の配列は変えない", () => {
  assert.deepEqual(ids(sortRows(ROWS, "unknown", "natural")), ["a", "b", "c", "d"]);
  assert.deepEqual(ids(sortRows(ROWS, null, null)), ["a", "b", "c", "d"]);
  sortRows(ROWS, "exchange", "natural");
  assert.deepEqual(ids(ROWS), ["a", "b", "c", "d"]);
});

// ---------- タイル ----------

test("ベストシーズンの月の書き方", () => {
  assert.equal(formatMonths([6, 7, 8]), "6〜8月");
  assert.equal(formatMonths([2, 3, 7]), "2・3・7月");
  assert.equal(formatMonths([1, 2, 12]), "12〜2月"); // 年をまたぐ
  assert.equal(formatMonths([1, 11, 12]), "11〜1月");
  assert.equal(formatMonths([5]), "5月");
  assert.equal(formatMonths([4, 5]), "4・5月");
  assert.equal(formatMonths([]), "—");
  assert.equal(formatMonths(undefined), "—");
});

test("安全のタイル：お知らせの件数と変化", () => {
  const recent = new Date(Date.now() - 2 * 24 * 3600 * 1000).toISOString();
  const s = summarize({ safety: ok({ level: 0, notices: [{}, {}, {}], changed: true, changed_at: recent }) }, TODAY);
  assert.deepEqual(s.safety, { status: "ok", level: 0, notices: 3, changed: true });
  const old = summarize({ safety: ok({ level: 0, notices: [], changed: true, changed_at: "2026-01-01T06:00:00+09:00" }) }, TODAY);
  assert.equal(old.safety.changed, false); // 7日より前の変化は出さない
});
