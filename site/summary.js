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

// ---------- ベストシーズンの目安 ----------
// 点数 = |平均気温 − 22| + 降水量 ÷ 20（低いほど過ごしやすい）。その都市の中で上位3か月

const COMFORT_TEMP = 22;
const RAIN_PER_DEGREE = 20;
const BEST_MONTHS = 3;

function bestSeason(months) {
  if (!Array.isArray(months)) return [];
  const scored = months
    .filter((m) => m && typeof m.temp === "number" && typeof m.precip === "number")
    .map((m) => ({ month: m.month, score: Math.abs(m.temp - COMFORT_TEMP) + m.precip / RAIN_PER_DEGREE }));
  scored.sort((a, b) => a.score - b.score || a.month - b.month);
  return scored.slice(0, BEST_MONTHS).map((m) => m.month).sort((a, b) => a - b);
}

// 月の並びを短く書く。3か月以上続いていれば「6〜8月」（年またぎは「12〜2月」）、それ以外は「2・3・7月」
function formatMonths(months) {
  if (!Array.isArray(months) || months.length === 0) return "—";
  const sorted = [...new Set(months)].sort((a, b) => a - b);
  if (sorted.length >= 3) {
    for (const start of sorted) {
      const run = sorted.map((_, i) => ((start - 1 + i) % 12) + 1);
      if (run.every((m) => sorted.includes(m))) return `${start}〜${run[run.length - 1]}月`;
    }
  }
  return `${sorted.join("・")}月`;
}

// ---------- 現地時刻と時差 ----------

// その時間帯での「壁の時計の時刻」を UTC の数値として表したもの（時差の計算用）
function wallClockMs(timeZone, nowMs) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  }).formatToParts(new Date(nowMs));
  const get = (type) => Number(parts.find((p) => p.type === type).value);
  return Date.UTC(get("year"), get("month") - 1, get("day"), get("hour"), get("minute"));
}

function timeDiffText(timeZone, nowMs) {
  if (typeof timeZone !== "string") return null;
  let local, diffMinutes;
  try {
    const here = wallClockMs(timeZone, nowMs);
    diffMinutes = Math.round((here - wallClockMs("Asia/Tokyo", nowMs)) / 60000);
    const d = new Date(here);
    local = `${d.getUTCHours()}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
  } catch (e) {
    return null; // 読めない時間帯
  }
  if (diffMinutes === 0) return { local, diff: "日本と同じ時刻" };
  const sign = diffMinutes > 0 ? "+" : "−";
  const abs = Math.abs(diffMinutes);
  const hours = Math.floor(abs / 60);
  const minutes = abs % 60;
  return { local, diff: `日本より${sign}${hours}時間${minutes ? `${minutes}分` : ""}` };
}

// ---------- 1時間ごとの天気（Open-Meteo の応答を読む） ----------

function parseHourly(raw) {
  const h = raw && raw.hourly;
  if (!h || !Array.isArray(h.time)) return null;
  const at = (key, i) => (Array.isArray(h[key]) && typeof h[key][i] === "number" ? h[key][i] : null);
  return h.time.map((t, i) => ({
    time: typeof t === "string" ? `${Number(t.slice(11, 13))}:${t.slice(14, 16)}` : "—",
    temp: at("temperature_2m", i),
    prob: at("precipitation_probability", i),
    code: at("weather_code", i),
    night: at("is_day", i) === 0,
  }));
}

// ---------- 円換算 ----------

// 入力欄の文字を数値にする。全角数字・カンマ・空白を受け付ける。読めなければ null
function parseAmount(text) {
  if (typeof text !== "string") return null;
  const normalized = text
    .replace(/[０-９]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0))
    .replace(/[．。]/g, ".")
    .replace(/[,，\s]/g, "");
  if (!/^\d+(\.\d+)?$/.test(normalized)) return null;
  return Number(normalized);
}

// その通貨で普段使う小数の桁（ポンドは2、ウォンは0）
function currencyDigits(currency) {
  try {
    return new Intl.NumberFormat("ja-JP", { style: "currency", currency }).resolvedOptions().maximumFractionDigits;
  } catch (e) {
    return 2;
  }
}

function toYen(amount, rate) {
  return Math.round(amount * rate);
}

function fromYen(yen, rate, digits) {
  return round(yen / rate, digits);
}

function formatAmount(value, digits) {
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

// ---------- 為替の「今の位置」（過去1年の中で高いか安いか） ----------

const FX_WINDOW_DAYS = 365;
const FX_MIN_POINTS = 60;
const FX_LOW = 20;   // これ以下なら円高寄り（割安）
const FX_HIGH = 80;  // これ以上なら円安寄り（割高）

function fxPosition(history) {
  if (!Array.isArray(history) || history.length === 0) return null;
  const latest = history[history.length - 1];
  const from = daysBefore(latest.date, FX_WINDOW_DAYS);
  const values = history.filter((h) => h.date >= from && typeof h.jpy === "number").map((h) => h.jpy);
  if (values.length < FX_MIN_POINTS) return null;
  const below = values.filter((v) => v < latest.jpy).length;
  const pct = Math.round((below / values.length) * 100);
  const level = pct <= FX_LOW ? "low" : pct >= FX_HIGH ? "high" : "mid";
  const label = { low: "円高寄り（割安）", mid: "平均的", high: "円安寄り（割高）" }[level];
  return { min: Math.min(...values), max: Math.max(...values), pct, level, label };
}

// ---------- 比較表の並べ替え ----------
// natural：見出しを最初に押したときの順。値の無い行はいつも一番下

const SORT_KEYS = {
  exchange: { value: (c) => c.pct, ascending: true },     // 円高（割安）が上
  forecast: { value: (c) => c.tmax, ascending: false },   // 暖かい順
  climate: { value: (c) => c.temp, ascending: false },    // 暖かい順
  holidays: { value: (c) => c.date, ascending: true },    // 近い順
  safety: { value: (c) => c.level, ascending: true },     // 低い順
};

function sortRows(rows, column, direction) {
  const key = SORT_KEYS[column];
  if (!key || !direction) return [...rows];
  const ascending = direction === "natural" ? key.ascending : !key.ascending;
  const valueOf = (r) => {
    const cell = r.summary && r.summary[column];
    if (!cell || (cell.status !== "ok" && cell.status !== "error")) return null;
    const v = key.value(cell);
    return v === undefined ? null : v;
  };
  return rows
    .map((r, i) => ({ r, i, v: valueOf(r) }))
    .sort((a, b) => {
      if (a.v === null || b.v === null) return (a.v === null) - (b.v === null) || a.i - b.i;
      const cmp = a.v < b.v ? -1 : a.v > b.v ? 1 : 0;
      return (ascending ? cmp : -cmp) || a.i - b.i;
    })
    .map((x) => x.r);
}

// ---------- 情報ごとの要約（data → 表の1マス分） ----------

const SUMMARIZERS = {
  exchange(data) {
    const history = data.history;
    const latest = history[history.length - 1];
    const target = daysBefore(latest.date, 30);
    const before = [...history].reverse().find((h) => h.date <= target);
    const position = fxPosition(history);
    if (!before) return { pct: null, word: null, position };
    const pct = round(((latest.jpy - before.jpy) / before.jpy) * 100, 2);
    return { pct, word: pct > 0 ? "円安" : pct < 0 ? "円高" : "変化なし", position };
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
    return { temp: m ? m.temp : null, precip: m ? m.precip : null, best: bestSeason(data.months) };
  },

  holidays(data, today) {
    const next = data.holidays.find((h) => h.date >= today);
    return next ? { date: next.date, name: next.local_name } : { date: null, name: null };
  },

  safety(data) {
    const recent = Date.now() - Date.parse(data.changed_at) <= 7 * 24 * 60 * 60 * 1000;
    return {
      level: data.level,
      notices: Array.isArray(data.notices) ? data.notices.length : null,
      changed: Boolean(data.changed) && recent,
    };
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
  module.exports = {
    STALE_HOURS, isStale, ageText, summarize, daysBefore, bestSeason, timeDiffText, parseHourly,
    parseAmount, currencyDigits, toYen, fromYen, formatAmount, fxPosition, sortRows, formatMonths,
  };
}
