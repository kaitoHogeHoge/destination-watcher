// 比較の一覧と、古いデータの警告に使う計算。画面の描画はしない（テストできるように分けてある）。
//
// ブラウザでは <script> で読み込んで関数をそのまま使い、
// テストでは Node.js から require して使う。

const STALE_HOURS = 36;      // 最後の自動実行からこれ以上経ったら「古い」
const FORECAST_DAYS = 7;     // 「来週の天気」に使う日数
const RAINY_PROB = 50;       // 降水確率がこれ以上の日を「雨の日」と数える

function daysBefore(isoDate, days) {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d - days)).toISOString().slice(0, 10);
}

// 「2026-10-13T06:00:00+09:00」の形だけを読む。それ以外は NaN
function parseIso(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value)) return NaN;
  return Date.parse(value);
}

function isStale(generatedAt, nowMs) {
  const t = parseIso(generatedAt);
  return !Number.isFinite(t) || nowMs - t > STALE_HOURS * 60 * 60 * 1000;
}

function ageText(generatedAt, nowMs) {
  const t = parseIso(generatedAt);
  if (!Number.isFinite(t)) return "";
  const hours = Math.floor((nowMs - t) / (60 * 60 * 1000));
  return hours < 24 ? `${hours}時間前` : `${Math.floor(hours / 24)}日前`;
}

function round(value, digits) {
  const scale = 10 ** digits;
  return Math.round(value * scale) / scale;
}

function average(values) {
  const nums = values.filter((v) => typeof v === "number");
  return nums.length ? round(nums.reduce((a, b) => a + b, 0) / nums.length, 1) : null;
}

// ---------- 情報ごとの要約（data → 表の1マス分） ----------

const SUMMARIZERS = {
  exchange(data) {
    const history = data.history;
    const latest = history[history.length - 1];
    const target = daysBefore(latest.date, 30);
    const before = [...history].reverse().find((h) => h.date <= target);
    if (!before) return { pct: null, word: null };
    const pct = round(((latest.jpy - before.jpy) / before.jpy) * 100, 2);
    return { pct, word: pct > 0 ? "円安" : pct < 0 ? "円高" : "変化なし" };
  },

  forecast(data, today) {
    const days = data.days.filter((d) => d.date >= today).slice(0, FORECAST_DAYS);
    return {
      tmax: average(days.map((d) => d.tmax)),
      tmin: average(days.map((d) => d.tmin)),
      rainyDays: days.filter((d) => typeof d.precip_prob === "number" && d.precip_prob >= RAINY_PROB).length,
      days: days.length,
    };
  },

  climate(data, today) {
    const month = Number(today.slice(5, 7));
    const m = data.months.find((x) => x.month === month);
    return { temp: m ? m.temp : null, precip: m ? m.precip : null };
  },

  holidays(data, today) {
    const next = data.holidays.find((h) => h.date >= today);
    return next ? { date: next.date, name: next.local_name } : { date: null, name: null };
  },

  safety(data) {
    return { level: data.level };
  },
};

// records: { 情報の種類: 保存された record（無ければ null） }、today: "YYYY-MM-DD"
// 戻り値の各マスの status：ok / error（前回のデータで計算）/ unsupported / missing / broken
function summarize(records, today) {
  const result = {};
  for (const [name, fn] of Object.entries(SUMMARIZERS)) {
    const record = records[name];
    if (record && record.status === "unsupported") {
      result[name] = { status: "unsupported" };
    } else if (!record || record.data === null || record.data === undefined) {
      result[name] = { status: "missing" };
    } else {
      try {
        result[name] = { status: record.status === "error" ? "error" : "ok", ...fn(record.data, today) };
      } catch (e) {
        result[name] = { status: "broken" };
      }
    }
  }
  return result;
}

if (typeof module !== "undefined") {
  module.exports = { STALE_HOURS, isStale, ageText, summarize, daysBefore };
}
