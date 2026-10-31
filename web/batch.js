// Batch front end: run every scenario of the open definition, show the results table with a row
// drill-down, open a scenario in the schematic, and export the last results.
//
// The module is imported by app.js and knows nothing about the schematic. It reaches the rest of the
// page through the `host` object it is given. All text from a definition goes in with textContent.

import { NULL_TEXT, fmtNum, htmlEl } from "./schematic.js";

const COLUMNS = [
  ["scenario_id", "Scenario"],
  ["name", "Name"],
  ["result", "Result"],
  ["worst_element", "Worst element"],
  ["worst_band", "Worst band"],
  ["smallest_margin_pct", "Smallest margin (%)"],
  ["overloads", "Overloads"],
  ["configuration_errors", "Configuration errors"],
  ["unpowered_essential", "Unpowered essential loads"],
];

/** The text of one summary cell: counts as they are, a value that does not apply as an em dash. */
export function cellText(column, value) {
  if (value === null || value === undefined) return NULL_TEXT;
  if (column === "smallest_margin_pct") return fmtNum(value);
  return String(value);
}

/**
 * @param {object} host
 * @param {() => Record<string, string>} host.bandLabels  band key to label
 * @param {(busId: string) => string} host.busName
 * @param {(scenarioId: string) => void} host.openScenario  show the scenario in the schematic
 * @param {(view: string) => void} host.showView  "schematic" or "batch"
 * @param {(text: string, issues?: object[]) => void} host.showError
 */
export function initBatch(host) {
  const run = document.getElementById("run-batch");
  const table = document.getElementById("batch-table");
  const body = table.querySelector("tbody");
  const exportCsv = document.getElementById("export-csv");
  const exportJson = document.getElementById("export-json");
  const summary = document.getElementById("batch-summary");
  const empty = document.getElementById("batch-empty");
  const showBatch = document.getElementById("show-batch");
  const showSchematic = document.getElementById("show-schematic");

  let definitionId = null;
  let token = 0; // a result that comes back after the definition changed is dropped

  function setView(view) {
    host.showView(view);
    showSchematic.setAttribute("aria-pressed", String(view === "schematic"));
    showBatch.setAttribute("aria-pressed", String(view === "batch"));
  }

  function hasResults() {
    return body.children.length > 0;
  }

  function sync() {
    run.disabled = !definitionId;
    exportCsv.disabled = !hasResults();
    exportJson.disabled = !hasResults();
    showBatch.disabled = !hasResults();
    empty.hidden = hasResults();
  }

  /** Clears the table, and says which definition a later run is for (null when none is open). */
  function setDefinition(id) {
    token += 1;
    definitionId = id;
    body.replaceChildren();
    summary.textContent = "";
    setView("schematic");
    sync();
  }

  // --- Table ---

  function listOf(title, className, items) {
    if (items.length === 0) return null;
    return htmlEl(
      "section",
      { class: "detail-block" },
      htmlEl("h3", { text: title }),
      htmlEl("ul", {}, ...items.map((item) => htmlEl("li", { class: className }, ...item))),
    );
  }

  function detailBlocks(result) {
    const labels = host.bandLabels();
    const overloads = result.overload_details.map((o) => [
      htmlEl("span", { class: "element", text: o.element }), " ",
      htmlEl("span", { class: "band", text: labels[o.band] || o.band }), " ",
      htmlEl("span", { class: "with-margin", text: `${fmtNum(o.demand_with_margin)} W` }), " / ",
      htmlEl("span", { class: "capacity", text: `${fmtNum(o.capacity)} W` }),
    ]);
    const errors = result.error_messages.map((m) => [htmlEl("span", { class: "msg", text: m })]);
    const unpowered = result.unpowered_details.map((u) => [
      htmlEl("span", { class: "load-name", text: u.name }), " on ",
      htmlEl("span", { class: "bus", text: host.busName(u.bus) }),
    ]);
    const warnings = result.warnings.map((w) => [
      htmlEl("code", { class: "code", text: w.code }), " ",
      htmlEl("span", { class: "msg", text: w.message }),
    ]);
    const blocks = [
      listOf("Overloads", "overload", overloads),
      listOf("Configuration errors", "config-error", errors),
      listOf("Unpowered essential loads", "unpowered", unpowered),
      listOf("Warnings", "warning", warnings),
    ].filter(Boolean);
    return blocks.length ? blocks : [htmlEl("p", { class: "none", text: "Nothing to report." })];
  }

  function rowsFor(result) {
    const id = result.scenario_id;
    const toggle = htmlEl("button", {
      type: "button", class: "expand", "aria-expanded": "false",
      "aria-label": `Show detail of scenario ${id}`, text: "▸",
    });
    const row = htmlEl("tr", {
      class: "result", "data-scenario": id, "data-result": result.result, tabindex: "0",
      title: "Open this scenario in the schematic",
    }, htmlEl("td", { class: "expand-cell" }, toggle));
    for (const [column] of COLUMNS) {
      row.append(htmlEl("td", {
        "data-col": column,
        class: column === "result" ? `result-cell ${result.result === "PASS" ? "pass" : "fail"}` : null,
        text: cellText(column, result[column]),
      }));
    }
    const detail = htmlEl("tr", { class: "detail", "data-for": id, hidden: true },
      htmlEl("td", { colspan: String(COLUMNS.length + 1) }, ...detailBlocks(result)));

    toggle.addEventListener("click", () => {
      const open = detail.hidden;
      detail.hidden = !open;
      toggle.setAttribute("aria-expanded", String(open));
      toggle.textContent = open ? "▾" : "▸";
    });
    row.addEventListener("click", (event) => {
      if (!event.target.closest("button.expand")) host.openScenario(id);
    });
    row.addEventListener("keydown", (event) => {
      if (event.target === row && (event.key === "Enter" || event.key === " ")) {
        event.preventDefault();
        host.openScenario(id);
      }
    });
    return [row, detail];
  }

  function show(results) {
    body.replaceChildren(...results.flatMap(rowsFor));
    const failing = results.filter((r) => r.result !== "PASS").length;
    summary.textContent =
      `${results.length} scenarios: ${results.length - failing} pass, ${failing} fail.`;
    sync();
  }

  // --- Actions ---

  async function runAll() {
    const mine = ++token;
    const id = definitionId;
    if (!id) return;
    run.disabled = true;
    try {
      const response = await fetch(`/api/definitions/${encodeURIComponent(id)}/batch`, { method: "POST" });
      const reply = await response.json().catch(() => ({}));
      if (mine !== token) return;
      if (!response.ok) {
        host.showError("The scenarios were not run.", reply.errors);
        return;
      }
      show(reply.results);
      setView("batch");
    } catch {
      if (mine === token) host.showError("The server could not be reached.");
    } finally {
      if (mine === token) sync();
    }
  }

  async function download(format) {
    const id = definitionId;
    if (!id) return;
    const response = await fetch(`/api/definitions/${encodeURIComponent(id)}/batch/export?format=${format}`);
    if (!response.ok) {
      const reply = await response.json().catch(() => ({}));
      host.showError("The results were not exported.", reply.errors);
      return;
    }
    const url = URL.createObjectURL(await response.blob());
    const link = htmlEl("a", { href: url, download: `${id}-batch.${format}` });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  run.addEventListener("click", runAll);
  exportCsv.addEventListener("click", () => download("csv"));
  exportJson.addEventListener("click", () => download("json"));
  showBatch.addEventListener("click", () => setView("batch"));
  showSchematic.addEventListener("click", () => setView("schematic"));
  sync();

  return { setDefinition, showSchematic: () => setView("schematic") };
}
