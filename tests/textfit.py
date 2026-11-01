"""Measures the real text boxes of a drawn schematic, for the no-overlap, no-clipping and no-drop
checks (L2-WIN-058, L2-WIN-059).

`measure(page)` runs in the browser and returns every text of the drawing as a box in layout units
(the viewport transform undone), with the boxes of the elements, and the layout extent. `problems`
turns that into a list of findings, empty when the drawing is clean.
"""

# Gap kept between two texts, and between a text and a symbol that is not its own, in layout units.
GAP = 0.5
# A text box is the whole font cell, which has room above the capitals and below the descenders that
# no ink reaches. Lines of one block are 11 units apart and their cells overlap by design, so the
# vertical extent that counts is the ink: the cell less this much at the top and at the bottom.
INK_INSET = 2.0

MEASURE_JS = """
() => {
  const svg = document.getElementById("schematic");
  const ctm = document.getElementById("viewport").getScreenCTM();
  const k = ctm.a;
  const lay = (r) => ({
    x: (r.left - ctm.e) / k, y: (r.top - ctm.f) / k,
    r: (r.right - ctm.e) / k, b: (r.bottom - ctm.f) / k,
  });
  const texts = [...svg.querySelectorAll(".names text, .labels text")].map((t) => ({
    kind: t.closest(".names") ? "name" : "label",
    cls: t.getAttribute("class") || "",
    forId: t.dataset.label || t.dataset.name || null,
    text: t.textContent,
    ...lay(t.getBoundingClientRect()),
  }));
  const elements = [...svg.querySelectorAll(".elements > g")].map((g) => ({
    id: g.dataset.id, itemKind: g.dataset.kind,
    ...lay((g.querySelector(".bar, .body, .symbol, .hit") || g).getBoundingClientRect()),
  }));
  return { texts, elements, k };
}
"""


def measure(page):
    return page.evaluate(MEASURE_JS)


def _ink(box):
    return {**box, "y": box["y"] + INK_INSET, "b": box["b"] - INK_INSET}


def _overlap(a, b, gap=GAP):
    a, b = _ink(a), _ink(b)
    return a["x"] < b["r"] + gap and b["x"] < a["r"] + gap and a["y"] < b["b"] + gap and b["y"] < a["b"] + gap


def _name(t):
    return f"{t['kind']} {t['text']!r}" + (f" of {t['forId']}" if t["forId"] else "")


def problems(page, width, height):
    """Text overlaps, text on a symbol, and text outside the layout extent of `width` x `height`."""
    got = measure(page)
    texts, elements = got["texts"], got["elements"]
    found = []
    for i, a in enumerate(texts):
        for b in texts[i + 1 :]:
            if _overlap(a, b):
                found.append(f"text overlap: {_name(a)} and {_name(b)}")
        for e in elements:
            if e["itemKind"] == "bus" and a["cls"].startswith("bus-name") and a["forId"] == e["id"]:
                continue
            if e["itemKind"] == "bus" and e["id"] == a["forId"]:
                continue
            if _overlap(a, e, 0):
                found.append(f"text on symbol: {_name(a)} and {e['id']}")
        if a["x"] < 0 or a["y"] < 0 or a["r"] > width or a["b"] > height:
            found.append(f"clipped: {_name(a)} at {a['x']:.1f},{a['y']:.1f},{a['r']:.1f},{a['b']:.1f}")
    return found
