// Dindo web app: hash router + views rendered from the API. No framework, no build step.
const state = {
  lang: "es", caseId: 1, config: null, cases: [], summary: null, day: null,
  calMonth: null, calSel: null, calMode: "month", txStart: null, expCat: null, expPeriod: "all", docType: null, showInfo: false,
};
try {
  state.lang = localStorage.getItem("dindo.lang") || "es";
  state.caseId = Number(localStorage.getItem("dindo.case")) || 1;
  state.member = Number(localStorage.getItem("dindo.member")) || null;
} catch (_) {}
if (!I18N[state.lang]) state.lang = "es";

// ---------- helpers ----------
const $ = (s, el = document) => el.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const t = (k, vars = {}) => (I18N[state.lang][k] ?? I18N.es[k] ?? k).replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? "");
const locale = () => ({ es: "es-BO", en: "en-GB", it: "it-IT" }[state.lang]);
const nf = (n, dec = 0) => Number(n || 0).toLocaleString("es-BO", { minimumFractionDigits: dec, maximumFractionDigits: dec });
const money = (n, dec = 0) => `${nf(n, dec)} Bs`;
const D = (iso) => new Date(iso + "T12:00:00");
const isoOf = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const addDays = (iso, n) => { const d = D(iso); d.setDate(d.getDate() + n); return isoOf(d); };
const fdate = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : "—");
const fdm = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : "");
const wd = (iso, style = "short") => D(iso).toLocaleDateString(locale(), { weekday: style });
const monthTitle = (ym) => { const s = D(ym + "-01").toLocaleDateString(locale(), { month: "long", year: "numeric" }); return s[0].toUpperCase() + s.slice(1); };
const daysBetween = (a, b) => Math.round((D(b) - D(a)) / 86400000);
let clockOffset = 0;  // the demo can pin the clock (DINDO_TIME on the server)
const clock = () => new Date(Date.now() + clockOffset);
const nowHM = () => clock().toTimeString().slice(0, 5);

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) {
    let msg = res.status;
    try { msg = (await res.json()).detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}
const send = (path, method, body) => api(path, { method, body: JSON.stringify(body || {}) });
const C = (p) => `/api/cases/${state.caseId}${p}`;

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 2200);
}

const ICON = {
  home: '<path d="M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3z"/>',
  calendar: '<rect x="3" y="4.5" width="18" height="16" rx="2"/><path d="M3 9.5h18M8 2.5v4M16 2.5v4"/>',
  pill: '<path d="M10.5 20.5 20.5 10.5a4.95 4.95 0 0 0-7-7L3.5 13.5a4.95 4.95 0 0 0 7 7z"/><path d="m8.5 8.5 7 7"/>',
  clipboard: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V2.8h6V4M9 10h6M9 14h6M9 18h3"/>',
  tag: '<path d="M3 12V4.5A1.5 1.5 0 0 1 4.5 3H12l9 9-9 9z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
  steth: '<path d="M6 3v6a5 5 0 0 0 10 0V3"/><path d="M11 14v2a5 5 0 0 0 10 0v-2"/><circle cx="21" cy="12" r="2"/>',
  flask: '<path d="M9 3h6M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2h12.4a1.5 1.5 0 0 0 1.3-2L14 9V3"/><path d="M7 15h10"/>',
  money: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M12 7v10M14.5 9.2c0-1-1.1-1.7-2.5-1.7s-2.5.7-2.5 1.7c0 2.4 5 1.3 5 3.8 0 1-1.1 1.8-2.5 1.8s-2.5-.8-2.5-1.8"/>',
  shield: '<path d="M12 3 4.5 6v6c0 4.4 3.2 7.8 7.5 9 4.3-1.2 7.5-4.6 7.5-9V6z"/><path d="m9 12 2 2 4-4"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.4 3.3-5.5 6.5-5.5s5.9 2.1 6.5 5.5M16 4.8a3.5 3.5 0 0 1 0 6.4M18.5 14.8c1.7.8 2.8 2.6 3 5.2"/>',
  scale: '<path d="M12 3v18M7 21h10M5 7h14M5 7l-3 7a3 3 0 0 0 6 0zM19 7l-3 7a3 3 0 0 0 6 0z"/>',
  alert: '<path d="M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.2 9a3 3 0 0 1 5.6 1c0 2-2.8 2.5-2.8 4M12 17h.01"/>',
  cpu: '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  phone: '<path d="M21 16.5v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 1.1 3.7 2 2 0 0 1 3.1 1.5h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L7 9.4a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.8 2.2z"/>',
  camera: '<path d="M4 7h3l2-3h6l2 3h3a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z"/><circle cx="12" cy="13" r="3.8"/>',
  left: '<path d="m15 18-6-6 6-6"/>', right: '<path d="m9 18 6-6-6-6"/>', down: '<path d="m6 9 6 6 6-6"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>', speaker: '<path d="M11 5 6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>', bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/>', chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>', report: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h2M9 17h6M13 13h2"/>', check: '<path d="m5 12 5 5 9-10"/>', x: '<path d="M6 6l12 12M18 6 6 18"/>',
  share: '<circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="m8.2 10.8 7.6-4.4M8.2 13.2l7.6 4.4"/>',
};
const ic = (n) => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICON[n] || ""}</svg>`;

const KIND = {
  appointment: ["k_appointment", "--k-doctor_fees"], study: ["k_study", "--k-lab_imaging"], session: ["k_session", "--k-therapy"],
  hearing: ["k_hearing", "--k-legal"], accident: ["k_hosp", "--k-hospitalization"], admission: ["k_hosp", "--k-hospitalization"],
  surgery: ["k_hosp", "--k-hospitalization"], other: ["k_other", "--k-other"],
};
const kindColor = (k) => `var(${(KIND[k] || KIND.other)[1]})`;
const catColor = (c) => `var(--k-${c || "other"}, var(--k-other))`;
const sevTag = (s) => `<span class="tag ${s === "critical" ? "crit" : s === "warning" ? "warn" : ""}">${t(s === "critical" ? "critical" : s === "warning" ? "review" : "info")}</span>`;
// Short, scannable titles (the full sentence stays in the Alerts screen).
function findingTitle(f) {
  const d = (f.detail || "").toLowerCase(), doc = (f.title || "").toLowerCase();
  const what = /tac|tomograf/.test(doc + d) ? "o_ct" : /rx|radiograf|rayos/.test(doc + d) ? "o_xray" : /doppler|eco/.test(doc + d) ? "o_echo" : "o_order";
  if (f.kind === "body_side") return t("ft_side", { o: t(what) });
  if (f.kind === "date") return t(/anterior|antes|before/.test(d) ? "ft_before" : "ft_date");
  if (f.kind === "arithmetic") return t("ft_math");
  if (f.kind === "patient") return t("ft_patient");
  if (f.kind === "billing") return t(/particular|sin seguro/.test(d) ? "ft_private" : /recibo|fiscal|receipt/.test(d) ? "ft_receipt" : "ft_billing");
  const s = (f.detail || "").split(/[.;:]/)[0];
  return s.length > 60 ? s.slice(0, 58) + "…" : s;
}
const topic = (s, n = 46) => { s = String(s || ""); return s.length > n ? s.slice(0, n).replace(/\s+\S*$/, "") + "…" : s; };
const CLAIM_ST = ["to_submit", "submitted", "approved", "paid", "rejected"];
const claimSel = (i) => `<select class="sel st-sel st-${i.claim_status}" data-claim="${i.id}" aria-label="${t("claim_state")}">${CLAIM_ST.map((s) => `<option value="${s}" ${s === i.claim_status ? "selected" : ""}>${t("st_" + s)}</option>`).join("")}</select>`;
const stTag = (s) => `<span class="tag ${s === "paid" || s === "approved" ? "ok" : s === "to_submit" ? "warn" : s === "rejected" ? "crit" : ""}">${t("st_" + s)}</span>`;
const docLink = (id, label) => (id ? `<button class="linkish" data-doc="${id}">${ic("file").replace('class="i"', 'class="i" style="width:13px;height:13px;vertical-align:-2px"')} ${esc(label || t("open_doc"))}</button>` : "");

async function summary(force) {
  if (force || !state.summary || state.summary._day !== state.day || state.summary._case !== state.caseId) {
    state.summary = await api(C(`/summary?day=${state.day}`));
    state.summary._day = state.day;
    state.summary._case = state.caseId;
  }
  return state.summary;
}

// ---------- colours: each theme has its palettes ----------
const PALETTES = { light: ["verde", "azul", "turquesa", "grafito", "corp", "", "marfil", "pizarra", "lateral"], dark: ["corp", "", "noche", "vino"] };
const logo = (id) => `<svg class="logo-mark" viewBox="0 0 120 108" aria-hidden="true"><defs><linearGradient id="${id}" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#0B5F86"/><stop offset=".55" stop-color="#138C8A"/><stop offset="1" stop-color="#5DCB8A"/></linearGradient></defs><path d="M60 104C22 80 4 58 4 35 4 17 18 4 35 4c11 0 20 6 25 15C65 10 74 4 85 4c17 0 31 13 31 31 0 23-18 45-56 69z" fill="url(#${id})"/><path d="M10 60c26 30 70 32 104-14" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" opacity=".95"/><rect x="31" y="33" width="38" height="13" rx="3" fill="#fff"/><rect x="43.5" y="20.5" width="13" height="38" rx="3" fill="#fff"/></svg>`;
const palSel = () => {
  const th = document.documentElement.dataset.theme === "dark" ? "dark" : "light", cur = document.documentElement.dataset.pal || "";
  return `<label class="pal"><span class="lbl">${t("palette")}</span><select class="sel" data-pal>${PALETTES[th].map((p) => `<option value="${p}" ${p === cur ? "selected" : ""}>${t("pal_" + (p || "classic"))}</option>`).join("")}</select></label>`;
};
const setPal = (p) => {
  const th = document.documentElement.dataset.theme;
  document.documentElement.dataset.pal = p;
  try { localStorage.setItem("dindo.pal." + th, p); } catch (_) {}
};

// ---------- shell ----------
const NAV = [
  ["g_day", [["hoy", "home"], ["calendario", "calendar"], ["tratamiento", "pill"], ["indicaciones", "clipboard"]]],
  ["g_money", [["gastos", "money"], ["seguro", "shield"], ["cotizaciones", "tag"]]],
  ["g_archive", [["evolucion", "report"], ["diagnosticos", "steth"], ["examenes", "flask"], ["documentos", "file"], ["contactos", "users"], ["juicio", "scale"]]],
  ["g_review", [["preguntar", "chat"], ["alertas", "alert"], ["preguntas", "help"], ["capo", "cpu"]]],
];

function renderShell(route) {
  const s = state.summary;
  const c = state.cases.find((x) => x.id === state.caseId);
  const counts = { alertas: s?.findings?.length || 0, preguntas: s?.questions?.length || 0 };
  const caseBtn = `<button class="case-btn" data-open="cases"><b>${esc(c?.title || "")}</b>${ic("down")}</button>`;
  const dark = document.documentElement.dataset.theme === "dark";
  const memberSel = s?.members?.length ? `<label class="who"><span class="lbl">${t("who_am_i")}</span><select class="sel" data-member><option value="">—</option>${s.members.map((m) => `<option value="${m.id}" ${m.id === state.member ? "selected" : ""}>${esc(m.name)}</option>`).join("")}</select></label>` : "";
  $("#side").innerHTML = `<div class="brand">${logo("dg-side")}<div><span class="wm">DINDO</span><span class="tagline">${t("tagline")}</span></div></div>${caseBtn}${memberSel}
    ${NAV.map(([g, items]) => `<div class="ngroup"><span class="lbl">${t(g)}</span>${items.map(([r, i]) =>
      `<a href="#${r}" class="${route === r ? "on" : ""}">${ic(i)}<span>${t("nav_" + r)}</span>${counts[r] ? `<em>${counts[r]}</em>` : ""}</a>`).join("")}</div>`).join("")}
    <div class="side-foot">
      <a class="btn block" href="#subir">${ic("plus")} ${t("upload")}</a>
      <button class="btn danger block" data-open="emergency">${ic("phone")} ${t("emergency")}</button>
      <div class="row2"><select class="sel" data-lang>${["es", "en", "it"].map((l) => `<option value="${l}" ${l === state.lang ? "selected" : ""}>${l.toUpperCase()}</option>`).join("")}</select>
      <button class="btn icon" data-theme-toggle title="${t(dark ? "day" : "night")}" aria-label="${t(dark ? "day" : "night")}">${ic(dark ? "sun" : "moon")}</button></div>
      ${palSel()}
    </div>`;
  $("#mtop").innerHTML = `<span class="mlogo">${logo("dg-top")}</span>${caseBtn}<div class="r"><button class="btn danger sm" data-open="emergency">${ic("phone")} SOS</button><button class="btn icon" data-open="menu" aria-label="${t("nav_mas")}">${ic("menu")}</button></div>`;
  const mob = [["hoy", "home"], ["calendario", "calendar"], ["subir", "plus"], ["tratamiento", "pill"], ["gastos", "money"]];
  $("#mnav").innerHTML = mob.map(([r, i]) => r === "subir"
    ? `<a href="#subir" class="plus ${route === r ? "on" : ""}"><span class="pl">${ic("plus")}</span></a>`
    : `<a href="#${r}" class="${route === r ? "on" : ""}">${ic(i)}<span>${t("nav_" + r)}</span></a>`).join("");
  document.documentElement.lang = state.lang;
}

const pageHead = (title, sub, tools = "") => `<div class="ph"><div><h1>${title}</h1>${sub ? `<div class="sub">${sub}</div>` : ""}</div>${tools ? `<div class="tools">${tools}</div>` : ""}</div>`;

// ---------- HOY ----------
async function viewHoy() {
  const s = await summary();
  const meds = await api(C(`/medications?day=${state.day}`));
  renderShell("hoy");
  const isToday = state.day === state.config.today;
  const nowH = clock().getHours(), hm = nowHM();
  const late = (d) => !d.taken && (state.day < state.config.today || (isToday && d.time < hm));
  // rows: scheduled medications + active ones "as directed"
  const rows = new Map();
  s.doses.forEach((d) => {
    if (!rows.has(d.medication_id)) rows.set(d.medication_id, { name: d.name, dose: d.dose, sub: d.instructions, doses: [] });
    rows.get(d.medication_id).doses.push(d);
  });
  meds.items.filter((m) => !m.every_hours && m.start_date && m.start_date <= state.day &&
    (m.end_date ? m.end_date >= state.day : daysBetween(m.start_date, state.day) <= 14)).slice(0, 3).forEach((m) =>
    rows.set("x" + m.id, { name: m.name, dose: m.dose, sub: t("as_directed"), doses: [] }));
  const tick = (d) => `<button class="tick ${d.taken ? "done" : late(d) ? "late" : ""}" data-dose="${d.medication_id}|${d.scheduled_at}|${d.taken ? 1 : 0}" title="${esc(d.name)} ${d.time}${d.taken_by ? " · " + t("marked_by", { n: esc(d.taken_by) }) : ""}" aria-label="${t("mark_taken")} ${esc(d.name)} ${d.time}">${d.taken ? ic("check") : ""}</button>`;
  const grid = rows.size ? `<div class="hgrid-wrap"><div class="hgrid"><div></div>${[...Array(24)].map((_, h) => `<div class="hh ${isToday && h === nowH ? "now" : ""}">${String(h).padStart(2, "0")}</div>`).join("")}
    ${[...rows.values()].map((r) => `<div class="rx"><b>${esc(r.name)}</b><span class="dose">${esc(r.dose || "")}</span><span class="s">${esc(r.sub || "")}</span></div>
      ${[...Array(24)].map((_, h) => { const d = r.doses.find((x) => Number(x.time.slice(0, 2)) === h); return `<div class="c ${isToday && h === nowH ? "now" : ""}">${d ? tick(d) : ""}</div>`; }).join("")}`).join("")}
    </div></div>` : `<div class="empty">${t("nothing_today")}</div>`;
  const lateList = s.doses.filter(late);
  const agendaItems = [...s.events.map((e) => ({ ...e, today: true })), ...s.next_events];
  const agenda = agendaItems.length ? `<div class="agenda">${agendaItems.slice(0, 6).map((e) => `<div class="it"><i style="background:${kindColor(e.kind)}"></i><div class="one">
      <div class="d">${(e.today ? t("today_btn") + " · " : "") + wd(e.date) + " " + fdate(e.date) + (e.time ? " · " + e.time : "")}</div><span class="ttl" title="${esc(e.title)}">${esc(topic(e.title))}</span></div></div>`).join("")}</div>` : `<div class="empty">${t("no_upcoming")}</div>`;
  const toBuy = s.to_buy.length ? `<div class="list">${s.to_buy.map((m) => `<button class="row" data-doc="${m.document_id}"><span class="ttl">${esc(topic(m.name + (m.dose ? " · " + m.dose : ""), 34))}</span><span class="mono small muted">${fdate(m.start_date)}</span></button>`).join("")}</div>` : `<div class="empty">${t("nothing_to_buy")}</div>`;
  const phones = s.key_contacts.filter((c) => c.phones.length).length ? s.key_contacts.filter((c) => c.phones.length).map((c) => `<div class="phone-row"><span class="ttl">${esc(topic(c.name, 30))}</span><a href="tel:${esc(c.phones[0].replace(/[^\d+]/g, ""))}">${ic("phone")} ${esc(c.phones[0])}</a></div>`).join("") : `<div class="empty">${t("no_phones")}</div>`;
  const ins = s.instructions.length ? s.instructions.slice(0, 6).map((i) => `<div class="ins"><span class="tag ${i.polarity === "avoid" ? "crit" : "ok"}">${t(i.polarity === "avoid" ? "avoid" : "do")}</span><span class="txt ttl">${esc(topic(i.text.charAt(0).toUpperCase() + i.text.slice(1), 70))}</span>${i.until ? `<span class="until">${fdate(i.until)}</span>` : ""}</div>`).join("") : `<div class="empty">${t("no_ins")}</div>`;
  const alerts = s.findings.length ? s.findings.slice(0, 3).map((f) => `<button class="alert-mini" data-doc="${f.document_id || ""}" title="${esc(f.detail)}">${sevTag(f.severity)}<b>${esc(findingTitle(f))}</b></button>`).join("") : `<div class="empty">${t("no_alerts")}</div>`;
  const qLink = s.questions.length ? `<a class="linkish" href="#preguntas">${t("questions_n", { n: s.questions.length })} →</a>` : "";
  const sec = (title, body, extra = "") => `<div class="sec card-m"><div class="sec-h"><span class="lbl">${title}</span>${extra}</div>${body}</div>`;
  // phone: the dose due now + rest of the day
  const pending = s.doses.filter((d) => !d.taken);
  const lateNow = isToday ? pending.find(late) : null;  // an overdue dose comes before the next one
  const next = lateNow || (isToday && pending.find((d) => d.time >= hm)) || pending[0];
  const mins = next && isToday ? Math.round((new Date(`${state.day}T${next.time}:00`) - new Date(`${state.day}T${hm}:00`)) / 60000) : null;
  const dayItems = [...s.doses.map((d) => ({ time: d.time, html: `<span class="t">${d.time}</span><div><b>${esc(d.name)} ${esc(d.dose || "")}</b><span class="s">${d.day_no && d.days_total ? t("day_of", { a: d.day_no, b: d.days_total }) : esc(d.instructions || "")}</span></div>${tick(d)}` })),
    ...s.events.map((e) => ({ time: e.time || "99", html: `<span class="t">${esc(e.time || "—")}</span><div><b>${esc(e.title)}</b><span class="s">${t(KIND[e.kind]?.[0] || "k_other")}</span></div><span></span>` }))].sort((a, b) => a.time.localeCompare(b.time));
  const mobile = `<div class="only-mob stack">
      ${next ? `<div class="nowcard ${lateNow ? "late" : ""}"><span class="lbl">${lateNow ? t("late") + " · " + t("ago_min", { n: -mins }) : mins !== null && mins <= 0 ? t("now") + " · " + next.time : t("next_dose") + (mins ? " · " + t("in_min", { n: mins }) : "")}</span>
        <div class="r"><div class="med">${esc(next.name)} ${esc(next.dose || "")}<span>${esc(next.instructions || "")}</span></div><div class="time">${next.time}</div></div>
        <div class="f"><span>${next.day_no && next.days_total ? t("day_of", { a: next.day_no, b: next.days_total }) : ""}</span><button class="btn sm" data-dose="${next.medication_id}|${next.scheduled_at}|0">${t("mark_taken")}</button></div></div>` : ""}
      <div class="card-m"><div class="sec-h"><span class="lbl">${t("rest_of_day")}</span></div>${dayItems.length ? dayItems.map((x) => `<div class="dayrow">${x.html}</div>`).join("") : `<div class="empty">${t("nothing_today")}</div>`}</div>
    </div>`;
  const noticeText = (n) => ({
    hearing: t("nt_hearing", { n: n.days, x: esc(topic(n.text, 50)) }), visit: (n.days === 1 ? t("nt_tomorrow") : t("nt_in_days", { n: n.days })) + ": " + esc(topic(n.text, 50)),
    buy: n.days ? t("nt_buy", { x: esc(topic(n.text, 40)), n: n.days }) : t("nt_buy_today", { x: esc(topic(n.text, 40)) }), runout: t("nt_runout", { x: esc(topic(n.text, 40)), n: n.days }),
    claim: t("nt_claim", { c: n.count, n: n.days, a: money(n.amount) }), claim_late: t("nt_claim_late", { c: n.count, a: money(n.amount) }), coverage: t("nt_coverage", { p: n.pct }) }[n.kind] || "");
  const notices = s.notices.length ? `<div class="notices">${s.notices.slice(0, 5).map((n) => `<a class="notice ${n.level}" href="#${n.route}">${ic(n.kind === "hearing" ? "scale" : n.kind === "visit" ? "calendar" : n.kind === "claim" || n.kind === "claim_late" || n.kind === "coverage" ? "shield" : "pill")}<span>${noticeText(n)}</span></a>`).join("")}</div>` : "";
  const dayNav = `<button class="btn icon" data-speak title="${t("listen")}" aria-label="${t("listen")}">${ic("speaker")}</button><button class="btn" data-build-visit>${ic("report")} ${t("visit_summary")}</button><button class="btn icon" data-reminders title="${t("reminders")}" aria-label="${t("reminders")}">${ic("bell")}</button><button class="btn icon" data-day="-1" aria-label="‹">${ic("left")}</button><button class="btn" data-day="0">${t("today_btn")}</button><button class="btn icon" data-day="1" aria-label="›">${ic("right")}</button>`;
  $("#view").innerHTML = `${pageHead(t("nav_hoy"), `<span class="mono">${wd(state.day)} ${fdate(state.day)}${isToday ? " · " + hm : ""}</span>${s.case_day ? " · " + t("case_day", { n: s.case_day }) : ""}`, dayNav)}
    <div id="visit-out"></div>${notices}
    ${mobile}
    <div class="sec only-desk"><div class="sec-h"><span class="lbl">${t("sched24")}</span>${s.adherence.pct != null ? `<a href="#tratamiento">${t("adh_short", { p: s.adherence.pct })}</a>` : ""}</div>${grid}
      ${lateList.length ? `<div class="late-line"><span class="tag crit">${t("late")}</span>${lateList.map((d) => `${esc(d.name)} ${d.time}`).join(", ")} · ${t("not_marked")}</div>` : ""}</div>
    <div class="cols c3">${sec(t("agenda"), agenda)}${sec(t("to_buy"), toBuy)}${sec(t("key_phones"), phones, `<a href="#contactos">${t("see_all")}</a>`)}</div>
    <div class="cols wide">${sec(t("current_ins"), ins, `<a href="#indicaciones">→</a>`)}${sec(t("alerts"), alerts + qLink, `<a href="#alertas">→</a>`)}</div>`;
}

// ---------- CALENDARIO ----------
async function viewCalendario() {
  state.calMonth = state.calMonth || state.day.slice(0, 7);
  state.calSel = state.calSel || state.day;
  const [cal, s] = await Promise.all([api(C(`/calendar?month=${state.calMonth}`)), summary()]);
  renderShell("calendario");
  const first = state.calMonth + "-01";
  const startOffset = (D(first).getDay() + 6) % 7;
  let cells = [...Array(42)].map((_, i) => addDays(first, i - startOffset));
  if (cells[35].slice(0, 7) !== state.calMonth) cells = cells.slice(0, 35);
  if (state.calMode === "week") {
    const sel = cells.indexOf(state.calSel) >= 0 ? cells.indexOf(state.calSel) : 0;
    cells = cells.slice(Math.floor(sel / 7) * 7, Math.floor(sel / 7) * 7 + 7);
  }
  const evBy = {}, moneyBy = {}, docsBy = {};
  cal.events.forEach((e) => (evBy[e.date] = evBy[e.date] || []).push(e));
  cal.expenses.forEach((e) => (moneyBy[e.date] = e));
  cal.documents.forEach((d) => (docsBy[d.doc_date] = docsBy[d.doc_date] || []).push(d));
  const courses = cal.courses.slice(0, 3);
  const cell = (iso, i) => {
    const evs = evBy[iso] || [];
    const bars = courses.filter((c) => iso >= c.start_date && iso <= c.end_date).map((c) =>
      `<div class="cbar ${iso === c.start_date || i % 7 === 0 ? "first" : ""} ${iso === c.end_date || i % 7 === 6 ? "last" : ""}" title="${esc(c.name)}"></div>`).join("");
    return `<button class="d ${iso.slice(0, 7) !== state.calMonth ? "out" : ""} ${iso === state.calSel ? "sel" : ""} ${iso === cal.today ? "today" : ""}" data-calday="${iso}">
      <span class="dn">${Number(iso.slice(8))}</span>${bars}
      ${evs.slice(0, 3).map((e) => `<span class="chip" style="border-left-color:${kindColor(e.kind)}" title="${esc(e.title)}">${e.time ? e.time + " " : ""}${esc(e.title)}</span>`).join("")}${evs.length > 3 ? `<span class="more">+${evs.length - 3}</span>` : ""}
      ${evs.length ? `<span class="dots only-mob">${evs.slice(0, 4).map((e) => `<i style="background:${kindColor(e.kind)}"></i>`).join("")}</span>` : ""}
      ${moneyBy[iso] ? `<span class="money">${nf(moneyBy[iso].amount)} Bs</span>` : ""}</button>`;
  };
  const sel = state.calSel;
  const dayEvents = evBy[sel] || [];
  const starts = cal.courses.filter((c) => c.start_date === sel);
  const ongoing = cal.courses.filter((c) => sel > c.start_date && sel <= c.end_date);
  const exp = moneyBy[sel];
  const docIds = new Set((docsBy[sel] || []).map((d) => d.id));
  const qs = s.questions.filter((q) => docIds.has(q.document_id));
  const panel = `<div class="daypanel">
    <div class="sec-h serif"><b>${wd(sel, "long").replace(/^./, (c) => c.toUpperCase())} ${Number(sel.slice(8))}</b><button class="linkish" data-openday="${sel}">${t("open_day")} →</button></div>
    ${dayEvents.map((e) => `<div class="dp-it"><span class="t">${esc(e.time || "—")}</span><i style="background:${kindColor(e.kind)}"></i><div><b>${esc(topic(e.title, 60))}</b><span class="s">${t(KIND[e.kind]?.[0] || "k_other")}${e.place && !e.title.includes(e.place) ? " · " + esc(e.place) : ""}</span>${e.notes ? `<span class="s">${esc(topic(e.notes, 90))}</span>` : ""}${e.document_id ? `<div>${docLink(e.document_id)}</div>` : ""}</div></div>`).join("")}
    ${starts.map((c) => `<div class="dp-it"><span class="t">—</span><i style="background:var(--course)"></i><div><b>${t("starts_course", { name: esc(c.name) })}</b><span class="s">${c.every_hours ? t("course_until", { h: c.every_hours, d: fdate(c.end_date) }) : ""}${c.open_ended ? " · " + t("course_open") : ""}</span></div></div>`).join("")}
    ${ongoing.length ? `<div class="dp-it"><span class="t">Rx</span><i style="background:var(--course)"></i><div><b>${t("ongoing")}</b><span class="s">${ongoing.map((c) => esc(c.name)).join(" · ")}</span></div></div>` : ""}
    ${exp ? `<div class="dp-it"><span class="t">Bs</span><i style="background:var(--k-other)"></i><div><b>${t("expenses_n", { n: exp.n, a: money(exp.amount) })}</b><span class="s">${esc(exp.vendors || "")}</span></div></div>` : ""}
    ${(docsBy[sel] || []).length ? `<div class="dp-it"><span class="t">Doc</span><i style="background:var(--line2)"></i><div><b>${t("docs_day")}</b>${(docsBy[sel] || []).map((d) => `<div>${docLink(d.id, d.title)}</div>`).join("")}</div></div>` : ""}
    ${!dayEvents.length && !starts.length && !exp && !ongoing.length ? `<div class="empty" style="padding-top:14px">${t("no_events")}</div>` : ""}
    ${qs.map((q) => `<div class="callout"><b>${t("pending_q")}</b>${esc(q.question)} <a class="linkish" href="#preguntas">→</a></div>`).join("")}
  </div>`;
  const nEv = cal.events.filter((e) => ["appointment", "study"].includes(e.kind)).length;
  const mTotal = cal.expenses.reduce((a, e) => a + e.amount, 0);
  const tools = `<div class="seg"><button class="${state.calMode === "week" ? "on" : ""}" data-calmode="week">${t("week")}</button><button class="${state.calMode === "month" ? "on" : ""}" data-calmode="month">${t("month")}</button></div>
    <button class="btn icon" data-calnav="-1" aria-label="‹">${ic("left")}</button><button class="btn icon" data-calnav="1" aria-label="›">${ic("right")}</button>`;
  $("#view").innerHTML = `${pageHead(monthTitle(state.calMonth), t("cal_sub", { e: nEv, c: cal.courses.length, m: money(mTotal) }), tools)}
    <div class="legend">${["appointment", "study", "session", "hearing", "surgery"].map((k) => `<span><i style="background:${kindColor(k)}"></i>${t(KIND[k][0])}</span>`).join("")}<span><i style="background:var(--course)"></i>${t("k_course")}</span></div>
    <div class="cols" style="grid-template-columns:minmax(0,2.7fr) minmax(0,1fr);align-items:start">
      <div class="cal">${["lu", "ma", "mi", "ju", "vi", "sá", "do"].map((_, i) => `<div class="dow">${wd(addDays("2023-01-02", i)).replace(".", "")}</div>`).join("")}${cells.map(cell).join("")}</div>
      <div class="card-m">${panel}</div>
    </div>`;
  if (window.matchMedia("(max-width: 959px)").matches) $("#view .cols").style.gridTemplateColumns = "1fr";
}

// ---------- TRATAMIENTO ----------
async function viewTratamiento() {
  state.txStart = state.txStart || addDays(state.day, -6);
  const [wk, meds] = await Promise.all([api(C(`/doses?start=${state.txStart}&days=7`)), api(C(`/medications?day=${state.day}`))]);
  await summary();
  renderShell("tratamiento");
  const days = wk.days.map((d) => d.date);
  const end = days[6];
  const byMed = new Map();
  wk.days.forEach((d) => d.doses.forEach((x) => {
    if (!byMed.has(x.medication_id)) byMed.set(x.medication_id, new Map());
    byMed.get(x.medication_id).set(`${d.date}|${x.time}`, x);
  }));
  const active = meds.items.filter((m) => byMed.has(m.id) || (!m.every_hours && m.start_date && m.start_date <= end &&
    (m.end_date ? m.end_date >= state.txStart : daysBetween(m.start_date, end) <= 30)));
  const earlier = meds.items.filter((m) => !active.includes(m) && m.start_date && m.start_date < state.txStart);
  const block = (m) => {
    const map = byMed.get(m.id);
    const times = map ? [...new Set([...map.values()].map((x) => x.time))].sort() : [];
    let prog = "";
    if (m.start_date && m.end_date) {
      const total = daysBetween(m.start_date, m.end_date) + 1;
      const n = Math.min(total, Math.max(0, daysBetween(m.start_date, state.day) + 1));
      prog = `<div class="progress"><i style="width:${(n / total) * 100}%"></i></div><div class="pmeta">${t("day_of", { a: n, b: total })} · ${t("ends", { d: D(m.end_date).toLocaleDateString(locale(), { day: "numeric", month: "short", year: "numeric" }) })}</div>`;
    } else if (m.start_date) {
      prog = `<div class="pmeta">${fdate(m.start_date)} · ${t("no_end")}</div>`;
    }
    const grid = times.length ? `<div class="wgrid"><span></span>${days.map((d) => `<span class="h ${d === state.day ? "today" : ""}">${wd(d).replace(".", "")}<br>${Number(d.slice(8))}</span>`).join("")}
      ${times.map((tm) => `<span class="t">${tm}</span>${days.map((d) => { const x = map.get(`${d}|${tm}`); if (!x) return "<span></span>";
        const lt = !x.taken && (d < state.config.today || (d === state.config.today && tm < nowHM()));
        return `<button class="tick ${x.taken ? "done" : lt ? "late" : ""}" data-dose="${x.medication_id}|${x.scheduled_at}|${x.taken ? 1 : 0}" aria-label="${esc(m.name)} ${d} ${tm}">${x.taken ? ic("check") : ""}</button>`; }).join("")}`).join("")}</div>`
      : `<em class="muted">${t("as_directed")}</em>`;
    return `<div class="med-block"><div class="top"><span class="nm">${esc(m.name)}${m.dose ? " · " + esc(m.dose) : ""}</span><span class="muted small">${esc(m.instructions || "")}</span></div>
      ${prog}${grid}<div class="small">${docLink(m.document_id)}</div></div>`;
  };
  const tools = `<button class="btn" data-open="addmed">${ic("plus")} ${t("add_med")}</button><button class="btn icon" data-txnav="-7" aria-label="‹">${ic("left")}</button><button class="btn" data-txnav="0">${t("today_btn")}</button><button class="btn icon" data-txnav="7" aria-label="›">${ic("right")}</button>`;
  const adh = state.summary.adherence;
  const members = Object.entries(adh.by_member).filter(([k]) => k);
  const adhStrip = adh.expected ? `<div class="kpis"><div><b>${adh.pct} %</b><span>${t("adh_7")}</span></div><div><b>${adh.taken}/${adh.expected}</b><span>${t("adh_doses")}</span></div>
    <div><b>${adh.streak}</b><span>${t("adh_streak")}</span></div><div><b style="font-size:16px">${members.length ? members.map(([k, v]) => `${esc(k)} ${v}`).join(" · ") : "—"}</b><span>${t("adh_who")}</span></div></div>` : "";
  $("#view").innerHTML = `${pageHead(t("treatment"), `${fdm(state.txStart)} – ${fdate(end)}`, tools)}${adhStrip}
    <div class="sec">${active.filter((m) => byMed.has(m.id)).map(block).join("") || (active.length ? "" : `<div class="empty">${t("no_meds")}</div>`)}</div>
    ${active.some((m) => !byMed.has(m.id)) ? `<div class="sec"><div class="sec-h"><span class="lbl">${t("as_directed_list")}</span></div><div class="list compact">${active.filter((m) => !byMed.has(m.id)).map((m) => `<button class="row" data-doc="${m.document_id || ""}"><span class="ttl">${esc(m.name)}${m.dose ? " · " + esc(m.dose) : ""}</span><span class="mono small muted">${fdate(m.start_date)}</span></button>`).join("")}</div></div>` : ""}
    ${earlier.length ? `<div class="sec"><div class="sec-h"><span class="lbl">${t("earlier")}</span></div><div class="list">${earlier.map((m) => `<div class="row"><div>${esc(m.name)} ${m.dose ? "· " + esc(m.dose) : ""}<span class="s">${esc(m.instructions || "")}</span><div class="small">${docLink(m.document_id, m.document_title)}</div></div><span class="mono small muted">${fdate(m.start_date)}${m.end_date ? " – " + fdate(m.end_date) : ""}</span></div>`).join("")}</div></div>` : ""}`;
}

// ---------- INDICACIONES ----------
async function viewIndicaciones() {
  const [items] = await Promise.all([api(C("/instructions")), summary()]);
  renderShell("indicaciones");
  const KINDS = ["diet", "activity", "care", "medication", "other"];
  const kindOf = (i) => (KINDS.includes(i.kind) ? i.kind : "other");
  // one block per date, newest first; undated ones at the end
  const dates = [...new Set(items.map((i) => i.start_date || ""))].sort((a, b) => (!a ? 1 : !b ? -1 : b.localeCompare(a)));
  const docsOf = (list) => [...new Map(list.filter((i) => i.document_id).map((i) => [i.document_id, i.document_title])).entries()];
  const row = (i) => { const exp = i.until && i.until < state.day; return `<div class="ins ${exp ? "expired" : ""}" style="flex-direction:column;align-items:stretch;gap:4px;border-bottom:1px solid var(--line);padding:12px 0">
      <div style="display:flex;gap:12px;align-items:baseline"><span class="tag ${i.polarity === "avoid" ? "crit" : "ok"}">${t(i.polarity === "avoid" ? "avoid" : "do")}</span><span class="txt cap">${esc(i.text)}</span></div>
      <div class="small muted" style="padding-left:2px">${t("ik_" + kindOf(i))}${i.until ? ` · <span class="mono">${t("until", { d: fdate(i.until) })}</span>${exp ? " · " + t("expired") : ""}` : ""}</div></div>`; };
  $("#view").innerHTML = `${pageHead(t("ins_title"), t("ins_sub", { n: items.length }))}
    ${dates.length ? dates.map((d) => { const list = items.filter((i) => (i.start_date || "") === d); return `<div class="sec">
      <div class="sec-h"><span class="lbl">${d ? wd(d) + " " + fdate(d) : t("no_date")}</span><span class="small">${docsOf(list).map(([id, title]) => docLink(id, title)).join(" ")}</span></div>
      <div>${list.map(row).join("")}</div></div>`; }).join("")
      : `<div class="empty">${t("ins_empty")}</div>`}`;
}

// ---------- GASTOS ----------
async function viewGastos() {
  const [e, s] = await Promise.all([api(C("/expenses")), summary()]);
  renderShell("gastos");
  const members = s.members;
  let items = e.items;
  if (state.expPeriod === "month") items = items.filter((i) => i.date.slice(0, 7) === state.day.slice(0, 7));
  if (state.expPeriod === "week") items = items.filter((i) => i.date > addDays(state.day, -7) && i.date <= state.day);
  const shown = state.expCat ? items.filter((i) => i.category === state.expCat) : items;
  const recovered = e.items.filter((i) => ["approved", "paid"].includes(i.claim_status)).reduce((a, i) => a + (i.reimbursed_amount || i.amount), 0);
  const errors = e.items.filter((i) => i.problems.length).length;
  const cats = {};
  items.forEach((i) => { cats[i.category] = cats[i.category] || { amount: 0, n: 0 }; cats[i.category].amount += i.amount; cats[i.category].n++; });
  const catList = Object.entries(cats).sort((a, b) => b[1].amount - a[1].amount);
  const maxCat = Math.max(1, ...catList.map(([, v]) => v.amount));
  const payers = {};
  items.forEach((i) => { const k = i.paid_by_name || t("unassigned"); payers[k] = (payers[k] || 0) + i.amount; });
  const maxPay = Math.max(1, ...Object.values(payers));
  const dates = e.items.map((i) => i.date).sort();
  const title = (i) => esc((i.line_items[0]?.description || i.description || i.vendor || "").split(";")[0]);
  const row = (i) => {
    const sub = i.line_items.length > 1 || (i.line_items.length === 1 && i.line_items[0].description !== title(i));
    const paidSel = (i) => `<select class="sel" data-paid="${i.id}" aria-label="${t("paid")}"><option value="">${t("unassigned")}</option>${members.map((m) => `<option value="${m.id}" ${m.id === i.paid_by ? "selected" : ""}>${esc(m.name)}</option>`).join("")}</select>`;
    return `<tr class="main-row ${sub ? "has-sub" : ""}" data-doc="${i.document_id || ""}">
      <td class="mono">${fdm(i.date)}<br><span class="muted small">${i.date.slice(0, 4)}</span></td>
      <td><b>${title(i)}</b>${i.vendor ? ` · ${esc(i.vendor)}` : ""}
        <div class="tags">${i.reimbursable ? `<span class="tag ok plain">${t("reimbursable")}</span>` : ""}${i.claim_status && i.claim_status !== "not_applicable" ? claimSel(i) : ""}
        ${i.note ? `<span class="tag warn plain" title="${esc(i.note)}">${t("not_medical_tag")}</span>` : ""}
        ${i.problems.slice(0, 2).map((p) => `<span class="tag crit plain" title="${esc(p)}">${esc(p.length > 46 ? p.slice(0, 44) + "…" : p)}</span>`).join("")}
        ${i.invoice_number ? `<span class="tag plain">${t("invoice_n", { n: esc(i.invoice_number) })}</span>` : ""}<span class="tag plain" style="border-color:${catColor(i.category)};color:${catColor(i.category)}">${t("cat_" + i.category)}</span></div>
        <label class="only-mob mob-paid"><span class="small muted">${t("paid")}:</span> ${paidSel(i)}</label></td>
      <td>${paidSel(i)}</td>
      <td class="r mono">${nf(i.amount, 2)}</td></tr>
      ${sub ? `<tr class="sub"><td></td><td colspan="3"><ul>${i.line_items.map((li) => `<li>${esc(li.description || "")}${li.amount != null ? " · " + nf(li.amount, 2) : ""}</li>`).join("")}</ul></td></tr>` : ""}`;
  };
  const tools = `<div class="seg">${[["all", "all"], ["month", "month"], ["week", "week"]].map(([k, l]) => `<button class="${state.expPeriod === k ? "on" : ""}" data-expperiod="${k}">${t(l)}</button>`).join("")}</div><button class="btn" data-export>${t("export")}</button>`;
  $("#view").innerHTML = `${pageHead(t("exp_title"), dates.length ? t("exp_sub", { a: fdate(dates[0]), b: fdate(dates[dates.length - 1]), n: e.items.length }) : "", tools)}
    <div class="kpis"><div><b>${nf(e.total)}</b><span>${t("k_spent")}</span></div><div><b>${nf(e.reimbursable)}</b><span>${t("k_reimb")}</span></div>
      <div><b>${nf(recovered)}</b><span>${t("k_recovered")}</span></div><div><b style="color:var(--crit)">${errors}</b><span>${t("k_errors")}</span></div></div>
    <form class="sec" id="ask-form"><div class="ask-box"><input class="input" id="ask-q" placeholder="${t("ask_ph")}" ${state.config.ai_connected ? "" : "disabled"} autocomplete="off"><button class="btn primary" ${state.config.ai_connected ? "" : "disabled"}>${t("ask")}</button></div>
      <div class="chat" id="ask-log"></div>${state.config.ai_connected ? "" : `<span class="small muted">${t("ask_off")}</span>`}</form>
    <div class="cols wide">
      <div class="sec"><div class="sec-h serif"><b>${state.expCat ? t("movements_cat", { c: t("cat_" + state.expCat) }) : t("movements")}</b>${state.expCat ? `<button class="linkish" data-expcat="">${t("show_all")}</button>` : ""}</div>
        <div style="overflow-x:auto"><table class="tbl"><thead><tr><th>${t("date")}</th><th>${t("what")}</th><th>${t("paid")}</th><th class="r">${t("amount")}</th></tr></thead><tbody>${shown.map(row).join("") || `<tr><td colspan="4" class="empty">—</td></tr>`}</tbody></table></div></div>
      <div class="sec">
        <div class="sec-h serif"><b>${t("by_cat")}</b></div>
        <div>${catList.map(([k, v]) => `<button class="cat-row ${state.expCat === k ? "on" : ""}" data-expcat="${k}"><i style="background:${catColor(k)}"></i><span>${t("cat_" + k)}</span>
          <span class="bar"><i style="width:${(v.amount / maxCat) * 100}%;background:${catColor(k)}"></i></span><span class="v">${nf(v.amount)}<small>${v.n} ${t("receipts")}</small></span></button>`).join("")}</div>
        <div class="sec-h serif" style="margin-top:14px"><b>${t("who_paid")}</b></div>
        <div>${Object.entries(payers).map(([k, v]) => `<div class="cat-row" style="grid-template-columns:minmax(0,1fr) 110px 100px"><span>${esc(k)}</span><span class="bar"><i style="width:${(v / maxPay) * 100}%;background:var(--ink2)"></i></span><span class="v">${nf(v)}</span></div>`).join("")}</div>
      </div>
    </div>`;
}

// ---------- DIAGNÓSTICOS ----------
async function viewDiagnosticos() {
  const [list] = await Promise.all([api(C("/diagnoses")), summary()]);
  renderShell("diagnosticos");
  const who = (d) => [d.doctor, d.specialty, d.issuer].filter(Boolean).filter((v, i, a) => a.indexOf(v) === i).map(esc).join(" · ");
  $("#view").innerHTML = `${pageHead(t("nav_diagnosticos"), t("dx_sub", { n: list.length }))}
    <div class="callout">${t("dx_note")}</div>
    ${list.length ? `<div class="sec"><div class="dx-list">${list.map((d) => `<div class="dx">
      <span class="mono small muted">${d.date ? fdate(d.date) : t("no_date")}</span>
      <div><b class="dx-text">${esc(d.diagnosis)}</b><span class="s">${who(d)}</span><div class="small">${docLink(d.document_id, d.title)}</div></div></div>`).join("")}</div></div>`
      : `<div class="empty">${t("dx_empty")}</div>`}`;
}

// ---------- PEDIDOS DE EXÁMENES ----------
async function viewExamenes() {
  const [orders] = await Promise.all([api(C("/study-orders")), summary()]);
  renderShell("examenes");
  const all = orders.flatMap((o) => o.studies), done = all.filter((s) => s.status === "done").length;
  $("#view").innerHTML = `${pageHead(t("nav_examenes"), t("ex_sub", { n: all.length, o: orders.length, d: done }))}
    ${orders.length ? `<div class="cols c2">${orders.map((o) => `<div class="sec"><div class="sec-h"><span class="lbl">${o.date ? fdate(o.date) : t("no_date")}</span>${docLink(o.document_id)}</div>
      <div class="ex-head"><b>${esc(o.doctor || o.issuer || o.title)}</b>${o.doctor && o.issuer ? `<span class="s">${esc(o.issuer)}</span>` : ""}${o.reason ? `<span class="s">${t("ex_reason")}: ${esc(o.reason)}</span>` : ""}</div>
      <div class="list">${o.studies.map((s) => `<div class="row"><span class="${s.status === "done" ? "muted" : ""}">${s.status === "done" ? "✓ " : ""}${esc(s.name)}</span>
        <button class="btn sm" data-status="tasks|${s.id}|${s.status === "done" ? "pending" : "done"}">${t(s.status === "done" ? "ex_undo" : "ex_done")}</button></div>`).join("")}</div></div>`).join("")}</div>`
      : `<div class="empty">${t("ex_empty")}</div>`}`;
}

// ---------- COTIZACIONES ----------
async function viewCotizaciones() {
  const [qs] = await Promise.all([api(C("/quotes")), summary()]);
  renderShell("cotizaciones");
  $("#view").innerHTML = `${pageHead(t("quotes"), t("quotes_sub"))}
    ${qs.length ? `<div class="cols c2">${qs.map((g) => `<div class="card-m"><div class="sec-h q-head"><span><b class="q-title">${esc(g.product)}</b><span class="q-count">${g.options.length} ${t(g.options.length === 1 ? "option" : "options")}</span></span>
        ${g.purchase ? `<span class="tag ok plain">${t("bought_at", { v: esc(g.purchase.vendor || ""), a: money(g.purchase.amount) })}</span>` : ""}</div>
        <div class="list">${g.options.map((o) => `<button class="row" data-doc="${o.document_id}"><div style="min-width:0"><span class="ttl">${esc(topic(o.item || "", 52))}</span><span class="s">${[o.seller, o.phone, o.date && fdate(o.date)].filter(Boolean).map(esc).join(" · ")}</span></div><span class="mono">${o.price != null ? money(o.price) : "—"}</span></button>`).join("")}</div></div>`).join("")}</div>` : `<div class="empty">${t("no_quotes")}</div>`}`;
}

// ---------- SEGURO ----------
async function viewSeguro() {
  const [ins, s] = await Promise.all([api(C("/insurance")), summary()]);
  renderShell("seguro");
  if (!ins.policy) { $("#view").innerHTML = `${pageHead(t("nav_seguro"))}<div class="empty">${t("no_policy")}</div>`; return; }
  const p = await api(C("/packages/insurance"));
  const lim = ins.policy.coverage_limit || 0;
  const used = p.recovered + p.in_claim;
  const sent = ins.items.filter((i) => ["submitted", "approved", "paid", "rejected"].includes(i.claim_status));
  $("#view").innerHTML = `${pageHead(t("nav_seguro"), `${esc(ins.policy.insurer)} · NIT ${esc(ins.policy.nit || "")}`)}
    ${lim ? `<div class="sec coverage"><span class="lbl">${t("ins_used")}</span><div><b>${money(used)}</b><span class="of">/ ${money(lim)}</span></div>
      <div class="bigbar"><i style="width:${Math.min(100, (used / lim) * 100)}%"></i></div><span class="mono small muted">${Math.round((used / lim) * 100)} % · ${t("available", { a: money(lim - used) })}</span></div>` : ""}
    <div class="cols c3">
      <div class="sec card-m"><div class="sec-h"><span class="lbl">${t("to_send", { n: p.include.length })}</span></div>
        <div class="list">${p.include.map((i) => `<div class="row"><div>${esc(i.vendor || "")} ${i.invoice_number ? "N.º " + esc(i.invoice_number) : ""}<span class="s">${fdate(i.date)} · <button class="linkish" data-claimset="${i.id}|submitted">${t("mark_one_sent")}</button></span></div><span class="mono">${money(i.amount)}</span></div>`).join("") || `<div class="empty">—</div>`}</div>
        <div id="pkg-out" style="display:flex;gap:8px;flex-wrap:wrap">${p.include.length ? `<button class="btn primary" data-build="insurance">${t("build_claim")}</button><button class="btn" data-claimall="${p.include.map((i) => i.id).join(",")}">${t("mark_all_sent")}</button>` : ""}</div></div>
      <div class="sec card-m"><div class="sec-h"><span class="lbl">${t("to_fix", { n: p.fix.length })}</span></div>
        ${p.fix.map((i) => `<div class="list"><div class="row" data-doc="${i.document_id}" style="cursor:pointer"><div>${esc(i.vendor || "")} ${i.invoice_number ? "N.º " + esc(i.invoice_number) : ""}${i.problems.map((x) => `<span class="s"><span class="tag crit">Error</span> ${esc(x)}</span>`).join("")}</div><span class="mono">${money(i.amount)}</span></div></div>`).join("") || `<div class="empty">—</div>`}</div>
      <div class="sec card-m"><div class="sec-h"><span class="lbl">${t("sent", { n: sent.length })}</span></div>
        <div class="list">${sent.map((i) => `<div class="row"><div>${esc(i.vendor || "")}<span class="s">${fdate(i.date)}</span></div><div style="text-align:right"><span class="mono">${money(i.amount)}</span><br>${claimSel(i)}</div></div>`).join("") || `<div class="empty">—</div>`}</div></div>
    </div>`;
}

// ---------- DOCUMENTOS ----------
async function viewDocumentos() {
  const [docs] = await Promise.all([api(C("/documents")), summary()]);
  renderShell("documentos");
  const types = [...new Set(docs.map((d) => d.doc_type))];
  const shown = state.docType ? docs.filter((d) => d.doc_type === state.docType) : docs;
  $("#view").innerHTML = `${pageHead(t("nav_documentos"), t("docs_n", { n: docs.length }))}
    ${types.length > 1 ? `<div class="chips"><button class="${!state.docType ? "on" : ""}" data-doctype="">${t("all_types")}</button>${types.map((ty) => `<button class="${state.docType === ty ? "on" : ""}" data-doctype="${ty}">${t("dt_" + ty)}</button>`).join("")}</div>` : ""}
    <div class="docgrid">${shown.map((d) => `<button class="doc-card" data-doc="${d.id}"><div class="thumb">${/\.(jpe?g|png|webp)$/i.test(d.file_path || "") ? `<img src="/api/documents/${d.id}/file" alt="" loading="lazy">` : ic("file")}</div>
      <span class="lbl">${t("dt_" + d.doc_type)}</span><b>${esc(d.title)}</b><span class="d">${fdate(d.doc_date)}</span></button>`).join("")}</div>`;
}

// ---------- CONTACTOS ----------
const CT_GROUPS = ["emergency", "doctor", "clinic", "pharmacy", "legal", "other"];
function contactRow(c, emergency) {
  const ph = c.phones[0];
  return `<div class="ct"><div><b>${esc(c.name)}</b><span class="s">${esc([c.role, c.organization].filter(Boolean).join(" · "))}</span>
    ${c.phones.slice(0, 2).map((p) => `<span class="ph-num">${esc(p)}</span>`).join("")}${c.phones.length > 2 ? `<span class="s mono">${c.phones.slice(2).map(esc).join(" · ")}</span>` : ""}</div>
    ${ph ? `<div class="acts"><button class="btn icon" data-copy="${esc(ph)}" aria-label="${t("copy")}">${ic("copy")}</button><a class="btn ${emergency ? "danger" : ""}" href="tel:${esc(ph.replace(/[^\d+]/g, ""))}">${ic("phone")} ${t("call")}</a></div>` : ""}</div>`;
}
async function viewContactos() {
  const [cs] = await Promise.all([api(C("/contacts")), summary()]);
  renderShell("contactos");
  const groups = CT_GROUPS.map((g) => [g, cs.filter((c) => c.group === g)]).filter(([g, v]) => v.length || g === "emergency");
  $("#view").innerHTML = `${pageHead(t("nav_contactos"), "", `<button class="btn" data-open="addcontact">${ic("plus")} ${t("add_contact")}</button>`)}
    <div class="cols c2">${groups.map(([g, list]) => `<div class="sec card-m"><div class="sec-h"><span class="lbl">${t("ct_" + g)}</span></div>
      ${list.length ? list.map((c) => contactRow(c, g === "emergency")).join("") : `<div class="empty">${t("no_emergency")}</div>`}</div>`).join("")}</div>`;
}

// ---------- JUICIO ----------
async function viewJuicio() {
  const [p, s] = await Promise.all([api(C("/packages/legal")), summary()]);
  renderShell("juicio");
  const legalDocs = p.documents.filter((d) => d.doc_type === "legal");
  $("#view").innerHTML = `${pageHead(t("lawsuit"), esc(s.case.summary || ""), `<span id="pkg-out"><button class="btn primary" data-build="legal">${t("build_evidence")}</button></span>`)}
    <div class="cols c3">
      <div class="sec card-m"><div class="sec-h"><span class="lbl">${t("hearings")}</span></div>
        ${p.hearings.map((h) => `<div class="hearing"><span class="mono small muted">${fdate(h.date)}${h.time ? " · " + esc(h.time) : ""}</span><span>${esc(h.title)}</span><span>${h.date < state.config.today ? `<span class="tag">${t("held")}</span>` : `<span class="tag warn">${t("upcoming")}</span>`}</span></div>`).join("") || `<div class="empty">${t("no_hearings")}</div>`}</div>
      <div class="sec card-m"><div class="sec-h"><span class="lbl">${t("legal_contacts")}</span></div>
        ${p.legal_contacts.map((c) => `<div class="ct"><div><b>${esc(c.name)}</b><span class="s">${esc(c.role || "")}</span>${JSON.parse(c.phones || "[]").map((x) => `<span class="ph-num" style="font-size:18px">${esc(x)}</span>`).join("")}</div></div>`).join("") || `<div class="empty">—</div>`}</div>
      <div class="sec card-m"><div class="sec-h"><span class="lbl">${t("legal_docs")}</span></div>
        <div class="list">${legalDocs.map((d) => `<div class="row" data-doc="${d.id}" style="cursor:pointer"><div>${esc(d.title)}<span class="s mono">${fdate(d.doc_date)}</span></div></div>`).join("") || `<div class="empty">${t("no_legal")}</div>`}</div>
        <span class="small muted">+ ${p.counts.medical} ${t("nav_documentos").toLowerCase()} · ${money(p.total)}</span></div>
    </div>`;
}

// ---------- ALERTAS ----------
async function viewAlertas() {
  const [fs] = await Promise.all([api(C("/findings")), summary()]);
  renderShell("alertas");
  const open = fs.filter((f) => f.status === "open");
  const main = open.filter((f) => f.severity !== "info"), minor = open.filter((f) => f.severity === "info");
  const item = (f) => `<div class="alert-item ${f.severity === "critical" ? "crit" : f.severity === "info" ? "info" : ""}">
    <div style="display:flex;gap:6px;flex-wrap:wrap">${sevTag(f.severity)}<span class="tag plain">${t("src_" + (f.source || "ai").replace("+", "_"))}</span></div>
    <h3>${esc(findingTitle(f))}</h3><span>${esc(f.detail)}</span><span class="small">${t("source")}: ${docLink(f.document_id, f.title)}</span>
    <div class="acts"><button class="btn sm" data-status="findings|${f.id}|resolved">${t("resolved")}</button><button class="btn sm" data-status="findings|${f.id}|dismissed">${t("dismiss")}</button></div></div>`;
  $("#view").innerHTML = `${pageHead(t("nav_alertas"), t("open_n", { n: main.length }))}
    <div class="sec">${main.map(item).join("") || `<div class="empty">${t("no_alerts")}</div>`}</div>
    ${minor.length ? `<div class="sec"><button class="linkish" data-showinfo>${t("show_minor", { n: minor.length })}</button>${state.showInfo ? minor.map(item).join("") : ""}</div>` : ""}`;
}

// ---------- PREGUNTAS ----------
function questionsHtml(qs) {
  return qs.filter((q) => q.status === "open").map((q) => `<div class="q-item" data-q="${q.id}"><h3>${esc(q.question)}</h3>${q.document_id ? docLink(q.document_id) : ""}
    <div class="opts">${JSON.parse(q.options || "[]").map((o) => `<button class="btn" data-answer="${q.id}" data-value="${esc(o)}">${esc(o)}</button>`).join("")}</div>
    <form data-answer-form="${q.id}"><input class="input" placeholder="${t("other_answer")}" autocomplete="off"><button class="btn">${t("ok")}</button></form></div>`).join("");
}
async function viewPreguntas() {
  const s = await summary(true);
  renderShell("preguntas");
  $("#view").innerHTML = `${pageHead(t("q_title"))}<div class="sec"><div class="sec-h"><span class="lbl">${t("q_help")}</span></div>${questionsHtml(s.questions) || `<div class="empty">${t("q_none")}</div>`}</div>`;
}

// ---------- EVOLUCIÓN ----------
async function viewEvolucion() {
  const [items] = await Promise.all([api(C("/evolution")), summary()]);
  renderShell("evolucion");
  const f = state.evoFilter || "all";
  const accidentDate = items.find((x) => x.kind === "accident")?.date;
  const merged = [];
  items.forEach((x) => {
    const prev = merged[merged.length - 1];
    if (x.kind === "med_start" && prev && prev.kind === "med_start" && prev.date === x.date && !x.every_hours && !prev.every_hours) {
      prev.names = (prev.names || [prev.title + (prev.dose ? " " + prev.dose : "")]).concat(x.title + (x.dose ? " " + x.dose : ""));
    } else merged.push({ ...x });
  });
  const unsure = accidentDate ? merged.filter((x) => x.date < accidentDate) : [];
  const shown = merged.filter((x) => (f === "all" || x.group === f) && !unsure.includes(x));
  const months = {};
  shown.forEach((x) => (months[x.date.slice(0, 7)] = months[x.date.slice(0, 7)] || []).push(x));
  const color = (x) => x.group === "medication" ? "var(--k-medication)" : x.group === "legal" ? "var(--k-legal)" : x.group === "study" ? "var(--k-lab_imaging)" : kindColor(x.kind);
  const label = (x) => ({ med_start: t("evo_med"), instruction: t(x.polarity === "avoid" ? "avoid" : "do"), session: t("k_session") }[x.kind]
    || (x.kind.startsWith("doc_") ? t("dt_" + x.kind.slice(4)) : t(KIND[x.kind]?.[0] || "k_other")));
  const title = (x) => x.kind === "session" ? t("evo_sessions", { n: x.count, a: fdm(x.date), b: fdm(x.until) }) + (x.title ? " · " + esc(topic(x.title, 40)) : "")
    : x.kind === "med_start" ? (x.names ? `${t("evo_meds_day")}: ${esc(topic(x.names.join(", "), 110))}` : `${t("starts_course", { name: esc(x.title) })}${x.dose ? " " + esc(x.dose) : ""}`) : esc(topic(x.title, 90));
  const sub = (x) => x.kind === "med_start" ? [x.every_hours ? t("every_h", { h: x.every_hours }) : t("as_directed"), x.until ? t("until", { d: fdate(x.until) }) : ""].filter(Boolean).join(" · ")
    : x.kind === "instruction" && x.until ? t("until", { d: fdate(x.until) }) : esc(topic(x.detail || "", 140));
  const first = shown[0]?.date, accident = accidentDate || first;
  $("#view").innerHTML = `${pageHead(t("nav_evolucion"), shown.length ? t("evo_sub", { a: fdate(first), b: fdate(shown[shown.length - 1].date), n: shown.length }) : "", `<button class="btn primary" data-evo-ai>${t("evo_ai")}</button>`)}
    <div id="evo-ai"></div>
    <div class="chips">${["all", "clinical", "medication", "study", "legal"].map((k) => `<button class="${f === k ? "on" : ""}" data-evofilter="${k}">${t("evo_f_" + k)}</button>`).join("")}</div>
    ${Object.entries(months).map(([ym, list]) => `<div class="evo-month"><div class="evo-mh"><b>${monthTitle(ym)}</b>${accident ? `<span class="mono small muted">${t("case_month", { n: Math.max(1, Math.round(daysBetween(accident, ym + "-15") / 30) + 1) })}</span>` : ""}</div>
      <div class="evo-list">${list.map((x) => `<div class="evo-it"><span class="evo-d mono">${fdm(x.date)}</span><i style="background:${color(x)}"></i>
        <div class="evo-body"><span class="lbl" style="color:${color(x)}">${label(x)}</span><b>${title(x)}</b>${sub(x) ? `<span class="s">${sub(x)}</span>` : ""}
          ${x.thumb ? `<button class="evo-thumb" data-doc="${x.document_id}"><img src="/api/documents/${x.document_id}/file" alt="" loading="lazy"></button>` : x.document_id ? docLink(x.document_id) : ""}</div></div>`).join("")}</div></div>`).join("") || `<div class="empty">—</div>`}
    ${unsure.length && f === "all" ? `<div class="evo-month"><div class="evo-mh"><b>${t("evo_unsure")}</b><span class="small muted">${t("evo_unsure_sub")}</span></div><div class="list compact">${unsure.map((x) => `<button class="row" data-doc="${x.document_id || ""}"><span class="ttl">${esc(topic(x.title, 80))}</span><span class="mono small muted">${fdate(x.date)}</span></button>`).join("")}</div></div>` : ""}`;
}

// ---------- PREGUNTAR ----------
async function viewPreguntar() {
  await summary();
  renderShell("preguntar");
  const sugg = ["ask_s1", "ask_s2", "ask_s3", "ask_s4", "ask_s5"].map((k) => t(k));
  $("#view").innerHTML = `${pageHead(t("nav_preguntar"), t("ask_case_sub"))}
    <form class="sec" id="case-ask"><div class="ask-box"><input class="input" id="case-q" placeholder="${t("ask_case_ph")}" autocomplete="off" ${state.config.ai_connected ? "" : "disabled"}><button class="btn primary" ${state.config.ai_connected ? "" : "disabled"}>${t("ask")}</button></div>
      <div class="chips">${sugg.map((q) => `<button type="button" data-suggest="${esc(q)}">${esc(q)}</button>`).join("")}</div>
      <div class="chat" id="case-log"></div></form>`;
}
function renderAnswer(text) {
  return esc(text).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/^[-*] /gm, "• ").replace(/\n/g, "<br>")
    .replace(/\[doc:\s*(\d+)\]/g, (_, id) => `<button class="doclink" data-doc="${id}">${ic("file")}</button>`);
}

// ---------- BAJO EL CAPÓ ----------
async function viewCapo() {
  const [c] = await Promise.all([api("/api/ai-calls?limit=80"), summary()]);
  renderShell("capo");
  const tok = c.totals.reduce((a, m) => a + (m.tin || 0) + (m.tout || 0), 0);
  const n = c.totals.reduce((a, m) => a + m.n, 0);
  $("#view").innerHTML = `${pageHead(t("nav_capo"), t("hood_sub", { n, t: nf(tok) }))}
    <div class="sec"><span class="lbl">Endpoint</span><span class="mono small" style="overflow-wrap:anywhere">${esc(c.endpoint || "—")}</span></div>
    <div class="kpis">${c.totals.slice(0, 4).map((m) => `<div><b style="font-size:17px">${esc(m.model)}</b><span>${m.n} · ${(m.avg_ms / 1000).toFixed(1)} s · ${nf((m.tin || 0) + (m.tout || 0))} tok</span></div>`).join("")}</div>
    <div class="tbl-card" style="overflow-x:auto"><table class="tbl"><thead><tr><th>${t("date")}</th><th>${t("model")}</th><th>${t("purpose")}</th><th>${t("document")}</th><th class="r">${t("latency")}</th><th class="r">${t("tokens")}</th></tr></thead>
    <tbody>${c.calls.map((x) => `<tr><td class="mono small muted">${esc(x.created_at)}</td><td class="mono small">${esc(x.model)}${x.ok ? "" : ` <span class="tag crit">error</span>`}</td><td>${t("p_" + x.purpose)}</td><td>${x.document_id ? docLink(x.document_id, x.document_title) : ""}</td>
      <td class="r mono" style="white-space:nowrap">${(x.latency_ms / 1000).toLocaleString(locale(), { maximumFractionDigits: 1 })} s</td><td class="r mono">${x.input_tokens ?? "—"} / ${x.output_tokens ?? "—"}</td></tr>`).join("")}</tbody></table></div>`;
}

// ---------- SUBIR ----------
async function viewSubir() {
  await summary();
  renderShell("subir");
  const on = state.config.ai_connected;
  $("#view").innerHTML = `${pageHead(t("up_title"), t("up_sub"))}
    <label class="drop" id="drop"><input type="file" id="files" accept="image/*,application/pdf" multiple hidden ${on ? "" : "disabled"}>${ic("camera")}
      <span class="btn primary">${t("up_btn")}</span><span class="small muted">${on ? t("up_types") : t("ai_off")}</span></label>
    <div class="sec" id="up-sec" hidden><div class="sec-h"><span class="lbl">${t("files")}</span></div><div id="up-list"></div></div>`;
  const drop = $("#drop");
  ["dragover", "dragenter"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.style.borderColor = "var(--brand)"; }));
  drop.addEventListener("dragleave", () => { drop.style.borderColor = ""; });
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.style.borderColor = ""; if (on) uploadFiles(e.dataTransfer.files); });
}

async function uploadFiles(files) {
  $("#up-sec").hidden = false;
  const list = $("#up-list");
  const queue = [...files].map((f) => {
    const row = document.createElement("div");
    row.className = "up-row";
    row.innerHTML = `<b>${esc(f.name)}</b><span class="meta"><span class="spin"></span> ${t("reading")}</span>`;
    list.prepend(row);
    return { f, row };
  });
  const worker = async () => {
    while (queue.length) {
      const { f, row } = queue.shift();
      const t0 = performance.now();
      const fd = new FormData();
      fd.append("file", f);
      try {
        const res = await fetch(C("/documents"), { method: "POST", body: fd });
        const d = await res.json();
        if (!res.ok) throw new Error(d.detail || res.status);
        const counts = Object.entries(d.linked).filter(([, v]) => v.length).map(([k, v]) => `${v.length} ${t("lk_" + k)}`).join(" · ");
        const al = d.linked.findings.filter((x) => x.severity !== "info");
        row.innerHTML = `<div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><button class="linkish" data-doc="${d.id}" style="font-size:15px;font-weight:600;color:var(--ink)">${esc(d.title)}</button><span class="tag">${t("dt_" + d.doc_type)}</span></div>
          <span class="meta">${counts || "—"}</span><span class="small muted">${esc(d.extracted?._model || "")} · ${((performance.now() - t0) / 1000).toFixed(0)} s</span>
          ${al.map((x) => `<span class="small" style="color:${x.severity === "critical" ? "var(--crit)" : "var(--warn)"}">${esc(x.detail)}</span>`).join("")}`;
      } catch (err) {
        row.innerHTML = `<b>${esc(f.name)}</b><span class="small" style="color:var(--crit)">${t("read_error")}: ${esc(err.message)}</span>`;
      }
    }
  };
  await Promise.all([worker(), worker()]);
  state.summary = null;
}

// ---------- sheets ----------
function openSheet(title, body) {
  $("#sheet").innerHTML = `<div class="sheet-h"><h2>${title}</h2><button class="btn icon" data-close aria-label="${t("close")}">${ic("x")}</button></div>${body}`;
  $("#modal").hidden = false;
}

async function openDoc(id) {
  const d = await api(`/api/documents/${id}`);
  const x = d.extracted || {};
  const img = /\.(jpe?g|png|webp)$/i.test(d.file_path || "");
  const fields = [["f_issuer", d.issuer], ["f_doctor", x.doctor?.name && `${x.doctor.name}${x.doctor.specialty ? " · " + x.doctor.specialty : ""}`],
    ["f_billed", x.billed_to && `${x.billed_to}${x.billed_to_nit ? " · NIT " + x.billed_to_nit : ""}`], ["f_total", x.total != null && money(x.total, 2)], ["f_diag", x.diagnosis_text]].filter(([, v]) => v);
  const linked = Object.entries(d.linked).filter(([k, v]) => v.length && !["questions", "findings"].includes(k));
  const label = (k, r) => esc(r.name || r.title || r.text || r.vendor || r.detail || "") + (r.amount != null ? ` · ${money(r.amount, 2)}` : r.dose ? ` · ${r.dose}` : r.date ? ` · ${fdate(r.date)}` : "");
  openSheet(esc(d.title), `<div class="docview">
    <div>${img ? `<img src="/api/documents/${id}/file" alt="${esc(d.title)}">` : d.file_path ? `<a class="btn" href="/api/documents/${id}/file" target="_blank">PDF</a>` : ""}</div>
    <div style="display:grid;gap:14px;align-content:start">
      <div><span class="tag">${t("dt_" + d.doc_type)}</span> <span class="mono small muted">${fdate(d.doc_date)}</span></div>
      <dl class="kv">${fields.map(([k, v]) => `<dt>${t(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
      ${d.linked.findings.filter((f) => f.status === "open").map((f) => `<div class="callout ${f.severity === "critical" ? "crit" : ""}" style="margin:0">${sevTag(f.severity)} ${esc(f.detail)}</div>`).join("")}
      ${questionsHtml(d.linked.questions)}
      ${linked.length ? `<div class="sec-h"><span class="lbl">${t("extracted")}</span></div><div class="list">${linked.map(([k, v]) => v.map((r) => `<div class="row"><div>${label(k, r)}</div><span class="tag plain">${t("lk_" + k)}</span></div>`).join("")).join("")}</div>` : ""}
      ${x._model ? `<span class="small muted">${t("read_by", { m: esc(x._model) })}</span>` : ""}
      ${d.file_path ? `<div><button class="btn" data-sharedoc="${id}" data-title="${esc(d.title)}">${ic("share")} ${t("share")}</button></div>` : ""}
    </div></div>`);
}

async function shareUrl(url, name, type) {
  try {
    const blob = await (await fetch(url)).blob();
    const file = new File([blob], name, { type: type || blob.type });
    if (navigator.canShare?.({ files: [file] })) return await navigator.share({ files: [file], title: name });
    window.open(url, "_blank");
  } catch (err) { console.warn(err); }
}

async function openCases() {
  state.cases = await api("/api/cases");
  openSheet(t("cases"), `<button class="btn primary" data-open="newcase" style="justify-self:start">${ic("plus")} ${t("new_case")}</button><div class="list">${state.cases.map((c) => `<div class="row" data-case="${c.id}" style="cursor:pointer"><div><b>${esc(c.title)}</b><span class="s">${esc(c.summary || "")}</span></div>${c.id === state.caseId ? ic("check") : ""}</div>`).join("")}</div>`);
}

function openMenu() {
  const dark = document.documentElement.dataset.theme === "dark";
  const s = state.summary;
  const who = s?.members?.length ? `<label class="who"><span class="lbl">${t("who_am_i")}</span><select class="sel" data-member><option value="">—</option>${s.members.map((m) => `<option value="${m.id}" ${m.id === state.member ? "selected" : ""}>${esc(m.name)}</option>`).join("")}</select></label>` : "";
  openSheet(t("sections"), `${who}${NAV.map(([g, items]) => `<div class="sec"><span class="lbl">${t(g)}</span><div class="list">${items.map(([r, i]) => `<a class="row" href="#${r}" data-close style="text-decoration:none"><span style="display:flex;gap:10px;align-items:center">${ic(i)} ${t("nav_" + r)}</span></a>`).join("")}</div></div>`).join("")}
    <div style="display:flex;gap:8px"><select class="sel" data-lang>${["es", "en", "it"].map((l) => `<option value="${l}" ${l === state.lang ? "selected" : ""}>${l.toUpperCase()}</option>`).join("")}</select>
    <button class="btn" data-theme-toggle>${ic(dark ? "sun" : "moon")} ${t(dark ? "day" : "night")}</button></div>${palSel()}`);
}

async function openEmergency() {
  const cs = await api(C("/contacts"));
  const em = cs.filter((c) => c.group === "emergency"), docs = cs.filter((c) => c.group === "doctor" && c.phones.length).slice(0, 4);
  openSheet(t("emergency"), `${em.length ? em.map((c) => contactRow(c, true)).join("") : `<div class="callout crit" style="margin:0">${t("no_emergency")} <button class="linkish" data-open="addcontact">${t("add_contact")} →</button></div>`}
    ${docs.length ? `<div class="sec-h"><span class="lbl">${t("ct_doctor")}</span></div>${docs.map((c) => contactRow(c)).join("")}` : ""}`);
}

function openAddMed() {
  openSheet(t("add_med"), `<form id="med-form" style="display:grid;gap:12px;max-width:520px">
    <input class="input" name="name" placeholder="${t("med_name")}" required>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input class="input" name="dose" placeholder="${t("med_dose")}"><input class="input" name="every_hours" type="number" min="1" max="72" placeholder="${t("med_every")}"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px"><label class="small muted">${t("med_first")}<input class="input" name="first_time" type="time" value="08:00"></label>
      <label class="small muted">${t("med_start")}<input class="input" name="start_date" type="date" value="${state.day}"></label>
      <label class="small muted">${t("med_days")}<input class="input" name="days" type="number" min="1" placeholder="30"></label></div>
    <input class="input" name="instructions" placeholder="${t("med_ins")}">
    <div><button class="btn primary">${t("save")}</button></div></form>`);
}

function openNewCase() {
  openSheet(t("new_case"), `<form id="case-form" style="display:grid;gap:12px;max-width:520px">
    <label class="fld"><span class="lbl">${t("nc_title")}</span><input class="input" name="title" placeholder="${t("nc_title_ph")}" required maxlength="80"></label>
    <label class="fld"><span class="lbl">${t("nc_subject")}</span><input class="input" name="subject_name" placeholder="${t("nc_subject_ph")}" maxlength="80"></label>
    <label class="fld"><span class="lbl">${t("nc_kind")}</span><select class="sel" name="subject_kind"><option value="person">${t("nc_person")}</option><option value="pet">${t("nc_pet")}</option></select></label>
    <label class="fld"><span class="lbl">${t("nc_members")}</span><input class="input" name="members" placeholder="${t("nc_members_ph")}"></label>
    <label class="fld"><span class="lbl">${t("nc_summary")}</span><input class="input" name="summary" placeholder="${t("nc_summary_ph")}" maxlength="300"></label>
    <div><button class="btn primary">${t("nc_create")}</button></div></form>`);
}

function openAddContact() {
  openSheet(t("add_contact"), `<form id="ct-form" style="display:grid;gap:12px;max-width:480px">
    <input class="input" name="name" placeholder="${t("name")}" required><input class="input" name="role" placeholder="${t("role")}">
    <input class="input" name="phone" placeholder="${t("phone")}" inputmode="tel"><label style="display:flex;gap:8px;align-items:center"><input type="checkbox" name="is_emergency"> ${t("is_emergency")}</label>
    <div><button class="btn primary">${t("save")}</button></div></form>`);
}

// ---------- read aloud, visit summary, reminders ----------
function speakDay() {
  if (!("speechSynthesis" in window)) return toast(t("no_voice"));
  if (speechSynthesis.speaking) { speechSynthesis.cancel(); return; }
  const s = state.summary, hm = nowHM();
  const parts = [`${wd(state.day, "long")} ${D(state.day).toLocaleDateString(locale(), { day: "numeric", month: "long" })}.`];
  const pend = s.doses.filter((d) => !d.taken);
  if (pend.length) parts.push(t("sp_doses", { n: pend.length }) + " " + pend.map((d) => `${d.name} ${d.dose || ""}, ${t("sp_at")} ${d.time}${d.time < hm && state.day === state.config.today ? ", " + t("late").toLowerCase() : ""}`).join(". ") + ".");
  else parts.push(t("sp_no_doses"));
  if (s.events.length) parts.push(t("sp_events") + " " + s.events.map((e) => (e.time ? e.time + ", " : "") + e.title).join(". ") + ".");
  if (s.next_events[0]) parts.push(t("sp_next", { d: D(s.next_events[0].date).toLocaleDateString(locale(), { day: "numeric", month: "long" }), x: s.next_events[0].title }));
  const ins = s.instructions.slice(0, 4).map((i) => `${t(i.polarity === "avoid" ? "avoid" : "do")}: ${i.text}`);
  if (ins.length) parts.push(t("sp_ins") + " " + ins.join(". ") + ".");
  const u = new SpeechSynthesisUtterance(parts.join(" "));
  u.lang = { es: "es-ES", en: "en-US", it: "it-IT" }[state.lang];
  const v = speechSynthesis.getVoices().find((x) => x.lang.startsWith(state.lang));
  if (v) u.voice = v;
  u.rate = 0.95;
  speechSynthesis.speak(u);
}

async function buildVisit() {
  const out = $("#visit-out");
  out.innerHTML = `<div class="callout" style="margin:0"><span class="spin"></span> ${t("building")}</div>`;
  try {
    const r = await send(C("/packages/visit"), "POST");
    out.innerHTML = `<div class="callout" style="margin:0;border-color:var(--brand);background:var(--brand-weak)"><b>${t("visit_ready")}</b>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px"><a class="btn primary sm" href="${r.url}" target="_blank">${t("open_pdf")}</a><button class="btn sm" data-sharepdf="${r.url}">${ic("share")} ${t("share")}</button></div></div>`;
  } catch (err) { out.innerHTML = `<div class="callout crit" style="margin:0">${esc(err.message)}</div>`; }
}

state.timers = [];
async function toggleReminders() {
  if (!("Notification" in window)) return toast(t("no_notif"));
  if (state.timers.length) { state.timers.forEach(clearTimeout); state.timers = []; return toast(t("rem_off")); }
  const perm = await Notification.requestPermission();
  if (perm !== "granted") return toast(t("no_notif"));
  const s = await summary(true), now = clock();
  const reg = await navigator.serviceWorker?.getRegistration?.();
  const show = (title, body) => (reg ? reg.showNotification(title, { body, icon: "/icon.svg", tag: title }) : new Notification(title, { body }));
  s.doses.filter((d) => !d.taken).forEach((d) => {
    const at = new Date(`${isoOf(now)}T${d.time}:00`);
    if (at > now) state.timers.push(setTimeout(() => show(`${d.name} ${d.dose || ""}`.trim(), t("rem_body", { t: d.time })), at - now));
  });
  s.events.filter((e) => e.time).forEach((e) => {
    const at = new Date(`${isoOf(now)}T${e.time}:00`); at.setMinutes(at.getMinutes() - 60);
    if (at > now) state.timers.push(setTimeout(() => show(e.title, t("rem_event", { t: e.time })), at - now));
  });
  show("Dindo", t("rem_on", { n: state.timers.length }));
}

// ---------- actions ----------
async function build(kind) {
  const out = $("#pkg-out");
  out.innerHTML = `<span class="small muted"><span class="spin"></span> ${t("building")}</span>`;
  try {
    const r = await send(C(`/packages/${kind}`), "POST");
    out.innerHTML = `<div style="display:grid;gap:8px"><span class="small"><b>${t("pdf_ready", { n: r.pages })}</b></span><div style="display:flex;gap:8px;flex-wrap:wrap">
      <a class="btn primary sm" href="${r.url}" target="_blank">${t("open_pdf")}</a><button class="btn sm" data-sharepdf="${r.url}">${ic("share")} ${t("share")}</button>
      ${kind === "insurance" ? `<button class="btn sm" data-marksent>${t("mark_sent")}</button>` : ""}</div></div>`;
  } catch (err) {
    out.innerHTML = `<span class="small" style="color:var(--crit)">${esc(err.message)}</span>`;
  }
}

function exportCsv() {
  api(C("/expenses")).then((e) => {
    const rows = [["fecha", "proveedor", "detalle", "categoria", "monto_bs", "factura", "reembolsable", "estado", "pago"]].concat(
      e.items.map((i) => [i.date, i.vendor || "", (i.description || "").replace(/\s+/g, " "), i.category, i.amount, i.invoice_number || "", i.reimbursable ? "si" : "no", i.claim_status, i.paid_by_name || ""]));
    const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv" })), download: "gastos-dindo.csv" });
    a.click();
  });
}

async function answerQ(qid, value) {
  await send(`/api/questions/${qid}/answer`, "POST", { answer: value });
  document.querySelectorAll(`[data-q="${qid}"]`).forEach((el) => { el.outerHTML = `<div class="q-item"><b>✓ ${esc(value)}</b></div>`; });
  state.summary = null;
}

document.addEventListener("click", async (ev) => {
  if (ev.target.closest("select, input, textarea")) return;  // form controls inside clickable rows
  const cl = ev.target.closest("[data-claimset],[data-claimall]");
  if (cl) {
    const ids = cl.dataset.claimset ? [cl.dataset.claimset.split("|")[0]] : cl.dataset.claimall.split(",");
    for (const id of ids) await send(`/api/expenses/${id}`, "PATCH", { claim_status: "submitted" });
    state.summary = null;
    toast("✓");
    return route();
  }
  const evo = ev.target.closest("[data-evofilter],[data-evo-ai]");
  if (evo) {
    if (evo.dataset.evofilter) { state.evoFilter = evo.dataset.evofilter; return route(); }
    const out = $("#evo-ai");
    out.innerHTML = `<div class="chat"><div class="a"><span class="spin"></span> ${t("thinking")}</div></div>`;
    try { const r = await send(C("/ask"), "POST", { question: t("evo_prompt"), lang: state.lang }); out.innerHTML = `<div class="chat"><div class="a">${renderAnswer(r.answer)}</div></div>`; }
    catch (err) { out.innerHTML = `<div class="callout crit">${esc(err.message)}</div>`; }
    return;
  }
  const extra = ev.target.closest("[data-suggest],[data-speak],[data-build-visit],[data-reminders]");
  if (extra) {
    if (extra.dataset.suggest) { $("#case-q").value = extra.dataset.suggest; return $("#case-ask").requestSubmit(); }
    if (extra.dataset.speak !== undefined) return speakDay();
    if (extra.dataset.buildVisit !== undefined) return buildVisit();
    if (extra.dataset.reminders !== undefined) return toggleReminders();
  }
  const el = ev.target.closest("[data-dose],[data-doc],[data-status],[data-case],[data-open],[data-close],[data-day],[data-calday],[data-calmode],[data-calnav],[data-openday],[data-txnav],[data-expcat],[data-expperiod],[data-export],[data-doctype],[data-copy],[data-build],[data-sharepdf],[data-sharedoc],[data-marksent],[data-answer],[data-showinfo],[data-theme-toggle]");
  if (!el) { if (ev.target.id === "modal") $("#modal").hidden = true; return; }
  const ds = el.dataset;
  if (ds.close !== undefined) { $("#modal").hidden = true; return; }
  if (ds.open) return ({ cases: openCases, newcase: openNewCase, menu: openMenu, emergency: openEmergency, addcontact: openAddContact, addmed: openAddMed }[ds.open])();
  if (ds.themeToggle !== undefined) {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("dindo.theme", next); const v = localStorage.getItem("dindo.pal." + next); document.documentElement.dataset.pal = v === null ? (next === "dark" ? "corp" : "verde") : v; } catch (_) {}
    $("#modal").hidden = true;
    return route();
  }
  if (ds.case) {
    state.caseId = Number(ds.case);
    try { localStorage.setItem("dindo.case", state.caseId); } catch (_) {}
    Object.assign(state, { summary: null, calSel: null, calMonth: null, expCat: null, docType: null });
    $("#modal").hidden = true;
    return route();
  }
  if (ds.dose) {
    ev.stopPropagation();
    const [med, at, taken] = ds.dose.split("|");
    if (taken === "1") await api(`/api/medications/${med}/doses?scheduled_at=${encodeURIComponent(at)}`, { method: "DELETE" });
    else await send(`/api/medications/${med}/doses`, "POST", { scheduled_at: at, member_id: state.member });
    state.summary = null;
    return route();
  }
  if (ds.doc) { if (ev.target.closest("select")) return; return openDoc(ds.doc); }
  if (ds.status) {
    const [table, id, status] = ds.status.split("|");
    await send(`/api/${table}/${id}`, "PATCH", { status });
    state.summary = null;
    return route();
  }
  if (ds.day !== undefined) { state.day = ds.day === "0" ? state.config.today : addDays(state.day, Number(ds.day)); return route(); }
  if (ds.calday) { state.calSel = ds.calday; if (ds.calday.slice(0, 7) !== state.calMonth) state.calMonth = ds.calday.slice(0, 7); return route(); }
  if (ds.calmode) { state.calMode = ds.calmode; return route(); }
  if (ds.calnav) {
    if (state.calMode === "week") { state.calSel = addDays(state.calSel, 7 * Number(ds.calnav)); state.calMonth = state.calSel.slice(0, 7); }
    else { const d = D(state.calMonth + "-01"); d.setMonth(d.getMonth() + Number(ds.calnav)); state.calMonth = isoOf(d).slice(0, 7); state.calSel = state.calMonth + "-01"; }
    return route();
  }
  if (ds.openday) { state.day = ds.openday; location.hash = "#hoy"; return; }
  if (ds.txnav) { state.txStart = ds.txnav === "0" ? addDays(state.day, -6) : addDays(state.txStart, Number(ds.txnav)); return route(); }
  if (ds.expcat !== undefined) { state.expCat = ds.expcat && ds.expcat !== state.expCat ? ds.expcat : null; return route(); }
  if (ds.expperiod) { state.expPeriod = ds.expperiod; return route(); }
  if (ds.export !== undefined) return exportCsv();
  if (ds.doctype !== undefined) { state.docType = ds.doctype || null; return route(); }
  if (ds.copy) {
    try { await navigator.clipboard.writeText(ds.copy); toast(t("copied")); } catch (_) { toast(ds.copy); }
    return;
  }
  if (ds.build) return build(ds.build);
  if (ds.sharepdf) return shareUrl(ds.sharepdf, ds.sharepdf.split("/").pop(), "application/pdf");
  if (ds.sharedoc) return shareUrl(`/api/documents/${ds.sharedoc}/file`, ds.title + ".jpg");
  if (ds.marksent !== undefined) { await send(C("/packages/insurance/submitted"), "POST"); state.summary = null; return route(); }
  if (ds.answer) return answerQ(ds.answer, ds.value);
  if (ds.showinfo !== undefined) { state.showInfo = !state.showInfo; return route(); }
});

document.addEventListener("change", async (e) => {
  if (e.target.id === "files" && e.target.files.length) { await uploadFiles(e.target.files); e.target.value = ""; return; }
  if (e.target.dataset.pal !== undefined) { setPal(e.target.value); $("#modal").hidden = true; return route(); }
  if (e.target.dataset.lang !== undefined) {
    state.lang = e.target.value;
    try { localStorage.setItem("dindo.lang", state.lang); } catch (_) {}
    $("#modal").hidden = true;
    return route();
  }
  if (e.target.dataset.member !== undefined) {
    state.member = Number(e.target.value) || null;
    try { localStorage.setItem("dindo.member", state.member || ""); } catch (_) {}
    toast("✓");
    return;
  }
  if (e.target.dataset.claim) {
    await send(`/api/expenses/${e.target.dataset.claim}`, "PATCH", { claim_status: e.target.value });
    state.summary = null;
    toast("✓");
    return route();
  }
  if (e.target.dataset.paid) {
    await send(`/api/expenses/${e.target.dataset.paid}`, "PATCH", { paid_by: e.target.value ? Number(e.target.value) : null });
    toast("✓");
    return route();
  }
});

document.addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  if (f.dataset.answerForm) { const v = f.querySelector("input").value.trim(); if (v) answerQ(f.dataset.answerForm, v); return; }
  if (f.id === "case-form") {
    const c = await send("/api/cases", "POST", Object.fromEntries(new FormData(f)));
    state.cases = await api("/api/cases");
    state.caseId = c.id;
    try { localStorage.setItem("dindo.case", c.id); } catch (_) {}
    Object.assign(state, { summary: null, calSel: null, calMonth: null, expCat: null, docType: null, member: null });
    $("#modal").hidden = true;
    toast(t("nc_done"));
    location.hash = "#subir";
    return route();
  }
  if (f.id === "ct-form") {
    const data = Object.fromEntries(new FormData(f));
    data.is_emergency = !!f.is_emergency.checked;
    await send(C("/contacts"), "POST", data);
    $("#modal").hidden = true;
    return route();
  }
  if (f.id === "case-ask") {
    const q = $("#case-q").value.trim();
    if (!q) return;
    $("#case-log").insertAdjacentHTML("afterbegin", `<div class="a" id="pending"><span class="spin"></span> ${t("thinking")}</div><div class="q">${esc(q)}</div>`);
    $("#case-q").value = "";
    try { const r = await send(C("/ask"), "POST", { question: q, lang: state.lang }); $("#pending").innerHTML = renderAnswer(r.answer); }
    catch (err) { $("#pending").textContent = `${t("read_error")}: ${err.message}`; }
    $("#pending").removeAttribute("id");
    return;
  }
  if (f.id === "med-form") {
    await send(C("/medications"), "POST", Object.fromEntries(new FormData(f)));
    $("#modal").hidden = true;
    state.summary = null;
    return route();
  }
  if (f.id === "ask-form") {
    const q = $("#ask-q").value.trim();
    if (!q) return;
    const log = $("#ask-log");
    log.insertAdjacentHTML("beforeend", `<div class="q">${esc(q)}</div><div class="a" id="pending"><span class="spin"></span> ${t("thinking")}</div>`);
    $("#ask-q").value = "";
    try {
      const r = await send(C("/ask"), "POST", { question: q, lang: state.lang });
      $("#pending").innerHTML = renderAnswer(r.answer);
    } catch (err) { $("#pending").textContent = `${t("read_error")}: ${err.message}`; }
    $("#pending").removeAttribute("id");
  }
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("#modal").hidden = true; });

// ---------- router ----------
const VIEWS = { hoy: viewHoy, calendario: viewCalendario, tratamiento: viewTratamiento, indicaciones: viewIndicaciones, gastos: viewGastos,
  seguro: viewSeguro, cotizaciones: viewCotizaciones, diagnosticos: viewDiagnosticos, examenes: viewExamenes, documentos: viewDocumentos, contactos: viewContactos, juicio: viewJuicio, alertas: viewAlertas, preguntas: viewPreguntas, capo: viewCapo, subir: viewSubir, preguntar: viewPreguntar, evolucion: viewEvolucion };

async function route() {
  const r = location.hash.slice(1) || "hoy";
  try {
    await (VIEWS[r] || viewHoy)();
    window.scrollTo(0, 0);
  } catch (err) {
    console.error(err);
    $("#view").innerHTML = `<div class="callout crit">${esc(err.message)}</div>`;
  }
}

window.addEventListener("hashchange", () => { $("#modal").hidden = true; route(); });
(async () => {
  state.config = await api("/api/config");
  if (state.config.now) { const [h, m] = state.config.now.split(":").map(Number), d = new Date(); clockOffset = ((h * 60 + m) - (d.getHours() * 60 + d.getMinutes())) * 60000; }
  state.cases = await api("/api/cases");
  if (!state.cases.some((c) => c.id === state.caseId)) state.caseId = state.cases[0]?.id || 1;
  state.day = state.config.today;
  await route();
  if (new URLSearchParams(location.search).get("open") === "menu") openMenu();  // deep link to the phone menu
  try { navigator.serviceWorker?.register("/sw.js"); } catch (_) {}
})();
