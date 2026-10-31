// Schematic rendering, pan and zoom, and the number formats shared by the whole front end.
//
// The layout is computed by the back end (ela/layout.py) and drawn here as it comes. This module
// holds no layout logic. Every piece of text that comes from a definition goes in with textContent
// (never innerHTML), because uploaded definitions are untrusted.

const SVG_NS = "http://www.w3.org/2000/svg";
export const NULL_TEXT = "—"; // em dash, shown for a value that does not apply

// --- DOM helpers ---------------------------------------------------------------------------------

function build(node, attrs, children) {
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "text") node.textContent = value;
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function svgEl(tag, attrs, ...children) {
  return build(document.createElementNS(SVG_NS, tag), attrs, children);
}

export function htmlEl(tag, attrs, ...children) {
  return build(document.createElement(tag), attrs, children);
}

// --- Number formats ------------------------------------------------------------------------------
//
// These follow ela.format.format_pct: half up on the shortest decimal form of the number, so 76.625
// shows 76.63 and 12.0 shows 12. JavaScript's toFixed works on the binary value and gets some of
// these wrong. A negative number is written with the ASCII hyphen-minus.

function scaledDigits(value, places) {
  // |value| rounded half up at `places` decimals, as a BigInt of that many hundredths and so on.
  const abs = Math.abs(value);
  let text = String(abs);
  if (/e/i.test(text)) text = abs.toFixed(20); // tiny numbers only, which round to zero anyway
  const [whole, fraction = ""] = text.split(".");
  const padded = fraction.padEnd(places + 1, "0");
  let digits = BigInt(whole + padded.slice(0, places));
  if (padded.charCodeAt(places) >= 53) digits += 1n; // next digit 5 or more rounds up
  return digits;
}

function groupDigits(digits, places) {
  const text = digits.toString().padStart(places + 1, "0");
  return places === 0 ? text : `${text.slice(0, -places)}.${text.slice(-places)}`;
}

/** A number with exactly `places` decimals, half up. */
export function fmtFixed(value, places = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return NULL_TEXT;
  const digits = scaledDigits(value, places);
  const sign = value < 0 && digits !== 0n ? "-" : "";
  return sign + groupDigits(digits, places);
}

/** A number with at most `places` decimals and no trailing zeros: 12.0 gives 12, 76.625 gives 76.63. */
export function fmtNum(value, places = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return NULL_TEXT;
  const digits = scaledDigits(value, places);
  if (digits === 0n) return "0";
  let text = groupDigits(digits, places);
  if (places > 0) text = text.replace(/0+$/, "").replace(/\.$/, "");
  return (value < 0 ? "-" : "") + text;
}

/** Power to the nearest watt: whole W below 1000 W after rounding, kW with two decimals from there. */
export function fmtPower(watts) {
  if (watts === null || watts === undefined || Number.isNaN(watts)) return NULL_TEXT;
  const rounded = scaledDigits(watts, 0);
  const sign = watts < 0 && rounded !== 0n ? "-" : "";
  if (rounded < 1000n) return `${sign}${rounded} W`;
  const hundredths = (rounded + 5n) / 10n;
  return `${sign}${groupDigits(hundredths, 2)} kW`;
}

// --- Element status ------------------------------------------------------------------------------

export const CLICKABLE_KINDS = new Set([
  "engine_generator", "apu_generator", "emergency_generator", "battery", "tru", "contactor",
  "crew_switch",
]);
const ICON_KINDS = new Set([
  "engine_generator", "apu_generator", "emergency_generator", "battery", "tru",
]);
const SOURCE_KINDS = new Set([
  "engine_generator", "apu_generator", "emergency_generator", "battery",
]);

/** One of failed, overloaded, energised, deenergised. A failed unit is grey with a mark. */
export function statusOf(kind, record, overloaded) {
  if (!record) return "deenergised";
  const isUnit = SOURCE_KINDS.has(kind) || kind === "tru";
  if (isUnit && record.state === "failed") return "failed";
  if (overloaded) return "overloaded";
  return record.energised ? "energised" : "deenergised";
}

// --- Symbols -------------------------------------------------------------------------------------

// A contactor is two contact dots joined by a blade. Closed, the blade runs from dot to dot. Open, it
// leaves the second dot at an angle and stops short of the first, so the shape differs without colour.
const CONTACTOR_PATHS = {
  vertical: { closed: "M10 0V20", open: "M10 0V4M10 20V16M10 16L16.5 6" },
  horizontal: { closed: "M0 10H20", open: "M0 10H4M20 10H16M16 10L6 3.5" },
};
const CONTACT_DOTS = {
  vertical: [[10, 4], [10, 16]],
  horizontal: [[4, 10], [16, 10]],
};
const SWITCH_PATHS = {
  on: "M5 13H15",
  off: "M5 13L14.5 5.5",
};

function hitRect(width, height) {
  return svgEl("rect", { class: "hit", x: 0, y: 0, width, height });
}

function drawBus(width, height) {
  return [svgEl("rect", { class: "bar", x: 0, y: 0, width, height, rx: 2 })];
}

function drawGenerator(width, height) {
  const r = Math.min(width, height) / 2 - 1.5;
  return [
    hitRect(width, height),
    svgEl("circle", { class: "body", cx: width / 2, cy: height / 2, r }),
    svgEl("text", { class: "glyph", x: width / 2, y: height / 2, text: "G" }),
  ];
}

function drawBattery(width, height) {
  const mid = width / 2;
  return [
    hitRect(width, height),
    svgEl("path", {
      class: "symbol",
      d:
        `M${mid} 1.5V9M${mid - 9} 9H${mid + 9}M${mid - 5} 14H${mid + 5}` +
        `M${mid - 9} 19H${mid + 9}M${mid - 5} 24H${mid + 5}M${mid} 24V${height - 1.5}`,
    }),
    svgEl("path", { class: "plate", d: `M${mid - 5} 14H${mid + 5}M${mid - 5} 24H${mid + 5}` }),
    svgEl("path", { class: "plus", d: `M${mid + 8} 3H${mid + 14}M${mid + 11} 0V6` }),
  ];
}

function drawTru(width, height) {
  return [
    hitRect(width, height),
    svgEl("rect", { class: "body", x: 1.5, y: 1.5, width: width - 3, height: height - 3, rx: 3 }),
    svgEl("path", { class: "symbol", d: `M4 ${height - 4}L${width - 4} 4` }),
    // AC on the input (upper) side, DC on the output (lower) side
    svgEl("path", { class: "symbol", d: `M6 8Q8 4 10 8T14 8` }),
    svgEl("path", {
      class: "symbol",
      d: `M${width - 14} ${height - 9}H${width - 7}M${width - 14} ${height - 6}H${width - 7}`,
    }),
  ];
}

function drawContactor(item) {
  const orientation = item.orientation in CONTACTOR_PATHS ? item.orientation : "vertical";
  return [
    hitRect(item.width, item.height),
    svgEl("path", { class: "symbol", d: CONTACTOR_PATHS[orientation].closed }),
    ...CONTACT_DOTS[orientation].map(([cx, cy]) => svgEl("circle", { class: "contact", cx, cy, r: 2.6 })),
  ];
}

function drawSwitch(width, height) {
  return [
    hitRect(width, height),
    svgEl("rect", { class: "body", x: 0.75, y: 0.75, width: width - 1.5, height: height - 1.5, rx: 4 }),
    svgEl("path", { class: "symbol", d: SWITCH_PATHS.on }),
    svgEl("circle", { class: "contact", cx: 5, cy: 13, r: 2 }),
    svgEl("circle", { class: "contact", cx: 15, cy: 13, r: 2 }),
  ];
}

const SYMBOL_NAMES = {
  bus: "bus",
  engine_generator: "generator",
  apu_generator: "generator",
  emergency_generator: "generator",
  battery: "battery",
  tru: "tru",
  contactor: "contactor",
  crew_switch: "switch",
};

function drawItem(item) {
  switch (item.kind) {
    case "bus": return drawBus(item.width, item.height);
    case "battery": return drawBattery(item.width, item.height);
    case "tru": return drawTru(item.width, item.height);
    case "contactor": return drawContactor(item);
    case "crew_switch": return drawSwitch(item.width, item.height);
    default: return drawGenerator(item.width, item.height);
  }
}

function failMark(width, height) {
  const a = Math.min(width, height) * 0.27;
  return svgEl("path", {
    class: "fail-mark",
    d: `M${a} ${a}L${width - a} ${height - a}M${width - a} ${a}L${a} ${height - a}`,
  });
}

// --- The schematic -------------------------------------------------------------------------------

const MIN_ZOOM = 0.2;
const MAX_ZOOM = 8;
const MAX_FIT = 1.5;
const CLICK_SLOP = 5; // px: pointer movement below this is a click

export class Schematic {
  /**
   * @param {SVGSVGElement} svg  the #schematic element, holding a #viewport group with the layers
   * @param {{onActivate: Function, onHover: Function}} callbacks
   */
  constructor(svg, callbacks) {
    this.svg = svg;
    this.cb = callbacks;
    this.viewport = svg.querySelector("#viewport");
    this.layers = {};
    for (const name of ["wires", "elements", "names", "labels"]) {
      this.layers[name] = this.viewport.querySelector(`.${name}`);
    }
    this.view = { k: 1, tx: 0, ty: 0, initial: true };
    this.items = new Map(); // id -> {item, group, busId}
    this.extent = null;
    this.press = null;
    this.bindPointer();
    new ResizeObserver(() => {
      if (this.view.initial) this.fit();
    }).observe(svg);
  }

  // --- Building ---

  clear() {
    for (const layer of Object.values(this.layers)) layer.replaceChildren();
    this.items.clear();
    this.extent = null;
  }

  /** Draws a definition's layout from scratch and puts the view at its initial position. */
  build(layout) {
    this.clear();
    this.extent = { width: layout.width, height: layout.height };
    for (const c of layout.connectors) {
      this.layers.wires.append(
        svgEl("polyline", {
          class: "wire",
          "data-from": c.from,
          "data-to": c.to,
          points: c.points.map((p) => p.join(",")).join(" "),
        }),
      );
    }
    const ordered = [...layout.items].sort((a, b) => (a.kind === "bus" ? 0 : 1) - (b.kind === "bus" ? 0 : 1));
    for (const item of ordered) {
      const group = svgEl(
        "g",
        {
          class: `el kind-${item.kind}${CLICKABLE_KINDS.has(item.kind) ? " clickable" : ""}`,
          "data-id": item.id,
          "data-kind": item.kind,
          "data-symbol": SYMBOL_NAMES[item.kind] || item.kind,
          "data-state": "",
          transform: `translate(${item.x} ${item.y})`,
        },
        ...drawItem(item),
      );
      this.layers.elements.append(group);
      const busId = item.kind === "crew_switch" ? item.id.replace(/_switch$/, "") : null;
      this.items.set(item.id, { item, group, busId });
    }
    this.resetView();
  }

  // --- View ---

  applyView() {
    const { k, tx, ty } = this.view;
    this.viewport.setAttribute("transform", `translate(${tx} ${ty}) scale(${k})`);
  }

  /** Fits the whole layout in the drawing area, centred. Does nothing while the area is hidden. */
  fit() {
    const width = this.svg.clientWidth;
    const height = this.svg.clientHeight;
    if (!this.extent || !width || !height) return;
    const k = Math.min(width / this.extent.width, height / this.extent.height, MAX_FIT);
    this.view.k = k;
    this.view.tx = (width - this.extent.width * k) / 2;
    this.view.ty = (height - this.extent.height * k) / 2;
    this.applyView();
  }

  resetView() {
    this.view.initial = true;
    this.view.k = 1;
    this.view.tx = 0;
    this.view.ty = 0;
    this.applyView();
    this.fit();
  }

  zoomAt(factor, px, py) {
    const view = this.view;
    const k = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, view.k * factor));
    view.tx = px - ((px - view.tx) * k) / view.k;
    view.ty = py - ((py - view.ty) * k) / view.k;
    view.k = k;
    view.initial = false;
    this.applyView();
  }

  // --- Pointer handling ---

  idAt(target) {
    const group = target instanceof Element ? target.closest("[data-id]") : null;
    return group && this.svg.contains(group) ? group.dataset.id : null;
  }

  bindPointer() {
    const svg = this.svg;
    svg.addEventListener("pointerdown", (e) => {
      if (e.pointerType === "mouse" && e.button !== 0) return;
      this.press = {
        x: e.clientX,
        y: e.clientY,
        id: this.idAt(e.target),
        tx: this.view.tx,
        ty: this.view.ty,
        moved: false,
        pointerId: e.pointerId,
      };
      try {
        svg.setPointerCapture(e.pointerId);
      } catch {
        // A pointer that is not active (a synthetic event) cannot be captured. Nothing is lost.
      }
    });
    svg.addEventListener("pointermove", (e) => {
      const press = this.press;
      if (!press) {
        if (e.pointerType === "mouse") this.cb.onHover(this.idAt(e.target), e);
        return;
      }
      if (e.pointerId !== press.pointerId) return;
      const dx = e.clientX - press.x;
      const dy = e.clientY - press.y;
      if (!press.moved && Math.hypot(dx, dy) >= CLICK_SLOP) {
        press.moved = true;
        svg.classList.add("panning");
        this.cb.onHover(null, e);
      }
      if (press.moved) {
        this.view.tx = press.tx + dx;
        this.view.ty = press.ty + dy;
        this.view.initial = false;
        this.applyView();
      }
    });
    const finish = (e, cancelled) => {
      const press = this.press;
      if (!press || e.pointerId !== press.pointerId) return;
      this.press = null;
      svg.classList.remove("panning");
      if (svg.hasPointerCapture(e.pointerId)) svg.releasePointerCapture(e.pointerId);
      if (!cancelled && !press.moved) this.cb.onActivate(press.id, e);
    };
    svg.addEventListener("pointerup", (e) => finish(e, false));
    svg.addEventListener("pointercancel", (e) => finish(e, true));
    svg.addEventListener("pointerleave", (e) => {
      if (e.pointerType === "mouse" && !this.press) this.cb.onHover(null, e);
    });
    svg.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        const box = svg.getBoundingClientRect();
        this.cb.onHover(null, e);
        this.zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - box.left, e.clientY - box.top);
      },
      { passive: false },
    );
  }

  // --- Drawing the analysis ---

  /**
   * Colours, states, failure marks and value labels from an analysis result.
   * @param {object} result  the analyse response
   * @param {string} band    transient, short_term or continuous
   * @param {Record<string, string>} bandLabels  band key to display label
   * @param {Record<string, string>} names  element id to name, for the ids drawn beside icons
   */
  update(result, band, bandLabels, names) {
    const failedBands = new Map();
    for (const o of result.overloads) {
      if (!failedBands.has(o.element)) failedBands.set(o.element, []);
      failedBands.get(o.element).push(o.band);
    }
    const status = new Map();
    this.layers.labels.replaceChildren();
    this.layers.names.replaceChildren();

    for (const [id, entry] of this.items) {
      const { item, group } = entry;
      const elementId = entry.busId || id;
      const record = result.el[elementId];
      const bands = failedBands.get(elementId) || [];
      const st = statusOf(entry.busId ? "bus" : item.kind, record, bands.length > 0);
      status.set(id, st);
      group.setAttribute(
        "class",
        `el kind-${item.kind}${CLICKABLE_KINDS.has(item.kind) ? " clickable" : ""} status-${st}`,
      );
      group.dataset.state = record && record.state ? record.state : "";
      group.dataset.status = st;
      group.dataset.energised = record && record.energised ? "true" : "false";

      const symbol = group.querySelector(".symbol");
      if (item.kind === "contactor" && symbol) {
        const paths = CONTACTOR_PATHS[item.orientation in CONTACTOR_PATHS ? item.orientation : "vertical"];
        symbol.setAttribute("d", record && record.state === "open" ? paths.open : paths.closed);
      }
      if (item.kind === "crew_switch" && symbol) {
        symbol.setAttribute("d", record && record.state === "off" ? SWITCH_PATHS.off : SWITCH_PATHS.on);
      }
      const mark = group.querySelector(".fail-mark");
      if (st === "failed" && !mark) group.append(failMark(item.width, item.height));
      if (st !== "failed" && mark) mark.remove();

      this.drawLabel(item, record, bands, band, bandLabels, st);
      this.drawName(item, names[id], st);
    }

    for (const wire of this.layers.wires.children) {
      wire.classList.toggle("live", this.wireLive(wire, result));
    }
  }

  wireLive(wire, result) {
    const ends = [wire.dataset.from, wire.dataset.to];
    const live = ends.map((id) => {
      const entry = this.items.get(id);
      const record = result.el[id];
      return { contactor: entry && entry.item.kind === "contactor", on: Boolean(record && record.energised) };
    });
    const nodes = live.filter((n) => !n.contactor);
    if (nodes.length === 0) return live.some((n) => n.on);
    return nodes.every((n) => n.on);
  }

  drawLabel(item, record, failed, band, bandLabels, status) {
    if (!record) return;
    const extra = failed.filter((b) => b !== band).map((b) => bandLabels[b] || b);
    let lines = [];
    if (item.kind === "bus") {
      if (!record.energised) return;
      const volts = record.voltage ? record.voltage[band] : null;
      const amps = record.current ? record.current[band] : null;
      const power = fmtPower(record.demand[band]);
      const head = `${fmtNum(volts)} V ${fmtFixed(amps, 2)} A`;
      const wide = item.label && item.label.width >= 100 && item.label.height < 22;
      lines = wide ? [`${head} ${power}`] : [head, power];
    } else if (ICON_KINDS.has(item.kind)) {
      if (status === "failed" || !record.energised || record.demand[band] === null) return;
      lines = [fmtPower(record.demand[band]), `${fmtNum(record.load_pct[band])} %`];
    } else if (item.kind === "contactor") {
      // No value label of its own, so it names every failed band, the displayed one included.
      if (failed.length === 0) return;
      extra.splice(0, extra.length, ...failed.map((b) => bandLabels[b] || b));
    } else {
      return;
    }
    if (extra.length) lines.push(`over: ${extra.join(", ")}`);
    this.layers.labels.append(this.labelText(item, lines));
  }

  labelText(item, lines) {
    const step = 11;
    const box = item.label || {
      x: item.x + item.width + 3,
      y: item.y + item.height / 2 - 6,
      width: 60,
      height: 12,
    };
    const onLeft = item.kind !== "bus" && box.x + box.width <= item.x;
    const above = item.kind === "bus" && box.y + box.height <= item.y;
    const x = onLeft ? box.x + box.width : box.x;
    const natural = Math.max(1, Math.round(box.height / 12));
    const grow = Math.max(0, lines.length - natural) * step;
    let y = box.y + 10;
    if (above) y -= grow;
    else if (item.kind !== "bus" && item.kind !== "contactor") y -= grow / 2;
    const text = svgEl("text", {
      class: `value-label${lines.some((l) => l.startsWith("over:")) ? " has-over" : ""}`,
      "data-label": item.id,
      x,
      y,
      "text-anchor": onLeft ? "end" : "start",
    });
    lines.forEach((line, i) => {
      const last = i === lines.length - 1;
      text.append(svgEl("tspan", { x, dy: i === 0 ? 0 : step, text: last ? line : `${line} ` }));
    });
    return text;
  }

  drawName(item, name, status) {
    if (!name || item.kind === "contactor" || item.kind === "crew_switch") return;
    if (item.kind === "bus") {
      if (name.length * 5.6 + 8 > item.width) return;
      this.layers.names.append(
        svgEl("text", {
          class: `bus-name status-${status}`,
          x: item.x + 5,
          y: item.y + item.height / 2,
          text: name,
        }),
      );
      return;
    }
    const labelOnRight = !item.label || item.label.x >= item.x + item.width;
    const x = labelOnRight ? item.x - 4 : item.x + item.width + 4;
    this.layers.names.append(
      svgEl("text", {
        class: "icon-name",
        x,
        y: item.y + item.height / 2,
        "text-anchor": labelOnRight ? "end" : "start",
        text: name,
      }),
    );
  }

  /** The on-screen rectangle of an element, for placing a tooltip. */
  rectOf(id) {
    const entry = this.items.get(id);
    return entry ? entry.group.getBoundingClientRect() : null;
  }
}
