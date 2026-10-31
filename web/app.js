// Interactive front end: definition list, state map, analysis requests, status panel and tooltip.
//
// The page keeps one state map (component id to state, only what differs from the default). Every
// state-changing click sends the whole map to the analyse endpoint and redraws from the answer, in
// place, so pan and zoom survive. Answers that arrive after a later click are discarded.

import {
  CLICKABLE_KINDS, NULL_TEXT, Schematic, fmtFixed, fmtNum, fmtPower, htmlEl,
} from "./schematic.js";

const $ = (id) => document.getElementById(id);
const BANDS = ["transient", "short_term", "continuous"];
const DEFAULT_BAND_LABELS = { transient: "Transient", short_term: "5 s", continuous: "Continuous" };
const ON_OFF = { operative: "failed", failed: "operative", available: "unavailable",
  unavailable: "available", closed: "open", open: "closed", on: "off", off: "on" };

const app = {
  id: null, // open definition
  data: null, // GET /api/definitions/{id}
  info: {}, // element id to {name, kind, role, default, ...}
  states: {},
  scenario: "",
  band: "continuous",
  result: null,
  analysisSeq: 0, // later clicks win over earlier answers
  openSeq: 0, // later definition choices win over earlier answers
  tooltipFor: null,
  tooltipPinned: false,
  tooltipAt: null,
};

const dom = {};

// --- Messages ------------------------------------------------------------------------------------

function issueList(issues) {
  return htmlEl(
    "ul",
    { class: "issues" },
    ...issues.map((i) =>
      htmlEl("li", { class: "issue" }, htmlEl("code", { class: "path", text: i.path }), " ",
        htmlEl("span", { class: "msg", text: i.message })),
    ),
  );
}

function showMessage(kind, text, issues) {
  dom.message.className = `message ${kind}`;
  dom.message.replaceChildren();
  if (text) dom.message.append(htmlEl("p", { text }));
  if (issues && issues.length) dom.message.append(issueList(issues));
}

function clearMessage() {
  dom.message.className = "message";
  dom.message.replaceChildren();
}

function showWarnings(warnings) {
  dom.warnings.replaceChildren();
  dom.warnings.hidden = !warnings || warnings.length === 0;
  if (dom.warnings.hidden) return;
  dom.warnings.append(htmlEl("h3", { text: "Definition warnings" }), issueList(warnings));
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

function failureIssues(body, response) {
  if (body && Array.isArray(body.errors) && body.errors.length) return body.errors;
  return [{ path: "$", message: `The server answered ${response.status} ${response.statusText}.` }];
}

// --- Definitions ---------------------------------------------------------------------------------

async function refreshDefinitions(selectId) {
  const response = await fetch("/api/definitions");
  const body = await readJson(response);
  const current = selectId ?? dom.definition.value;
  dom.definition.replaceChildren();
  for (const d of body.definitions || []) {
    const detail = d.aircraft ? `${d.aircraft}${d.revision ? ` rev ${d.revision}` : ""}` : "not readable";
    dom.definition.append(htmlEl("option", { value: d.id, title: detail, text: d.id }));
  }
  choose(dom.definition, current);
}

/** Selects the option with this value, or none: a select with nothing chosen shows blank. */
function choose(select, value) {
  const index = [...select.options].findIndex((o) => o.value === value && value !== "");
  select.selectedIndex = index;
}

function resetInteractiveView() {
  app.states = {};
  app.scenario = "";
  app.band = "continuous";
  app.result = null;
  app.analysisSeq += 1;
  hideTooltip();
  choose(dom.scenario, "");
}

function clearDrawing() {
  schematic.clear();
  app.data = null;
  app.info = {};
  dom.verdict.textContent = "";
  dom.verdict.className = "verdict";
  dom.statusList.replaceChildren();
  dom.hint.hidden = false;
  fillBands(null);
  fillScenarios(null);
}

async function openDefinition(id) {
  const seq = ++app.openSeq;
  resetInteractiveView();
  clearMessage();
  showWarnings([]);
  app.id = id || null;
  clearDrawing();
  if (!id) return;
  let response;
  let body;
  try {
    response = await fetch(`/api/definitions/${encodeURIComponent(id)}`);
    body = await readJson(response);
  } catch {
    if (seq === app.openSeq) showMessage("error", "The server could not be reached.");
    return;
  }
  if (seq !== app.openSeq) return;
  if (!response.ok) {
    showMessage("error", `${id} was not opened.`, failureIssues(body, response));
    showWarnings(body.warnings);
    return;
  }
  app.data = body;
  app.info = describe(body.definition);
  dom.hint.hidden = true;
  fillBands(body.definition);
  fillScenarios(body.definition);
  showWarnings(body.warnings);
  schematic.build(body.layout);
  await analyse();
}

/** Element id to its display facts, built from the definition. */
function describe(definition) {
  const info = {};
  for (const s of definition.sources) {
    info[s.id] = { name: s.name, kind: s.kind, default: s.default_state, kindText: sourceKindText(s) };
  }
  for (const t of definition.trus) {
    info[t.id] = { name: t.name, kind: "tru", default: t.default_state, kindText: "TRU" };
  }
  for (const c of definition.contactors) {
    info[c.id] = {
      name: c.name, kind: "contactor", default: c.default_state,
      kindText: c.kind === "bus_tie" ? "Bus tie" : "Contactor", from: c.from, to: c.to,
    };
  }
  for (const b of definition.buses) {
    info[b.id] = {
      name: b.name, kind: "bus", role: b.role, busType: b.type, switch: Boolean(b.crew_switch),
      default: b.crew_switch ? "on" : null, kindText: `${b.type} bus`,
    };
    if (b.crew_switch) {
      info[`${b.id}_switch`] = {
        name: `${b.name} crew switch`, kind: "crew_switch", default: "on", bus: b.id,
        kindText: "Crew switch",
      };
    }
  }
  return info;
}

function sourceKindText(s) {
  return {
    engine_generator: "Engine generator", apu_generator: "APU generator",
    emergency_generator: "Emergency generator", battery: "Battery",
  }[s.kind] || s.kind;
}

function bandLabels() {
  const configured = (app.data && app.data.definition.settings.bands) || {};
  const labels = {};
  for (const b of BANDS) labels[b] = (configured[b] && configured[b].label) || DEFAULT_BAND_LABELS[b];
  return labels;
}

function fillBands(definition) {
  dom.band.replaceChildren();
  const labels = definition ? bandLabels() : DEFAULT_BAND_LABELS;
  for (const b of BANDS) dom.band.append(htmlEl("option", { value: b, text: labels[b] }));
  dom.band.value = app.band;
}

function fillScenarios(definition) {
  dom.scenario.replaceChildren();
  for (const s of definition ? definition.scenarios : []) {
    dom.scenario.append(htmlEl("option", { value: s.id, text: s.name }));
  }
  choose(dom.scenario, app.scenario);
}

// --- Analysis ------------------------------------------------------------------------------------

async function analyse() {
  const seq = ++app.analysisSeq;
  const open = app.openSeq;
  let response;
  let body;
  try {
    response = await fetch(`/api/definitions/${encodeURIComponent(app.id)}/analyse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ states: app.states }),
    });
    body = await readJson(response);
  } catch {
    if (seq === app.analysisSeq) showMessage("error", "The server could not be reached.");
    return;
  }
  if (seq !== app.analysisSeq || open !== app.openSeq) return; // a later click has superseded this
  if (!response.ok) {
    showMessage("error", "The configuration was not analysed.", failureIssues(body, response));
    return;
  }
  clearMessage();
  app.result = body;
  render();
}

function render() {
  if (!app.result) return;
  schematic.update(app.result, app.band, bandLabels(), drawnNames());
  renderStatus();
  refreshTooltip();
}

function drawnNames() {
  const names = {};
  for (const [id, info] of Object.entries(app.info)) {
    names[id] = info.kind === "bus" ? info.name : id;
  }
  return names;
}

// --- Status panel --------------------------------------------------------------------------------

function renderStatus() {
  const r = app.result;
  const labels = bandLabels();
  dom.verdict.textContent = r.verdict;
  dom.verdict.className = `verdict ${r.verdict === "PASS" ? "pass" : "fail"}`;
  const items = [];
  const entry = (kind, tag, ...parts) =>
    htmlEl("li", { class: `status-item ${kind}`, "data-kind": kind }, htmlEl("span", { class: "tag", text: tag }), ...parts);
  const watts = (v) => `${fmtNum(v)} W`;
  for (const o of r.overloads) {
    items.push(
      entry("overload", "Overload",
        htmlEl("span", { class: "element", text: o.element }), " ",
        htmlEl("span", { class: "band", text: labels[o.band] || o.band }), " ",
        htmlEl("span", { class: "with-margin", text: watts(o.demand_with_margin) }), " / ",
        htmlEl("span", { class: "capacity", text: watts(o.capacity) })),
    );
  }
  for (const message of r.config_errors) {
    items.push(entry("config-error", "Configuration error", htmlEl("span", { class: "msg", text: message })));
  }
  for (const u of r.unpowered) {
    items.push(
      entry("unpowered", "Unpowered essential load",
        htmlEl("span", { class: "load-name", text: u.name }), " on ",
        htmlEl("span", { class: "bus", text: (app.info[u.bus] && app.info[u.bus].name) || u.bus })),
    );
  }
  for (const w of r.warnings) {
    items.push(
      entry("warning", "Warning",
        htmlEl("code", { class: "code", text: w.code }), " ",
        htmlEl("span", { class: "msg", text: w.message })),
    );
  }
  if (items.length === 0) items.push(htmlEl("li", { class: "status-item none", text: "Nothing to report." }));
  dom.statusList.replaceChildren(...items);
}

// --- Clicks --------------------------------------------------------------------------------------

function stateKeyOf(id) {
  const info = app.info[id];
  return info.kind === "crew_switch" ? info.bus : id;
}

function currentState(key) {
  return key in app.states ? app.states[key] : app.info[key].default;
}

function toggle(id) {
  const key = stateKeyOf(id);
  const next = ON_OFF[currentState(key)];
  if (!next) return false;
  if (next === app.info[key].default) delete app.states[key];
  else app.states[key] = next;
  if (app.scenario) {
    app.scenario = "";
    choose(dom.scenario, "");
  }
  analyse();
  return true;
}

function onActivate(id, event) {
  const touch = event.pointerType === "touch";
  const info = id ? app.info[id] : null;
  if (info && CLICKABLE_KINDS.has(info.kind)) toggle(id);
  if (touch) {
    if (id) showTooltip(id, { pinned: true });
    else hideTooltip();
  }
}

function onHover(id, event) {
  if (event.type === "wheel" || !id) {
    if (!app.tooltipPinned) hideTooltip();
    return;
  }
  showTooltip(id, { x: event.clientX, y: event.clientY });
}

// --- Tooltip -------------------------------------------------------------------------------------

function tooltipNode(id) {
  const info = app.info[id];
  const key = stateKeyOf(id);
  const record = app.result && app.result.el[key];
  const labels = bandLabels();
  const isBus = info.kind === "bus" || info.kind === "crew_switch";
  const busInfo = app.info[key];
  const rows = [];
  const rated = record && BANDS.some((b) => record.capacity[b] !== null);
  const isUnit = ["engine_generator", "apu_generator", "emergency_generator", "battery", "tru"].includes(info.kind);

  const head = htmlEl("tr", {}, htmlEl("th", { text: "Band" }), htmlEl("th", { text: "Demand" }));
  if (rated) head.append(htmlEl("th", { text: "With margin" }), htmlEl("th", { text: "Capacity" }), htmlEl("th", { text: "Remaining margin" }));
  else head.append(htmlEl("th", { text: "With margin" }), htmlEl("th", { text: "Capacity" }));
  if (isBus) head.append(htmlEl("th", { text: "Own load" }));
  if (isUnit) head.append(htmlEl("th", { text: "Load" }));

  BANDS.forEach((b, i) => {
    const w = (v) => (v === null || v === undefined ? NULL_TEXT : `${fmtNum(v)} W`);
    const row = htmlEl("tr", { "data-band": b }, htmlEl("th", { text: labels[b] }));
    const cell = (field, text, extra) => row.append(htmlEl("td", { "data-field": field, ...extra, text }));
    cell("demand", record ? w(record.demand[b]) : NULL_TEXT);
    cell("with_margin", record ? w(record.with_margin[b]) : NULL_TEXT);
    if (rated) {
      cell("capacity", w(record.capacity[b]));
      const mw = record.margin_w[b];
      const mp = record.margin_pct[b];
      cell("margin", mw === null || mw === undefined ? NULL_TEXT : `${fmtNum(mw)} W (${fmtNum(mp)} %)`);
    } else if (i === 0) {
      cell("capacity", "no capacity", { colspan: 2, rowspan: 3, class: "no-capacity" });
    }
    if (isBus) cell("own", record && record.own ? w(record.own[b]) : NULL_TEXT);
    if (isUnit) cell("load_pct", record && record.load_pct && record.load_pct[b] !== null ? `${fmtNum(record.load_pct[b])} %` : NULL_TEXT);
    rows.push(row);
  });

  const facts = [];
  const state = record && record.state;
  facts.push(["Kind", info.kindText]);
  if (info.kind === "bus") facts.push(["Role", info.role]);
  if (info.kind === "crew_switch") facts.push(["Bus", busInfo.name]);
  if (state) facts.push([info.kind === "bus" || info.kind === "crew_switch" ? "Crew switch" : "State", state]);
  if (info.kind === "contactor") facts.push(["Joins", `${info.from} and ${info.to}`]);
  if (record) facts.push(["Energised", record.energised ? "yes" : "no"]);

  const root = htmlEl("div", { class: "tt-body", "data-for": id });
  root.append(
    htmlEl("div", { class: "tt-title", text: info.name }),
    htmlEl("dl", { class: "tt-facts" },
      ...facts.flatMap(([k, v]) => [htmlEl("dt", { text: k }), htmlEl("dd", { "data-fact": k.toLowerCase(), text: v })])),
    htmlEl("table", { class: "tt-table" }, htmlEl("thead", {}, head), htmlEl("tbody", {}, ...rows)),
  );
  return root;
}

function placeTooltip(point) {
  const tip = dom.tooltip;
  const room = 12;
  const box = tip.getBoundingClientRect();
  let x = point.x + 16;
  let y = point.y + 16;
  if (x + box.width > window.innerWidth - room) x = Math.max(room, point.x - box.width - 16);
  if (y + box.height > window.innerHeight - room) y = Math.max(room, point.y - box.height - 16);
  tip.style.left = `${x}px`;
  tip.style.top = `${y}px`;
}

function showTooltip(id, { x, y, pinned = false } = {}) {
  if (!app.info[id] || !app.result) return;
  app.tooltipFor = id;
  app.tooltipPinned = pinned;
  if (x !== undefined) app.tooltipAt = { x, y };
  else {
    const rect = schematic.rectOf(id);
    app.tooltipAt = rect ? { x: rect.right, y: rect.bottom } : { x: 0, y: 0 };
  }
  dom.tooltip.replaceChildren(tooltipNode(id));
  dom.tooltip.hidden = false;
  dom.tooltip.dataset.for = id;
  placeTooltip(app.tooltipAt);
}

function refreshTooltip() {
  if (app.tooltipFor && !dom.tooltip.hidden) {
    dom.tooltip.replaceChildren(tooltipNode(app.tooltipFor));
    placeTooltip(app.tooltipAt);
  }
}

function hideTooltip() {
  app.tooltipFor = null;
  app.tooltipPinned = false;
  dom.tooltip.hidden = true;
  dom.tooltip.dataset.for = "";
}

// --- Controls ------------------------------------------------------------------------------------

async function upload(file) {
  const form = new FormData();
  form.append("file", file);
  clearMessage();
  let response;
  let body;
  try {
    response = await fetch("/api/definitions", { method: "POST", body: form });
    body = await readJson(response);
  } catch {
    showMessage("error", `${file.name} was not uploaded: the server could not be reached.`);
    return;
  }
  if (response.status === 201) {
    await refreshDefinitions(body.id);
    await openDefinition(body.id);
    showMessage("ok", `${file.name} was uploaded as ${body.id}.`);
    return;
  }
  if (response.status === 409) {
    const reason = failureIssues(body, response).map((i) => i.message).join(" ");
    showMessage("error", `${file.name} was not stored. It conflicts with a stored definition: ${reason}`);
    return;
  }
  showMessage("error", `${file.name} was rejected.`, failureIssues(body, response));
  showWarnings(body.warnings);
}

function selectScenario(id) {
  if (!id || !app.data) {
    app.scenario = "";
    return;
  }
  const scenario = app.data.definition.scenarios.find((s) => s.id === id);
  if (!scenario) return;
  app.scenario = id;
  app.states = { ...scenario.states };
  analyse();
}

function resetStates() {
  if (!app.data) return;
  app.states = {};
  app.scenario = "";
  choose(dom.scenario, "");
  analyse();
}

function bindControls() {
  dom.definition.addEventListener("change", () => openDefinition(dom.definition.value));
  dom.upload.addEventListener("change", async () => {
    const file = dom.upload.files[0];
    if (file) await upload(file);
    dom.upload.value = "";
  });
  dom.band.addEventListener("change", () => {
    app.band = dom.band.value;
    render();
  });
  dom.scenario.addEventListener("change", () => selectScenario(dom.scenario.value));
  dom.reset.addEventListener("click", resetStates);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hideTooltip();
  });
}

let schematic;

async function start() {
  dom.definition = $("definition-select");
  dom.reset = $("reset");
  dom.tooltip = $("tooltip");
  dom.message = $("message");
  dom.warnings = $("warnings");
  dom.upload = $("definition-upload");
  dom.band = $("band-select");
  dom.scenario = $("scenario-select");
  dom.verdict = $("status-verdict");
  dom.statusList = $("status-list");
  dom.hint = $("empty-hint");
  schematic = new Schematic($("schematic"), { onActivate, onHover });
  bindControls();
  fillBands(null);
  fillScenarios(null);
  try {
    await refreshDefinitions("");
  } catch {
    showMessage("error", "The list of definitions could not be loaded.");
  }
}

start();
