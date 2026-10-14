// 実行方法：node --test tests/js/
const test = require("node:test");
const assert = require("node:assert/strict");
const { isStale, ageText, summarize, daysBefore, bestSeason, timeDiffText, parseHourly } = require("../../site/summary.js");

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
  assert.deepEqual(s.exchange, { status: "ok", pct: 5, word: "円安" });
});

test("為替：30日前の値が無ければ pct は null", () => {
  const history = [{ date: "2026-10-12", jpy: 210 }];
  const s = summarize({ exchange: ok({ currency: "GBP", history }) }, TODAY);
  assert.deepEqual(s.exchange, { status: "ok", pct: null, word: null });
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
  assert.deepEqual(s.safety, { status: "ok", level: 3 });
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
  assert.deepEqual(s.safety, { status: "error", level: 1 }); // 前回のデータで計算し、失敗の印を残す
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
