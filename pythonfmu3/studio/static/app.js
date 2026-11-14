"use strict";
/* PythonFMU3 Studio front end: plain JavaScript, no dependencies. */

const TOKEN = new URLSearchParams(location.search).get("token") || "";
const $ = (sel) => document.querySelector(sel);

const S = {
  env: null,
  files: [],
  path: null,          // workspace-relative path of the open .py file
  saved: "",           // last saved content
  analysis: null,
  preview: "fmu",
  view: "editor",
  sim: { simulator: "python", values: {}, result: null, selected: null, running: false, pending: false },
  templates: [],
  tplCat: "all",
};

/* ---------- helpers ---------- */

function el(tag, props, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "dataset") Object.assign(node.dataset, v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

const SVGNS = "http://www.w3.org/2000/svg";
function svg(tag, attrs, ...children) {
  const node = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
  for (const c of children.flat()) if (c) node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return node;
}

async function api(path, { method = "GET", body, raw, query } = {}) {
  const url = new URL("/api/" + path, location.origin);
  for (const [k, v] of Object.entries(query || {})) url.searchParams.set(k, v);
  const headers = { "X-Studio-Token": TOKEN };
  let payload;
  if (raw !== undefined) { payload = raw; headers["Content-Type"] = "application/octet-stream"; }
  else if (body !== undefined) { payload = JSON.stringify(body); headers["Content-Type"] = "application/json"; }
  const res = await fetch(url, { method, headers, body: payload });
  let data;
  try { data = await res.json(); } catch { data = { ok: false, error: `HTTP ${res.status}` }; }
  return data;
}

function banner(kind, message, detail, extra) {
  const b = $("#banner");
  b.className = "banner " + kind;
  b.replaceChildren(...[el("strong", { text: message }), extra, detail ? el("pre", { text: detail }) : null,
    el("button", { type: "button", class: "btn push", onClick: () => (b.hidden = true) }, "Dismiss")].filter(Boolean));
  b.hidden = false;
}

function busy(button, on) {
  if (!button) return;
  button.disabled = on;
  if (on) { button.dataset.label = button.textContent; button.textContent = "Working…"; }
  else if (button.dataset.label) button.textContent = button.dataset.label;
}

const fmt = (x) => {
  if (x === null || x === undefined || Number.isNaN(x)) return "–";
  if (typeof x !== "number") return String(x);
  if (x === 0) return "0";
  const a = Math.abs(x);
  return a >= 1e5 || a < 1e-3 ? x.toExponential(3) : Number(x.toPrecision(5)).toString();
};

/* ---------- navigation ---------- */

function show(view) {
  S.view = view;
  for (const b of document.querySelectorAll(".tab")) {
    if (b.dataset.view === view) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
  }
  for (const v of ["editor", "simulate", "inspector", "templates"]) $("#view-" + v).hidden = v !== view;
  if (view === "simulate") renderSimSettings();
  if (view === "templates" && !S.templates.length) loadTemplates();
  if (view === "inspector") refreshFmuSelect();
}

/* ---------- files and editor ---------- */

async function loadFiles(select) {
  const r = await api("files");
  if (!r.ok) return banner("error", r.error);
  S.files = r.result;
  const sel = $("#file-select");
  const py = S.files.filter((f) => f.kind === "py");
  sel.replaceChildren(...(py.length ? py.map((f) => el("option", { value: f.path, text: f.path })) :
    [el("option", { value: "", text: "No .py files – use a template" })]));
  const target = select || S.path || (py[0] && py[0].path);
  if (target) { sel.value = target; if (target !== S.path) await openFile(target); }
  else if (!py.length) show("templates");
}

async function openFile(path) {
  if (S.path && dirty() && !confirm(`Discard unsaved changes to ${S.path}?`)) { $("#file-select").value = S.path; return; }
  const r = await api("file", { query: { path } });
  if (!r.ok) return banner("error", r.error);
  S.path = r.result.path;
  S.saved = r.result.content;
  $("#code").value = r.result.content;
  $("#code-name").textContent = S.path;
  S.sim.values = {}; S.sim.result = null; S.sim.selected = null;
  updateGutter(); updateDirty();
  await analyze();
}

const dirty = () => S.path && $("#code").value !== S.saved;
function updateDirty() { $("#dirty").hidden = !dirty(); }
function updateGutter() {
  const n = $("#code").value.split("\n").length;
  $("#gutter").textContent = Array.from({ length: n }, (_, i) => i + 1).join("\n");
}

async function save() {
  if (!S.path) return;
  const content = $("#code").value;
  const r = await api("file", { method: "POST", body: { path: S.path, content } });
  if (!r.ok) return banner("error", "Could not save", r.error);
  S.saved = content; updateDirty();
  await analyze();
}

async function analyze() {
  if (!S.path) return;
  const r = await api("analyze", { method: "POST", body: { path: S.path } });
  if (!r.ok) {
    S.analysis = null;
    renderAnalysis(r);
    return;
  }
  S.analysis = r.result;
  $("#banner").hidden = true;
  renderAnalysis();
}

/* ---------- analysis rendering ---------- */

function renderAnalysis(failure) {
  const a = S.analysis;
  const block = $("#preview-fmu"), xml = $("#preview-xml"), checks = $("#preview-checks"), table = $("#var-table");
  if (!a) {
    const msg = failure ? failure.error : "Open or create a model to see it here.";
    block.replaceChildren(el("div", { class: "empty" }, msg));
    xml.textContent = "";
    checks.replaceChildren(el("div", { class: "check-item error" }, el("strong", { text: "ERROR" }),
      el("div", {}, el("div", { class: "title", text: "The model could not be loaded" }),
        el("pre", { class: "mono", style: "white-space:pre-wrap;margin:6px 0 0", text: failure ? (failure.traceback || failure.error) : "" }))));
    table.replaceChildren();
    setBadge(1);
    return;
  }
  const vars = a.variables;
  const label = (v) => v.name + (v.size && v.size > 1 ? `[${v.size}]` : "") + (v.unit ? ` [${v.unit}]` : "");
  const params = vars.filter((v) => ["parameter", "structuralParameter"].includes(v.causality));
  const inputs = vars.filter((v) => v.causality === "input");
  const outputs = vars.filter((v) => v.causality === "output");
  const ifaceText = a.interfaces.map((i) => (i === "cs" ? "Co-Simulation" : "Model Exchange")).join(" + ");
  block.replaceChildren(el("div", { class: "block-wrap" },
    el("div", { class: "chips" }, params.map((p) => el("span", { class: "chip-param", text: `${p.name} = ${fmt(p.start ?? p.value)}` }))),
    el("div", { class: "block-row" },
      el("div", { class: "ports in" }, inputs.map((p) => el("div", { class: "port" }, el("span", { text: label(p), title: label(p) }), el("i")))),
      el("div", { class: "block" }, blockIcon(), el("b", { text: a.modelName }), el("small", { text: ifaceText || "no interface" })),
      el("div", { class: "ports out" }, outputs.map((p) => el("div", { class: "port" }, el("i"), el("span", { text: label(p), title: label(p) }))))),
    el("p", { class: "muted small", style: "text-align:center;max-width:380px;margin:0" },
      `${vars.length} variables · ${inputs.length} inputs · ${outputs.length} outputs · ${params.length} parameters` +
      (a.eventIndicators ? ` · ${a.eventIndicators} event indicator(s)` : ""))));
  xml.textContent = a.xml;

  const issues = a.checks.filter((c) => c.level !== "ok");
  checks.replaceChildren(...a.checks.map((c) => el("div", { class: "check-item " + c.level },
    el("strong", { text: { ok: "PASS", warning: "WARN", error: "ERROR" }[c.level] }),
    el("div", {}, el("div", { class: "title", text: c.title }), el("div", { text: c.detail })))));
  setBadge(issues.length);

  const byVar = {};
  for (const c of issues) if (c.variable) (byVar[c.variable] = byVar[c.variable] || []).push(c);
  table.replaceChildren(
    el("thead", {}, el("tr", {}, ["VR", "Name", "Type", "Causality", "Variability", "Initial", "Unit", "Start / value", "Check"].map((h) => el("th", { scope: "col", text: h })))),
    el("tbody", {}, vars.map((v) => el("tr", {},
      el("td", { class: "mono muted", text: v.vr }),
      el("td", { class: "mono", text: v.name + (v.dims.length ? ` [${v.dims.join(", ")}]` : "") }),
      el("td", {}, el("span", { class: "pill", text: v.type })),
      el("td", {}, el("span", { class: "pill caus-" + v.causality, text: v.causality })),
      el("td", { text: v.variability || "(default)" }),
      el("td", { class: "muted", text: v.initial || "–" }),
      el("td", { text: v.unit || "–" }),
      el("td", { class: "mono", text: short(v.start ?? v.value) }),
      el("td", {}, (byVar[v.name] || []).length
        ? (byVar[v.name]).map((c) => el("span", { class: "flag " + c.level, title: c.detail, text: c.title.replace(v.name + ": ", "") }))
        : el("span", { class: "flag ok", text: "OK" }))))));
}

function short(value) {
  if (Array.isArray(value)) return value.length > 6 ? `[${value.slice(0, 6).map(fmt).join(", ")}, …] (${value.length})` : `[${value.map(fmt).join(", ")}]`;
  return fmt(value);
}

function setBadge(n) {
  const b = $("#issue-badge");
  b.textContent = String(n);
  b.classList.toggle("bad", n > 0);
}

function blockIcon() {
  return svg("svg", { width: "56", height: "34", viewBox: "14 18 36 28", "aria-hidden": "true" },
    svg("path", { d: "M17 42 L22 42 C27 42 28 21.5 33.5 21 C38 20.6 39 26.5 43 25.6 L47 25", fill: "none", stroke: "#fff", "stroke-width": "3.2", "stroke-linecap": "round", "stroke-linejoin": "round" }));
}

function setPreview(tab) {
  S.preview = tab;
  for (const b of document.querySelectorAll(".subtab")) b.setAttribute("aria-selected", String(b.dataset.preview === tab));
  $("#preview-fmu").hidden = tab !== "fmu";
  $("#preview-xml").hidden = tab !== "xml";
  $("#preview-checks").hidden = tab !== "checks";
}

/* ---------- build and validate ---------- */

async function build(button) {
  if (!S.path) return;
  if (dirty()) await save();
  busy(button, true);
  const r = await api("build", { method: "POST", body: { path: S.path } });
  busy(button, false);
  if (!r.ok) { banner("error", "Build failed", r.traceback || r.error); return null; }
  const res = r.result;
  const link = el("a", { class: "btn", href: `/api/download?path=${encodeURIComponent(res.fmu)}&token=${encodeURIComponent(TOKEN)}`, download: "" }, "Download");
  banner("ok", `Built ${res.fmu}`, null, el("span", {}, `${(res.size / 1024 / 1024).toFixed(2)} MB · ${res.platforms.join(", ") || "no binaries"}`, " ", link));
  return res;
}

async function validate(button) {
  busy(button, true);
  const built = await build(null);
  if (!built) { busy(button, false); return; }
  const r = await api("validate", { method: "POST", body: { fmu: built.fmu } });
  busy(button, false);
  if (!r.ok) return banner("error", "Validation failed to run", r.error);
  const v = r.result;
  banner(v.passed ? "ok" : "error", `${v.passed ? "Valid" : "Invalid"}: ${built.fmu} (${v.tool})`, v.output);
  setPreview("checks");
}

/* ---------- simulate ---------- */

function simulatorOptions() {
  const env = S.env || {};
  return [
    { id: "python", label: "Python preview", ok: true, note: "Runs your class directly (Co-Simulation: do_step; Model Exchange: RK4 with event location). Fast enough to re-run while you drag." },
    { id: "fmusim", label: "fmusim", ok: !!env.fmusim, note: env.fmusim ? "Builds the FMU and runs it in fmusim, a native (non-Python) importer." : "Install fmusim (github.com/modelica/fmusim) or set PYTHONFMU3_FMUSIM to enable." },
    { id: "fmpy", label: "FMPy", ok: !!env.fmpy, note: env.fmpy ? "Builds the FMU and runs it with FMPy." : "pip install fmpy to enable." },
  ];
}

function renderSimSettings() {
  const a = S.analysis;
  const opts = simulatorOptions();
  $("#sim-choice").replaceChildren(...opts.map((o) => el("button", {
    type: "button", class: "chip-btn", "aria-pressed": String(S.sim.simulator === o.id), disabled: !o.ok, title: o.note,
    onClick: () => { S.sim.simulator = o.id; renderSimSettings(); },
  }, o.label)));
  $("#sim-note").textContent = (opts.find((o) => o.id === S.sim.simulator) || opts[0]).note;

  const iface = $("#sim-interface");
  const ifs = a ? a.interfaces : [];
  const current = iface.value;
  iface.replaceChildren(...ifs.map((i) => el("option", { value: i, text: i === "cs" ? "Co-Simulation" : "Model Exchange" })));
  if (ifs.includes(current)) iface.value = current;
  if (a && a.defaultExperiment && !S.sim.defaultsApplied) {
    if (a.defaultExperiment.stopTime) $("#sim-stop").value = a.defaultExperiment.stopTime;
    if (a.defaultExperiment.stepSize) $("#sim-step").value = a.defaultExperiment.stepSize;
    S.sim.defaultsApplied = true;
  }

  const box = $("#sim-params");
  if (!a) { box.replaceChildren(el("p", { class: "muted", text: "Open a model in the editor first." })); return; }
  const tunable = a.variables.filter((v) => ["parameter", "input"].includes(v.causality) && v.variability !== "constant" &&
    ["Float64", "Int32", "Int64", "UInt64", "Boolean"].includes(v.type) && !(v.size > 1));
  if (!tunable.length) { box.replaceChildren(el("p", { class: "muted", text: "This model has no scalar parameters or inputs." })); return; }
  box.replaceChildren(...tunable.map((v) => paramControl(v)));
}

function paramControl(v) {
  const start = typeof v.start === "number" ? v.start : (typeof v.value === "number" ? v.value : (v.value === true ? 1 : 0));
  const value = S.sim.values[v.name] ?? start;
  const isInt = v.type !== "Float64";
  const span = Math.abs(start) > 0 ? Math.abs(start) : 1;
  const lo = v.type === "Boolean" ? 0 : (start >= 0 && v.type === "UInt64" ? 0 : start - 2 * span);
  const hi = v.type === "Boolean" ? 1 : start + 2 * span;
  const step = isInt ? 1 : span / 100;
  const id = "p-" + v.name.replace(/[^A-Za-z0-9_-]/g, "_");
  const num = el("input", { type: "number", id, value: String(value), step: isInt ? "1" : "any", "aria-label": v.name });
  const range = el("input", { type: "range", min: String(lo), max: String(hi), step: String(step), value: String(value), "aria-label": `${v.name} slider`, tabindex: "-1" });
  const set = (x, from) => {
    const val = isInt ? Math.round(Number(x)) : Number(x);
    if (!Number.isFinite(val)) return;
    S.sim.values[v.name] = val;
    if (from !== num) num.value = String(val);
    if (from !== range) range.value = String(val);
    if ($("#sim-live").checked && S.sim.simulator === "python") scheduleRun();
  };
  num.addEventListener("change", () => set(num.value, num));
  range.addEventListener("input", () => set(range.value, range));
  return el("div", { class: "param" },
    el("div", { class: "param-head" },
      el("label", { for: id, class: "mono", text: v.name }),
      el("span", { class: "muted small", text: `${v.causality}${v.unit ? " · " + v.unit : ""}` }), num),
    range);
}

let runTimer = null;
function scheduleRun() {
  clearTimeout(runTimer);
  runTimer = setTimeout(() => runSimulation(), 220);
}

async function runSimulation(button) {
  if (!S.path || !S.analysis) { banner("info", "Open a model first"); return; }
  if (S.sim.running) { S.sim.pending = true; return; }
  if (dirty()) await save();
  S.sim.running = true;
  busy(button, true);
  const body = {
    path: S.path, simulator: S.sim.simulator, interface: $("#sim-interface").value || undefined,
    stopTime: Number($("#sim-stop").value) || 10, stepSize: Number($("#sim-step").value) || 0.01,
    startValues: S.sim.values,
  };
  const r = await api("simulate", { method: "POST", body });
  busy(button, false);
  S.sim.running = false;
  if (!r.ok) {
    banner("error", "Simulation failed", r.traceback || r.error);
  } else {
    S.sim.result = r.result;
    S.sim.stdout = r.stdout;
    renderResults();
  }
  if (S.sim.pending) { S.sim.pending = false; runSimulation(); }
}

function renderResults() {
  const res = S.sim.result;
  if (!res) return;
  const names = Object.keys(res.series);
  if (!S.sim.selected || !S.sim.selected.some((n) => names.includes(n))) S.sim.selected = names.slice(0, 4);
  $("#sim-series").replaceChildren(...names.map((n) => {
    const box = el("input", { type: "checkbox" });
    box.checked = S.sim.selected.includes(n);
    box.addEventListener("change", () => {
      S.sim.selected = box.checked ? [...S.sim.selected, n] : S.sim.selected.filter((x) => x !== n);
      renderCharts();
    });
    return el("label", {}, box, n);
  }));
  const t = res.time;
  const stats = [
    ["Simulator", { python: "Python preview", fmusim: "fmusim", fmpy: "FMPy" }[res.simulator] || res.simulator],
    ["Points", String(t.length)],
    ["End time", fmt(t[t.length - 1]) + " s"],
    ["Events", String(res.events.length)],
  ];
  $("#sim-stats").replaceChildren(...stats.map(([k, v]) => el("div", { class: "stat" }, el("div", { class: "k", text: k }), el("div", { class: "v", text: v }))));
  const log = [S.sim.stdout, res.log].filter(Boolean).join("\n");
  $("#sim-log-wrap").hidden = !log;
  $("#sim-log").textContent = log;
  renderCharts();
}

function renderCharts() {
  const res = S.sim.result;
  const box = $("#sim-charts");
  if (!res) { box.replaceChildren(el("div", { class: "empty", text: "Press Run to simulate." })); return; }
  const unitOf = {};
  for (const v of (S.analysis ? S.analysis.variables : [])) unitOf[v.name] = v.unit;
  box.replaceChildren(...S.sim.selected.filter((n) => res.series[n]).map((n) => chart(n, unitOf[n.replace(/\[\d+\]$/, "")], res.time, res.series[n], res.events)));
}

function niceTicks(lo, hi, count) {
  if (!(hi > lo)) { hi = lo + 1; lo = lo - 1; }
  const raw = (hi - lo) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || 10 * mag;
  const start = Math.floor(lo / step) * step, end = Math.ceil(hi / step) * step;
  const ticks = [];
  for (let x = start; x <= end + step / 2; x += step) ticks.push(Number(x.toPrecision(12)));
  return ticks;
}

function chart(name, unit, t, y, events) {
  const W = 800, H = 230, L = 58, R = 12, T = 12, B = 30;
  const finite = y.filter((v) => v !== null && Number.isFinite(v));
  const yt = niceTicks(Math.min(...finite), Math.max(...finite), 4);
  const xt = niceTicks(t[0], t[t.length - 1], 6);
  const x0 = xt[0], x1 = xt[xt.length - 1], y0 = yt[0], y1 = yt[yt.length - 1];
  const X = (v) => L + ((v - x0) / (x1 - x0)) * (W - L - R);
  const Y = (v) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
  const pts = [];
  t.forEach((tv, i) => { if (y[i] !== null && Number.isFinite(y[i])) pts.push(`${X(tv).toFixed(1)},${Y(y[i]).toFixed(1)}`); });
  const readout = el("span", { class: "readout" });
  const dot = svg("circle", { r: "4", fill: "#E8B11C", stroke: "#1F2933", "stroke-width": "1", visibility: "hidden" });
  const plot = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${name} over time` },
    yt.map((v) => svg("line", { x1: L, x2: W - R, y1: Y(v), y2: Y(v), stroke: "#EEF1F5" })),
    yt.map((v) => svg("text", { x: L - 8, y: Y(v) + 4, "text-anchor": "end", "font-size": "11", fill: "#5B6673" }, fmt(v))),
    xt.map((v) => svg("text", { x: X(v), y: H - 10, "text-anchor": "middle", "font-size": "11", fill: "#5B6673" }, fmt(v))),
    svg("line", { x1: L, x2: W - R, y1: H - B, y2: H - B, stroke: "#9AA6B4" }),
    events.map((e) => svg("line", { x1: X(e.t), x2: X(e.t), y1: T, y2: H - B, stroke: "#E8B11C", "stroke-dasharray": "3 4" })),
    svg("polyline", { points: pts.join(" "), fill: "none", stroke: "#2F5D8A", "stroke-width": "2", "stroke-linejoin": "round" }),
    dot);
  plot.addEventListener("mousemove", (ev) => {
    const r = plot.getBoundingClientRect();
    const tx = x0 + (((ev.clientX - r.left) / r.width) * W - L) / (W - L - R) * (x1 - x0);
    let best = 0;
    for (let i = 1; i < t.length; i++) if (Math.abs(t[i] - tx) < Math.abs(t[best] - tx)) best = i;
    if (y[best] === null) return;
    dot.setAttribute("cx", X(t[best])); dot.setAttribute("cy", Y(y[best])); dot.setAttribute("visibility", "visible");
    readout.textContent = `t = ${fmt(t[best])} s · ${fmt(y[best])}${unit ? " " + unit : ""}`;
  });
  plot.addEventListener("mouseleave", () => { dot.setAttribute("visibility", "hidden"); readout.textContent = ""; });
  return el("figure", { class: "chart" }, el("figcaption", {}, name, unit ? el("span", { class: "mono", text: `[${unit}]` }) : null, readout), plot);
}

function downloadCsv() {
  const res = S.sim.result;
  if (!res) return;
  const names = Object.keys(res.series);
  const lines = [["time", ...names].map((n) => `"${n}"`).join(",")];
  res.time.forEach((t, i) => lines.push([t, ...names.map((n) => res.series[n][i] ?? "")].join(",")));
  const a = el("a", { href: URL.createObjectURL(new Blob([lines.join("\n") + "\n"], { type: "text/csv" })), download: (S.analysis ? S.analysis.modelName : "result") + "_result.csv" });
  document.body.append(a); a.click(); a.remove();
}

/* ---------- inspector ---------- */

function refreshFmuSelect() {
  const sel = $("#fmu-select");
  const fmus = S.files.filter((f) => f.kind === "fmu");
  sel.replaceChildren(el("option", { value: "", text: fmus.length ? "FMUs in this folder…" : "No FMUs in this folder yet" }),
    ...fmus.map((f) => el("option", { value: f.path, text: f.path })));
}

async function inspectUpload(file) {
  if (!file) return;
  $("#inspect-out").replaceChildren(el("div", { class: "empty", text: `Reading ${file.name}…` }));
  const r = await api("inspect", { method: "POST", raw: await file.arrayBuffer(), query: { name: file.name } });
  renderInspection(r);
}

async function inspectPath(path) {
  if (!path) return;
  const r = await api("inspect", { method: "POST", body: { path } });
  renderInspection(r);
}

let inspectFilter = "all";
function renderInspection(r) {
  const out = $("#inspect-out");
  if (!r.ok) { out.replaceChildren(el("div", { class: "check-item error" }, el("strong", { text: "ERROR" }), el("div", { text: r.error }))); return; }
  const f = r.result;
  S.inspected = f;
  const caps = Object.entries(f.capabilities).map(([iface, c]) => `${iface}: ` + Object.entries(c).filter(([, v]) => v === "true").map(([k]) => k).join(", "));
  const validation = f.validation
    ? el("div", { class: "check-item " + (f.validation.passed ? "ok" : "error") }, el("strong", { text: f.validation.passed ? "PASS" : "FAIL" }), el("div", {}, el("div", { class: "title", text: `${f.validation.tool} validate` }), el("pre", { class: "mono", style: "white-space:pre-wrap;margin:4px 0 0", text: f.validation.output })))
    : null;
  out.replaceChildren(
    el("div", { class: "row" },
      el("section", { class: "panel summary", style: "flex: 999 1 560px" },
        el("div", { style: "display:flex;flex-wrap:wrap;gap:12px;align-items:baseline" }, el("h1", { text: f.modelName || "(unnamed)" }), el("span", { class: "mono muted", text: `${f.fileName} · ${(f.size / 1024 / 1024).toFixed(2)} MB` })),
        f.description ? el("p", { style: "margin:0", class: "muted", text: f.description }) : null,
        el("div", { class: "chips" }, el("span", { class: "tag strong", text: "FMI " + f.fmiVersion }), f.interfaces.map((i) => el("span", { class: "tag strong", text: i })),
          f.platforms.map((p) => el("span", { class: "tag", text: p })), f.sources ? el("span", { class: "tag", text: "sources" }) : null),
        el("dl", {},
          [["Generated by", f.generationTool], ["Author", f.author], ["Variables", String(f.variables.length)], ["Units", String(f.units)],
            ["Generated", f.generationDateAndTime], ["Capabilities", caps.join("; ") || "–"],
            ["Default experiment", f.defaultExperiment ? Object.entries(f.defaultExperiment).map(([k, v]) => `${k}=${v}`).join(", ") : "–"]]
            .map(([k, v]) => el("div", {}, el("dt", { text: k }), el("dd", { text: v || "–" }))))),
      el("section", { class: "panel summary", style: "flex: 1 1 320px" }, el("h2", { text: "Checks" }),
        f.problems.map((p) => el("div", { class: "check-item error" }, el("strong", { text: "ERROR" }), el("div", { text: p }))),
        f.problems.length ? null : el("div", { class: "check-item ok" }, el("strong", { text: "PASS" }), el("div", { text: "Archive layout and binaries" })),
        validation || el("p", { class: "muted small", text: "Install fmusim for a full schema validation." }))),
    el("section", { class: "panel" }, el("div", { class: "panel-head" }, el("h2", { text: "Variables" }), el("div", { id: "insp-filters", class: "chips" })),
      el("div", { class: "table-wrap" }, el("table", { id: "insp-table", class: "table" }))));
  renderInspectTable();
}

function renderInspectTable() {
  const f = S.inspected;
  const group = (v) => v.causality === "input" ? "inputs" : v.causality === "output" ? "outputs" : /parameter/i.test(v.causality) ? "parameters" : "other";
  const defs = [["all", "All"], ["inputs", "Inputs"], ["outputs", "Outputs"], ["parameters", "Parameters"], ["other", "Other"]];
  $("#insp-filters").replaceChildren(...defs.map(([id, label]) => el("button", {
    type: "button", class: "chip-btn", "aria-pressed": String(inspectFilter === id),
    onClick: () => { inspectFilter = id; renderInspectTable(); },
  }, `${label} ${id === "all" ? f.variables.length : f.variables.filter((v) => group(v) === id).length}`)));
  const rows = f.variables.filter((v) => inspectFilter === "all" || group(v) === inspectFilter);
  $("#insp-table").replaceChildren(
    el("thead", {}, el("tr", {}, ["VR", "Name", "Type", "Size", "Causality", "Variability", "Start", "Unit", "Description"].map((h) => el("th", { scope: "col", text: h })))),
    el("tbody", {}, rows.map((v) => el("tr", {},
      el("td", { class: "mono muted", text: v.vr }), el("td", { class: "mono", text: v.name }),
      el("td", {}, el("span", { class: "pill", text: v.type })), el("td", { class: "mono", text: v.dims.length ? `[${v.dims.join(", ")}]` : "1" }),
      el("td", {}, el("span", { class: "pill caus-" + v.causality, text: v.causality })), el("td", { text: v.variability || "–" }),
      el("td", { class: "mono", text: v.start.length > 40 ? v.start.slice(0, 40) + "…" : (v.start || "–") }),
      el("td", { text: v.unit || "–" }), el("td", { class: "muted", text: v.description || "" })))));
}

/* ---------- templates ---------- */

async function loadTemplates() {
  const r = await api("templates");
  if (!r.ok) return banner("error", r.error);
  S.templates = r.result;
  renderTemplates();
}

function renderTemplates() {
  const cats = [["all", "All"], ["cs", "Co-Simulation"], ["me", "Model Exchange"], ["control", "Control"], ["ml", "Machine learning"]];
  $("#tpl-cats").replaceChildren(...cats.map(([id, label]) => el("button", {
    type: "button", class: "chip-btn", "aria-pressed": String(S.tplCat === id), onClick: () => { S.tplCat = id; renderTemplates(); },
  }, label)));
  const q = $("#tpl-search").value.trim().toLowerCase();
  const items = S.templates.filter((t) => {
    const inCat = S.tplCat === "all" || t.categories.includes(S.tplCat) ||
      (S.tplCat === "cs" && t.interface.includes("Co-Simulation")) || (S.tplCat === "me" && t.interface.includes("Model Exchange"));
    return inCat && (!q || (t.title + " " + t.description + " " + t.tags.join(" ")).toLowerCase().includes(q));
  });
  $("#tpl-grid").replaceChildren(...(items.length ? items.map((t) => el("article", { class: "card" },
    el("div", { style: "display:flex;gap:12px;align-items:center" },
      el("img", { src: "logo.svg", alt: "", width: "36", height: "36" }),
      el("div", {}, el("h2", { text: t.title }), el("span", { class: "muted small", text: t.interface }))),
    el("p", { text: t.description }),
    el("div", { class: "chips" }, t.tags.map((g) => el("span", { class: "tag", text: g }))),
    el("button", { type: "button", class: "btn", onClick: () => useTemplate(t) }, "Use template"),
  )) : [el("div", { class: "empty", text: "No templates match." })]));
}

async function useTemplate(t) {
  const existing = new Set(S.files.map((f) => f.path));
  let name = `${t.id}.py`;
  for (let i = 2; existing.has(name); i++) name = `${t.id}_${i}.py`;
  const r = await api("templates/use", { method: "POST", body: { id: t.id, name } });
  if (!r.ok) return banner("error", "Could not create the file", r.error);
  await loadFiles(r.result.path);
  show("editor");
  banner("ok", `Created ${r.result.path} from the ${t.title} template`);
}

/* ---------- startup ---------- */

async function init() {
  if (!TOKEN) { banner("error", "Missing access token", "Open the Studio with the link printed by `pythonfmu3 studio`."); return; }
  const env = await api("env");
  if (!env.ok) { banner("error", "Cannot reach the Studio server", env.error); return; }
  S.env = env.result;
  $("#status-env").textContent = `PythonFMU3 ${S.env.version} · Python ${S.env.python} · fmusim: ${S.env.fmusim ? "found" : "not found"} · FMPy: ${S.env.fmpy ? "yes" : "no"}`;
  $("#status-ws").textContent = S.env.workspace;

  for (const b of document.querySelectorAll(".tab")) b.addEventListener("click", () => show(b.dataset.view));
  for (const b of document.querySelectorAll(".subtab")) b.addEventListener("click", () => setPreview(b.dataset.preview));
  $("#file-select").addEventListener("change", (e) => e.target.value && openFile(e.target.value));
  $("#btn-save").addEventListener("click", save);
  $("#btn-build").addEventListener("click", (e) => build(e.currentTarget));
  $("#btn-validate").addEventListener("click", (e) => validate(e.currentTarget));
  $("#btn-simulate").addEventListener("click", () => { show("simulate"); runSimulation(); });
  $("#btn-run").addEventListener("click", (e) => runSimulation(e.currentTarget));
  $("#btn-reset").addEventListener("click", () => { S.sim.values = {}; renderSimSettings(); runSimulation(); });
  $("#btn-csv").addEventListener("click", downloadCsv);
  $("#tpl-search").addEventListener("input", renderTemplates);

  const code = $("#code");
  code.addEventListener("input", () => { updateGutter(); updateDirty(); });
  code.addEventListener("scroll", () => { $("#gutter").scrollTop = code.scrollTop; });
  code.addEventListener("keydown", (e) => {
    if (e.key === "Tab" && !e.shiftKey) {
      e.preventDefault();
      const s = code.selectionStart;
      code.setRangeText("    ", s, code.selectionEnd, "end");
      updateGutter(); updateDirty();
    }
  });
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); save(); }
  });
  window.addEventListener("beforeunload", (e) => { if (dirty()) { e.preventDefault(); e.returnValue = ""; } });

  const drop = $("#drop");
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); inspectUpload(e.dataTransfer.files[0]); });
  $("#fmu-input").addEventListener("change", (e) => inspectUpload(e.target.files[0]));
  $("#fmu-select").addEventListener("change", (e) => inspectPath(e.target.value));

  setPreview("fmu");
  show("editor");
  await loadFiles();
  renderCharts();
}

init();
