// 行き先ウォッチャーの画面。site/data/ の JSON を読んでカードを描く。
//
// 新しい情報を足すときは、RENDERERS に「情報の種類: 表示する関数」を足す。
// 表示する関数は (data, record, card) を受け取り、区切りの中身の要素を返す。

const DATA_DIR = "data";

const PROVIDER_NAMES = {
  frankfurter: "Frankfurter",
  "open-meteo": "Open-Meteo",
  "nager-date": "Nager.Date",
  mofa: "外務省 海外安全情報オープンデータ",
};

const WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"];

// ---------- 書式 ----------

function fmtDate(isoDate) {
  const [y, m, d] = isoDate.split("-").map(Number);
  const weekday = WEEKDAYS[new Date(y, m - 1, d).getDay()];
  return `${m}/${d}（${weekday}）`;
}

function fmtDateTime(iso) {
  // 保存は日本時間なので、文字列から直接読み取る（閲覧者の時間帯に左右されない）
  const match = typeof iso === "string" && iso.match(/^\d{4}-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!match) return "—";
  const [, m, d, hh, mm] = match;
  return `${Number(m)}/${Number(d)} ${Number(hh)}:${mm}`;
}

// 変化の検出から CHANGED_DAYS 日以内か（取得が失敗し続けても、古い「変化あり」を出し続けない）
const CHANGED_DAYS = 7;
function isRecentChange(changedAt) {
  const t = Date.parse(changedAt);
  return Number.isFinite(t) && Date.now() - t <= CHANGED_DAYS * 24 * 60 * 60 * 1000;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// ---------- データの読み込み ----------

async function loadJson(path) {
  const response = await fetch(`${path}?t=${Date.now()}`);
  if (!response.ok) return null;
  return response.json();
}

// ---------- 区切り（情報1つ分）の共通部分 ----------

function renderSection(record, source, card) {
  const section = el("section", "section");
  const head = el("div", "section-head");
  head.append(el("h3", null, source.label));
  if (record && record.updated_at) {
    head.append(el("span", "updated", `最終更新：${fmtDateTime(record.updated_at)}`));
  }
  section.append(head);

  if (!record) {
    section.append(el("p", "note", "データがまだありません"));
    return section;
  }
  if (record.status === "unsupported") {
    section.append(el("p", "note", "この国は対象外です（データ元が未対応）"));
    return section;
  }
  if (record.status === "error") {
    const when = record.updated_at ? `（${fmtDateTime(record.updated_at)} 時点のデータを表示中）` : "";
    section.append(el("p", "warning", `⚠ 取得に失敗しました${when}`));
  }
  if (record.data === null || record.data === undefined) {
    section.append(el("p", "note", "データがまだありません"));
  } else {
    const renderer = RENDERERS[source.name];
    if (renderer) {
      try {
        section.append(renderer(record.data, record, card));
      } catch (e) {
        console.error(source.name, e);
        section.append(el("p", "note", "表示中に問題が起きました"));
      }
    } else {
      section.append(el("p", "note", "この情報の表示はまだ用意されていません"));
    }
  }
  if (record.provider) {
    const name = PROVIDER_NAMES[record.provider] || record.provider;
    section.append(el("p", "provider", `出典：${name}`));
  }
  return section;
}

// ---------- 為替 ----------

function changeText(label, now, before) {
  const span = el("span");
  if (before === undefined) {
    span.className = "flat";
    span.textContent = `${label}：—`;
    return span;
  }
  // 表示する桁で丸めてから向きを決める（-0.00「円高」のような表示を防ぐ）
  const digits = yenDigits(now);
  const scale = 10 ** digits;
  const diff = Math.round((now - before) * scale) / scale;
  const pct = (diff / before) * 100;
  const sign = diff > 0 ? "+" : diff < 0 ? "−" : "±";
  const word = diff > 0 ? "円安" : diff < 0 ? "円高" : "変化なし";
  span.className = diff > 0 ? "up" : diff < 0 ? "down" : "flat";
  span.textContent = `${label}：${sign}${Math.abs(diff).toFixed(digits)}円（${sign}${Math.abs(pct).toFixed(2)}%・${word}）`;
  return span;
}

// 1外貨が10円未満の通貨（タイバーツなど）は小数3桁まで出す
function yenDigits(value) {
  return value < 10 ? 3 : 2;
}

function renderExchange(data) {
  const wrap = el("div");
  const history = data.history;
  if (history.length === 0) {
    wrap.append(el("p", "note", "データがまだありません"));
    return wrap;
  }
  const latest = history[history.length - 1];
  const previous = history.length > 1 ? history[history.length - 2] : undefined;
  const target30 = daysBefore(latest.date, 30);
  const ago30 = [...history].reverse().find((h) => h.date <= target30);

  wrap.append(el("p", "fx-now", `1 ${data.currency} = ${latest.jpy.toFixed(yenDigits(latest.jpy))} 円`));
  wrap.append(el("p", "note", `${fmtDate(latest.date)} のレート`));
  const changes = el("div", "fx-changes");
  changes.append(changeText("前日比", latest.jpy, previous && previous.jpy));
  changes.append(changeText("30日前比", latest.jpy, ago30 && ago30.jpy));
  wrap.append(changes);

  const ranges = [
    { label: "30日", days: 30 },
    { label: "90日", days: 90 },
    { label: "1年", days: 365 },
  ];
  const buttons = el("div", "range-buttons");
  const box = el("div", "chart-box");
  const canvas = el("canvas");
  canvas.setAttribute("aria-label", `${data.currency} の円レートの推移`);
  box.append(canvas);
  wrap.append(buttons, box);

  let chart = null;
  function draw(days) {
    const from = daysBefore(latest.date, days);
    const points = history.filter((h) => h.date >= from);
    if (chart) chart.destroy();
    if (!window.Chart) {
      box.replaceChildren(el("p", "note", "グラフを読み込めませんでした"));
      return;
    }
    const color = cssVar("--accent");
    chart = new Chart(canvas, {
      type: "line",
      data: {
        labels: points.map((h) => h.date),
        datasets: [{ data: points.map((h) => h.jpy), borderColor: color, borderWidth: 2, pointRadius: 0, tension: 0.2 }],
      },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { title: (items) => fmtDate(items[0].label), label: (item) => `${item.parsed.y.toFixed(2)} 円` } },
        },
        interaction: { mode: "index", intersect: false },
        scales: {
          x: { ticks: { color: cssVar("--muted"), maxTicksLimit: 5, callback: function (v) { return fmtDate(this.getLabelForValue(v)).replace(/（.）/, ""); } }, grid: { display: false } },
          y: { ticks: { color: cssVar("--muted") }, grid: { color: cssVar("--line") } },
        },
      },
    });
  }

  for (const range of ranges) {
    const button = el("button", null, range.label);
    button.type = "button";
    button.setAttribute("aria-pressed", String(range.days === 90));
    button.addEventListener("click", () => {
      for (const b of buttons.children) b.setAttribute("aria-pressed", String(b === button));
      draw(range.days);
    });
    buttons.append(button);
  }
  // Chart.js は defer で読み込むので、描画は要素が画面に入った後に行う
  requestAnimationFrame(() => draw(90));
  wrap.append(renderConverter(data.currency, latest));
  return wrap;
}

// ---------- 円換算の計算機 ----------

function renderConverter(currency, latest) {
  const box = el("div", "converter");
  box.append(el("p", "converter-head", `円換算（${fmtDate(latest.date)} のレートで計算）`));
  const digits = currencyDigits(currency);
  const row = el("div", "converter-row");

  function field(unit, label) {
    const wrap = el("label", "converter-field");
    const input = el("input");
    input.type = "text";
    input.inputMode = "decimal";
    input.autocomplete = "off";
    input.placeholder = "0";
    input.setAttribute("aria-label", label);
    wrap.append(input, el("span", "converter-unit", unit));
    return { wrap, input };
  }
  const foreign = field(currency, `${currency} の金額`);
  const yen = field("円", "円の金額");
  row.append(foreign.wrap, el("span", "converter-arrow", "⇄"), yen.wrap);

  // 入力した側を元に、もう片方を書き換える
  foreign.input.addEventListener("input", () => {
    const amount = parseAmount(foreign.input.value);
    yen.input.value = amount === null ? "" : formatAmount(toYen(amount, latest.jpy), 0);
  });
  yen.input.addEventListener("input", () => {
    const amount = parseAmount(yen.input.value);
    foreign.input.value = amount === null ? "" : formatAmount(fromYen(amount, latest.jpy, digits), digits);
  });

  box.append(row, el("p", "note", "※ 両替やカードの手数料は含みません"));
  return box;
}

// ---------- 天気予報 ----------

// WMO 天気コード → [絵文字, 短い名前]
const WEATHER_CODES = [
  [[0], "☀️", "快晴"],
  [[1], "🌤️", "晴れ"],
  [[2], "⛅", "晴れ時々曇り"],
  [[3], "☁️", "曇り"],
  [[45, 48], "🌫️", "霧"],
  [[51, 53, 55, 56, 57], "🌦️", "霧雨"],
  [[61, 63, 65, 66, 67, 80, 81, 82], "🌧️", "雨"],
  [[71, 73, 75, 77, 85, 86], "❄️", "雪"],
  [[95, 96, 99], "⛈️", "雷雨"],
];

function weatherOf(code) {
  const found = WEATHER_CODES.find(([codes]) => codes.includes(code));
  return found ? { icon: found[1], name: found[2] } : { icon: "—", name: "—" };
}

function fmtNumber(value, suffix, digits = 0) {
  return value === null || value === undefined ? "—" : `${value.toFixed(digits)}${suffix}`;
}

function hm(hhmm) {
  return `${Number(hhmm.slice(0, 2))}:${hhmm.slice(3)}`;
}

function sunText(day) {
  if (day.daylight_h === 0) return "🌑 極夜";
  if (day.daylight_h >= 24) return "☀ 白夜";
  if (day.sunrise && day.sunset) return `☀ ${hm(day.sunrise)}–${day.sunset_next_day ? "翌" : ""}${hm(day.sunset)}`;
  return null;
}

function renderForecast(data) {
  const wrap = el("div");
  const today = data.days.find((d) => d.date >= todayLocal()) || data.days[0];
  if (today && typeof today.daylight_h === "number") {
    const polar = today.daylight_h === 0 ? "（極夜：日が昇りません）" : today.daylight_h >= 24 ? "（白夜：日が沈みません）" : "";
    wrap.append(el("p", "note", `今日の昼の長さ：${today.daylight_h.toFixed(1)}時間${polar}`));
  }
  const row = el("div", "forecast-row");
  for (const day of data.days) {
    const weather = weatherOf(day.code);
    const cell = el("div", "forecast-day");
    cell.append(
      el("div", "fc-date", fmtDate(day.date)),
      el("div", "fc-icon", weather.icon),
      el("div", "fc-name", weather.name),
    );
    const temps = el("div", "fc-temp");
    temps.append(el("span", "up", fmtNumber(day.tmax, "°")), " / ", el("span", "down", fmtNumber(day.tmin, "°")));
    cell.append(temps, el("div", "fc-prob", `☂ ${fmtNumber(day.precip_prob, "%")}`));
    const sun = sunText(day);
    if (sun) cell.append(el("div", "fc-sun", sun));
    row.append(cell);
  }
  wrap.append(row);
  return wrap;
}

// ---------- 月ごとの気候 ----------

function renderClimate(data) {
  const wrap = el("div");
  const scroller = el("div", "table-scroll");
  const table = el("table", "climate");
  const thisMonth = new Date().getMonth() + 1;
  const best = bestSeason(data.months);
  const rows = [
    ["月", (m) => `${best.includes(m.month) ? "★" : ""}${m.month}月`],
    ["平均気温", (m) => fmtNumber(m.temp, "°", 1)],
    ["降水量", (m) => fmtNumber(m.precip, "mm")],
  ];
  if (data.months.some((m) => typeof m.daylight === "number")) {
    rows.push(["昼の長さ", (m) => fmtNumber(m.daylight, "h", 1)]);
  }
  for (const [label, value] of rows) {
    const tr = el("tr");
    tr.append(el("th", null, label));
    for (const m of data.months) {
      const td = el(label === "月" ? "th" : "td", m.month === thisMonth ? "current" : null, value(m));
      tr.append(td);
    }
    table.append(tr);
  }
  scroller.append(table);
  wrap.append(scroller);
  if (best.length) {
    wrap.append(el("p", "best-season", `★ 過ごしやすい時期の目安：${best.join("・")}月（気温と雨から計算した目安です）`));
  }
  wrap.append(el("p", "note", data.period));
  // 今月が見えるように横スクロールしておく（左端の見出し列の分だけ手前にする）
  requestAnimationFrame(() => {
    const current = table.querySelector("th.current");
    const header = table.querySelector("th");
    if (current) scroller.scrollLeft = current.offsetLeft - header.offsetWidth - 40;
  });
  return wrap;
}

// ---------- 祝日 ----------

function renderHolidays(data) {
  if (data.holidays.length === 0) return el("p", "note", "今後6か月の祝日はありません");
  const list = el("ul", "holiday-list");
  for (const h of data.holidays) {
    const li = el("li");
    li.append(el("span", "hol-date", fmtDate(h.date)));
    const names = el("span", "hol-name", h.local_name);
    if (h.name && h.name !== h.local_name) names.append(el("span", "hol-en", `（${h.name}）`));
    li.append(names);
    list.append(li);
  }
  return list;
}

// ---------- 海外安全情報 ----------

const SAFETY_LEVELS = {
  0: "情報なし",
  1: "レベル1：十分注意してください",
  2: "レベル2：不要不急の渡航は止めてください",
  3: "レベル3：渡航は止めてください（渡航中止勧告）",
  4: "レベル4：退避してください。渡航は止めてください（退避勧告）",
};

function levelBadge(prefix, level, small) {
  const text = level === 0 ? `${prefix}：${SAFETY_LEVELS[0]}` : `${prefix} ${SAFETY_LEVELS[level]}`;
  return el("p", `badge level-${level}${small ? " small" : ""}`, text);
}

function renderSafety(data, record, card) {
  const wrap = el("div");
  if (data.changed && isRecentChange(data.changed_at)) {
    card.classList.add("alert");
    const parts = [];
    if (data.previous_level !== data.level) parts.push(`危険レベル ${data.previous_level ?? "?"}→${data.level}`);
    if (data.previous_infection_level !== data.infection_level) {
      parts.push(`感染症危険レベル ${data.previous_infection_level ?? "?"}→${data.infection_level}`);
    }
    wrap.append(el("p", "change-alert", `⚠ 変化あり：${parts.join("、")}（${fmtDateTime(data.changed_at).split(" ")[0]} 検出）`));
  }
  wrap.append(levelBadge("危険情報", data.level, false));
  wrap.append(levelBadge("感染症危険情報", data.infection_level, true));
  if (data.title) wrap.append(el("p", "safety-title", data.title));
  if (Array.isArray(data.notices)) {
    wrap.append(el("h4", "sub-head", "最近のお知らせ（30日以内）"));
    if (data.notices.length === 0) {
      wrap.append(el("p", "note", "30日以内のお知らせはありません"));
    } else {
      const list = el("ul", "notice-list");
      for (const n of data.notices) {
        const li = el("li");
        li.append(el("span", "hol-date", fmtDate(n.date).replace(/（.）/, "")));
        if (n.url) {
          const a = el("a", null, n.title);
          a.href = n.url;
          a.target = "_blank";
          a.rel = "noopener";
          a.title = n.kind;
          li.append(a);
        } else {
          li.append(el("span", null, n.title));
        }
        list.append(li);
      }
      wrap.append(list);
    }
  }
  if (Array.isArray(data.links) && data.links.length) {
    const links = el("p", "safety-links");
    for (const l of data.links) {
      const a = el("a", null, `${l.label} ↗`);
      a.href = l.url;
      a.target = "_blank";
      a.rel = "noopener";
      links.append(a);
    }
    wrap.append(links);
  }
  if (data.url) {
    const link = el("a", "safety-link", "外務省 海外安全ホームページで詳しく見る ↗");
    link.href = data.url;
    link.target = "_blank";
    link.rel = "noopener";
    wrap.append(link);
  }
  if (data.level > 0) {
    wrap.append(el("p", "note", "※国内の一部地域だけに出ている場合も、いちばん高いレベルを表示しています"));
  }
  return wrap;
}

// ---------- 情報の種類と表示関数の対応 ----------

const RENDERERS = {
  exchange: renderExchange,
  forecast: renderForecast,
  climate: renderClimate,
  holidays: renderHolidays,
  safety: renderSafety,
};

// ---------- 全体 ----------

// ---------- 現地時刻と時差 ----------

function startLocalClock(target, timeZone) {
  function tick() {
    const t = timeDiffText(timeZone, Date.now());
    target.textContent = t ? `現地 ${t.local}（${t.diff}）` : "";
  }
  tick();
  // 分が切り替わる瞬間にそろえてから、1分ごとに更新する
  setTimeout(() => {
    tick();
    setInterval(tick, 60 * 1000);
  }, 60 * 1000 - (Date.now() % (60 * 1000)) + 50);
}

// ---------- これから12時間の天気（画面を開いたときに直接取得） ----------

const HOURLY_API = "https://api.open-meteo.com/v1/forecast";
const HOURLY_TIMEOUT_MS = 10 * 1000;

function renderHourlySection(dest) {
  // 緯度経度の無い古いデータでは、この欄そのものを出さない
  if (typeof dest.lat !== "number" || typeof dest.lon !== "number") return null;
  const section = el("section", "section");
  const head = el("div", "section-head");
  head.append(el("h3", null, "これから12時間の天気"));
  const when = el("span", "updated", "取得中…");
  head.append(when);
  const body = el("div");
  body.append(el("p", "note", "読み込み中…"));
  section.append(head, body, el("p", "provider", "出典：Open-Meteo（この画面を開いたときに取得）"));

  const failed = () => {
    when.textContent = "";
    body.replaceChildren(el("p", "note", "今は取得できません（毎朝の予報は上に表示しています）"));
  };
  const params = new URLSearchParams({
    latitude: dest.lat, longitude: dest.lon,
    hourly: "temperature_2m,precipitation_probability,weather_code,is_day",
    forecast_hours: 12, timezone: "auto",
  });
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HOURLY_TIMEOUT_MS);
  fetch(`${HOURLY_API}?${params}`, { signal: controller.signal })
    .then((r) => (r.ok ? r.json() : null))
    .then((raw) => {
      const hours = parseHourly(raw);
      if (!hours || hours.length === 0) return failed();
      const row = el("div", "forecast-row");
      for (const h of hours) {
        const weather = weatherOf(h.code);
        if (h.night && (h.code === 0 || h.code === 1)) weather.icon = "🌙"; // 夜の晴れは月にする
        const cell = el("div", "forecast-day hourly");
        cell.append(
          el("div", "fc-date", h.time),
          el("div", "fc-icon", weather.icon),
          el("div", "fc-temp", fmtNumber(h.temp, "°")),
          el("div", "fc-prob", `☂ ${fmtNumber(h.prob, "%")}`),
        );
        row.append(cell);
      }
      const now = new Date();
      when.textContent = `取得：${now.getHours()}:${String(now.getMinutes()).padStart(2, "0")}`;
      body.replaceChildren(row);
    })
    .catch(failed)
    .finally(() => clearTimeout(timer));
  return section;
}

// ---------- 古いデータの警告 ----------

const ACTIONS_URL = "https://github.com/kaitoHogeHoge/destination-watcher/actions";

function renderStaleBanner(generatedAt) {
  const banner = el("div", "stale-banner");
  banner.setAttribute("role", "alert");
  const when = fmtDateTime(generatedAt);
  const age = ageText(generatedAt, Date.now());
  banner.append(
    el("strong", null, "⚠ データが古くなっています"),
    el("span", null, `（最終実行：${when}${age ? `・${age}` : ""}）。毎日の自動更新が止まっている可能性があります。`),
  );
  const link = el("a", null, "GitHub の実行結果を見る ↗");
  link.href = ACTIONS_URL;
  link.target = "_blank";
  link.rel = "noopener";
  banner.append(link);
  return banner;
}

// ---------- 比較の一覧 ----------

function todayLocal() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// 1マス分の表示。status に応じて「—」「対象外」「⚠」を付ける
function compareCell(cell, render) {
  const td = el("td");
  if (cell.status === "unsupported") {
    td.append(el("span", "flat", "対象外"));
  } else if (cell.status === "missing" || cell.status === "broken") {
    td.append(el("span", "flat", "—"));
  } else {
    if (cell.status === "error") {
      const mark = el("span", "cell-warn", "⚠ ");
      mark.title = "今回の取得に失敗したため、前回のデータです";
      td.append(mark);
    }
    td.append(render(cell));
  }
  return td;
}

const COMPARE_COLUMNS = [
  {
    label: "為替（30日前比）",
    name: "exchange",
    render: (c) => {
      if (c.pct === null) return el("span", "flat", "—");
      const cls = c.pct > 0 ? "up" : c.pct < 0 ? "down" : "flat";
      const sign = c.pct > 0 ? "+" : c.pct < 0 ? "−" : "±";
      return el("span", cls, `${sign}${Math.abs(c.pct).toFixed(2)}%・${c.word}`);
    },
  },
  {
    label: "来週の天気（7日間）",
    name: "forecast",
    render: (c) => {
      const span = el("span");
      span.append(el("span", "up", fmtNumber(c.tmax, "°", 1)), " / ", el("span", "down", fmtNumber(c.tmin, "°", 1)));
      span.append(`・☂ ${c.rainyDays}日`);
      return span;
    },
  },
  {
    label: "今月の気候",
    name: "climate",
    render: (c) => {
      const span = el("span", null, `${fmtNumber(c.temp, "°", 1)}・${fmtNumber(c.precip, "mm")}`);
      if (c.best && c.best.length) span.append(el("span", "flat", `（目安：${c.best.join("・")}月）`));
      return span;
    },
  },
  {
    label: "次の祝日",
    name: "holidays",
    render: (c) => (c.date ? el("span", null, `${fmtDate(c.date)} ${c.name}`) : el("span", "flat", "6か月内なし")),
  },
  {
    label: "危険レベル",
    name: "safety",
    render: (c) => el("span", `badge small level-${c.level}`, c.level === 0 ? "なし" : `レベル${c.level}`),
  },
];

function renderCompare(rows) {
  const section = el("section", "compare");
  section.append(el("h2", null, "比較"));
  const scroller = el("div", "table-scroll");
  const table = el("table", "compare-table");
  const head = el("tr");
  head.append(el("th", null, "行き先"));
  for (const col of COMPARE_COLUMNS) head.append(el("th", null, col.label));
  table.append(head);

  const today = todayLocal();
  for (const { dest, records } of rows) {
    const tr = el("tr");
    const nameCell = el("th");
    const link = el("a", null, dest.name);
    link.href = `#dest-${dest.id}`;
    nameCell.append(link);
    tr.append(nameCell);
    const summary = summarize(records, today);
    for (const col of COMPARE_COLUMNS) {
      tr.append(compareCell(summary[col.name] || { status: "missing" }, col.render));
    }
    table.append(tr);
  }
  scroller.append(table);
  section.append(scroller);
  section.append(el("p", "note", "☂ は降水確率50%以上の日数。為替は「1外貨＝何円」が30日前より上がっていれば円安です。"));
  return section;
}

// ---------- 全体 ----------

async function main() {
  const generated = document.getElementById("generated");
  const cards = document.getElementById("cards");
  const index = await loadJson(`${DATA_DIR}/index.json`).catch(() => null);
  if (!index) {
    generated.textContent = "データを読み込めませんでした";
    return;
  }
  generated.textContent = `最終実行：${fmtDateTime(index.generated_at)}`;
  if (isStale(index.generated_at, Date.now())) {
    document.querySelector(".page-header").after(renderStaleBanner(index.generated_at));
  }

  // 先に全行き先のデータを読み込む（比較の一覧とカードの両方で使う）
  const rows = await Promise.all(
    index.destinations.map(async (dest) => {
      const list = await Promise.all(
        index.sources.map((s) => loadJson(`${DATA_DIR}/${dest.id}/${s.name}.json`).catch(() => null)),
      );
      const records = {};
      index.sources.forEach((s, i) => (records[s.name] = list[i]));
      return { dest, records };
    }),
  );

  try {
    cards.before(renderCompare(rows));
  } catch (e) {
    console.error("compare", e);
  }

  for (const { dest, records } of rows) {
    const card = el("article", "card");
    card.id = `dest-${dest.id}`;
    const title = el("div", "card-title");
    const clock = el("span", "local-clock");
    title.append(el("h2", null, dest.name), clock);
    card.append(title, el("p", "country", dest.country));
    cards.append(card);
    const timeZone = records.forecast && records.forecast.data && records.forecast.data.timezone;
    if (timeZone) startLocalClock(clock, timeZone);
    for (const source of index.sources) {
      try {
        card.append(renderSection(records[source.name], source, card));
        if (source.name === "forecast") {
          const hourly = renderHourlySection(dest);
          if (hourly) card.append(hourly);
        }
      } catch (e) {
        // 1つの区切りが壊れていても、他の区切り・他の行き先は表示する
        console.error(dest.id, source.name, e);
        const section = el("section", "section");
        section.append(el("h3", null, source.label), el("p", "note", "表示中に問題が起きました"));
        card.append(section);
      }
    }
  }
}

main();
