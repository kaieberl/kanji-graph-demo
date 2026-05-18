"use strict";

const GRAPH_PATH = "../data/kanji_digraph.gexf";
const SIMILAR_LEVEL_LIMIT = 0;
const PAGE_SIZE = 10;
const DEFAULT_NODE_LIMIT = 12;

const state = {
  graph: null,
  graphMode: "similar",
  lookupValue: "時",
  pages: {},
  showRuby: true,
  tokenizer: null,
  tokenizerStatus: "loading",
};

const el = {};

document.addEventListener("DOMContentLoaded", () => {
  bindElements();
  bindEvents();
  updateRangeLabels();
  loadGraph();
  loadTokenizer();
});

function bindElements() {
  for (const id of [
    "status",
    "nodeCount",
    "edgeCount",
    "lookupInput",
    "lookupView",
    "textView",
    "knownLevel",
    "textInput",
    "lookupResults",
    "graphNodeLimit",
    "graphNodeLimitValue",
    "graphPanel",
    "graphTitle",
    "graphMeta",
    "graphSvg",
    "textResults",
    "textUnknown",
    "textHistogram",
  ]) {
    el[id] = document.getElementById(id);
  }
}

function bindEvents() {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => selectTab(button.dataset.tab));
  });

  document.getElementById("lookupForm").addEventListener("submit", (event) => {
    event.preventDefault();
    runLookup(el.lookupInput.value);
  });

  el.knownLevel.addEventListener("change", () => {
    resetTextPages();
    renderTextAnalysis();
  });
  el.graphNodeLimit.addEventListener("input", () => {
    updateRangeLabels();
    renderGraph();
  });
  el.textInput.addEventListener("input", () => {
    resetTextPages();
    renderTextAnalysis();
  });

  document.body.addEventListener("click", (event) => {
    const pageButton = event.target.closest("[data-page-key]");
    if (pageButton) {
      state.pages[pageButton.dataset.pageKey] = Number(pageButton.dataset.page);
      if (pageButton.dataset.pageKey.startsWith("text-")) {
        renderTextAnalysis();
      } else {
        runLookup(state.lookupValue, { preservePages: true });
      }
      return;
    }

    const kanjiButton = event.target.closest("[data-kanji]");
    if (kanjiButton) {
      selectTab("lookup");
      runLookup(kanjiButton.dataset.kanji);
      return;
    }

    const componentButton = event.target.closest("[data-component]");
    if (componentButton) {
      selectTab("lookup");
      runLookup(componentButton.dataset.component);
    }
  });

  document.body.addEventListener("change", (event) => {
    if (event.target.id === "rubyToggle") {
      state.showRuby = event.target.checked;
      renderTextAnalysis();
    }
  });
}

async function loadGraph() {
  try {
    const response = await fetch(GRAPH_PATH);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const xmlText = await response.text();
    state.graph = parseGexf(xmlText);
    el.status.textContent = "Graph data loaded";
    el.nodeCount.textContent = state.graph.nodes.size.toLocaleString();
    el.edgeCount.textContent = state.graph.edges.length.toLocaleString();
    renderAll();
  } catch (error) {
    el.status.textContent = "Could not load graph data";
    const message = "Open this demo through a local web server from the repository root, for example: python3 -m http.server";
    el.lookupResults.innerHTML = `<article class="panel detail-panel"><div class="error">${escapeHtml(message)}<br>${escapeHtml(error.message)}</div></article>`;
  }
}

function loadTokenizer() {
  if (!window.kuromoji) {
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/kuromoji@0.1.2/build/kuromoji.js";
    script.async = true;
    script.onload = buildTokenizer;
    script.onerror = () => {
      state.tokenizerStatus = "unavailable";
      renderTextAnalysis();
    };
    document.head.appendChild(script);
    renderTextAnalysis();
    return;
  }

  buildTokenizer();
}

function buildTokenizer() {
  window.kuromoji.builder({
    dicPath: "https://cdn.jsdelivr.net/npm/kuromoji@0.1.2/dict/",
  }).build((error, tokenizer) => {
    if (error) {
      state.tokenizerStatus = "unavailable";
      renderTextAnalysis();
      return;
    }
    state.tokenizer = tokenizer;
    state.tokenizerStatus = "ready";
    renderTextAnalysis();
  });
}

function renderAll() {
  runLookup(state.lookupValue);
  renderTextAnalysis();
}

function updateRangeLabels() {
  el.graphNodeLimitValue.textContent = el.graphNodeLimit.value;
}

function selectTab(tabName) {
  document.querySelectorAll(".tab-button").forEach((button) => button.classList.toggle("active", button.dataset.tab === tabName));
  el.lookupView.classList.toggle("active", tabName === "lookup");
  el.textView.classList.toggle("active", tabName === "text");
}

function parseGexf(xmlText) {
  const doc = new DOMParser().parseFromString(xmlText, "application/xml");
  const parserError = firstByLocalName(doc, "parsererror");
  if (parserError) {
    throw new Error("Invalid GEXF XML");
  }

  const attrNames = new Map();
  for (const attr of allByLocalName(doc, "attribute")) {
    attrNames.set(attr.getAttribute("id"), attr.getAttribute("title"));
  }

  const nodes = new Map();
  for (const nodeElement of allByLocalName(doc, "node")) {
    const id = nodeElement.getAttribute("id");
    const label = nodeElement.getAttribute("label") || id;
    const attrs = { id, label, level: -1, reading_on: [], reading_kun: [], strokes: 1, radical: "" };
    for (const attvalue of allByLocalName(nodeElement, "attvalue")) {
      const name = attrNames.get(attvalue.getAttribute("for"));
      if (!name) {
        continue;
      }
      const value = attvalue.getAttribute("value") || "";
      if (name === "reading_on" || name === "reading_kun") {
        attrs[name] = parsePythonList(value);
      } else if (name === "level" || name === "strokes") {
        attrs[name] = toInt(value, name === "strokes" ? 1 : -1);
      } else {
        attrs[name] = value;
      }
    }
    nodes.set(id, attrs);
  }

  const edges = [];
  const predecessors = new Map();
  const successors = new Map();
  for (const id of nodes.keys()) {
    predecessors.set(id, []);
    successors.set(id, []);
  }

  for (const edgeElement of allByLocalName(doc, "edge")) {
    const source = edgeElement.getAttribute("source");
    const target = edgeElement.getAttribute("target");
    if (!source || !target) {
      continue;
    }
    edges.push({ source, target });
    if (!successors.has(source)) {
      successors.set(source, []);
    }
    if (!predecessors.has(target)) {
      predecessors.set(target, []);
    }
    successors.get(source).push(target);
    predecessors.get(target).push(source);
  }

  return makeGraph({ nodes, edges, predecessors, successors });
}

function makeGraph(raw) {
  return {
    ...raw,
    has(node) {
      return this.nodes.has(node);
    },
    attrs(node) {
      return this.nodes.get(node);
    },
    getLevel(node) {
      return this.has(node) ? toInt(this.attrs(node).level, -1) : -1;
    },
    getReadings(node) {
      if (!this.has(node)) {
        throw new Error(`${node} is not in the graph`);
      }
      const attrs = this.attrs(node);
      return { on: attrs.reading_on || [], kun: attrs.reading_kun || [] };
    },
    getComponents(kanji) {
      if (!this.has(kanji)) {
        throw new Error(`${kanji} is not in the graph`);
      }
      return [...(this.predecessors.get(kanji) || [])].sort((a, b) => {
        const strokes = this.getStrokes(b) - this.getStrokes(a);
        return strokes || b.localeCompare(a, "ja");
      });
    },
    getCompounds(component) {
      if (!this.has(component)) {
        throw new Error(`${component} is not in the graph`);
      }
      return [...(this.successors.get(component) || [])].sort((a, b) => {
        const level = this.getLevel(b) - this.getLevel(a);
        return level || b.localeCompare(a, "ja");
      });
    },
    getStrokes(node) {
      return this.has(node) ? toInt(this.attrs(node).strokes, 1) : 1;
    },
    getSuccessors(component, kanji) {
      return this.getCompounds(component).filter((item) => item !== kanji);
    },
    getSimilarKanji(kanji, levelLimit = 0) {
      const components = this.getComponents(kanji);
      if (!components.length) {
        return [];
      }
      return this.getSuccessors(components[0], kanji)
        .filter((item) => this.getLevel(item) >= levelLimit);
    },
  };
}

function runLookup(value, options = {}) {
  if (!state.graph) {
    return;
  }
  const node = normalizeSingleInput(value);
  if (!options.preservePages && node !== state.lookupValue) {
    resetLookupPages();
  }
  state.lookupValue = node;
  el.lookupInput.value = node;

  if (!node || !state.graph.has(node)) {
    el.lookupResults.innerHTML = `<article class="panel detail-panel"><h2>Lookup</h2><div class="empty">${escapeHtml(node || "Input")} is not in the graph.</div></article>`;
    el.graphPanel.classList.add("hidden");
    return;
  }

  const isKanji = isKanjiResult(node);
  const isComponent = isComponentResult(node);
  const sections = [];
  if (isKanji) {
    sections.push(renderKanjiPanel(node));
  }
  if (isComponent) {
    sections.push(renderComponentPanel(node));
  }

  if (!sections.length) {
    sections.push(`<article class="panel detail-panel"><h2>${escapeHtml(node)}</h2><div class="empty">No lookup details are available for this node.</div></article>`);
  }

  el.lookupResults.innerHTML = sections.join("");
  state.graphMode = isComponent ? "component" : "similar";
  renderGraph();
}

function isKanjiResult(node) {
  if (!state.graph.has(node)) {
    return false;
  }
  const attrs = state.graph.attrs(node);
  return state.graph.getLevel(node) >= 0 || Boolean((attrs.reading_on || []).length || (attrs.reading_kun || []).length);
}

function isComponentResult(node) {
  return state.graph.has(node) && (state.graph.successors.get(node) || []).length > 0;
}

function renderKanjiPanel(kanji) {
  const readings = state.graph.getReadings(kanji);
  const components = state.graph.getComponents(kanji);
  const similar = state.graph.getSimilarKanji(kanji, SIMILAR_LEVEL_LIMIT);
  const attrs = state.graph.attrs(kanji);
  return `
    <article class="panel detail-panel">
    <h2>Kanji: ${escapeHtml(kanji)}</h2>
    <div class="stat-grid">
      <div class="stat"><strong>${state.graph.getLevel(kanji)}</strong>level</div>
      <div class="stat"><strong>${state.graph.getStrokes(kanji)}</strong>strokes</div>
      <div class="stat"><strong>${components.length}</strong>components</div>
      <div class="stat"><strong>${(state.graph.successors.get(kanji) || []).length}</strong>compounds</div>
    </div>
    <div class="readings">
      <div class="reading-box"><span>On</span>${escapeHtml(formatList(readings.on))}</div>
      <div class="reading-box"><span>Kun</span>${escapeHtml(formatList(readings.kun))}</div>
    </div>
    ${attrs.radical ? `<p><strong>Radical:</strong> ${escapeHtml(attrs.radical)}</p>` : ""}
    <h3>Components</h3>
    ${renderPagedChips(components, "component", "lookup-components")}
    <h3>Similar kanji</h3>
    ${renderPagedChips(similar, "kanji", "lookup-similar")}
    </article>
  `;
}

function renderComponentPanel(component) {
  const compounds = state.graph.getCompounds(component);
  const page = getPage("lookup-compounds", compounds.length);
  const shownCompounds = pageItems(compounds, page);
  const rows = shownCompounds.map((kanji) => {
    const readings = state.graph.getReadings(kanji);
    return `
      <tr>
        <td><button class="chip" type="button" data-kanji="${escapeAttr(kanji)}">${escapeHtml(kanji)}</button></td>
        <td>${state.graph.getLevel(kanji)}</td>
        <td>${escapeHtml(formatList(readings.on))}</td>
        <td>${escapeHtml(formatList(readings.kun))}</td>
      </tr>
    `;
  }).join("");

  return `
    <article class="panel detail-panel">
    <h2>Component: ${escapeHtml(component)}</h2>
    <div class="stat-grid">
      <div class="stat"><strong>${state.graph.getLevel(component)}</strong>level</div>
      <div class="stat"><strong>${state.graph.getStrokes(component)}</strong>strokes</div>
      <div class="stat"><strong>${compounds.length}</strong>containing</div>
      <div class="stat"><strong>${shownCompounds.length}</strong>shown</div>
    </div>
    <table>
      <thead><tr><th>Kanji</th><th>Level</th><th>On</th><th>Kun</th></tr></thead>
      <tbody>${rows || `<tr><td colspan="4">No compounds found.</td></tr>`}</tbody>
    </table>
    ${renderPagination("lookup-compounds", compounds.length)}
    </article>
  `;
}

function renderGraph() {
  if (!state.graph) {
    return;
  }

  const lookup = state.lookupValue;
  let title = "Graph";
  let primary = lookup;
  let componentNodes = new Set();
  let edges = [];
  const nodeLimit = Number(el.graphNodeLimit.value) || DEFAULT_NODE_LIMIT;

  if (!lookup || !state.graph.has(lookup)) {
    el.graphPanel.classList.add("hidden");
    return;
  }

  if (state.graphMode === "component") {
    title = `Kanji containing ${lookup}`;
    componentNodes = new Set([lookup]);
    edges = state.graph.getCompounds(lookup).map((kanji) => [lookup, kanji]);
  } else {
    title = `Similar kanji around ${lookup}`;
    for (const component of state.graph.getComponents(lookup)) {
      componentNodes.add(component);
      edges.push([component, lookup]);
      for (const similar of state.graph.getSuccessors(component, lookup)) {
        if (state.graph.getLevel(similar) >= 0) {
          edges.push([component, similar]);
        }
      }
    }
  }

  edges = limitGraphEdges(edges, lookup, nodeLimit);
  el.graphPanel.classList.toggle("hidden", edges.length === 0);
  el.graphTitle.textContent = title;
  el.graphMeta.textContent = `${uniqueNodes(edges).length}/${nodeLimit} nodes, ${edges.length} edges`;
  el.graphSvg.innerHTML = drawSvgGraph(edges, { primary, componentNodes, mode: state.graphMode });
}

function renderTextAnalysis() {
  if (!state.graph) {
    return;
  }

  const text = el.textInput.value;
  const threshold = Number(el.knownLevel.value);
  const showRuby = state.showRuby;
  const analysis = analyzeText(text, threshold);
  const annotated = renderAnnotatedText(text, analysis, { showRuby });
  const unknownItems = [...analysis.unknown.entries()].sort((a, b) => {
    const level = state.graph.getLevel(a[0]) - state.graph.getLevel(b[0]);
    return level || b[1] - a[1] || a[0].localeCompare(b[0], "ja");
  });
  const unknownPage = getPage("text-unknown", unknownItems.length);
  const unknownRows = pageItems(unknownItems, unknownPage).map(([kanji, count]) => {
    const readings = state.graph.getReadings(kanji);
    return `
      <tr>
        <td><button class="chip" type="button" data-kanji="${escapeAttr(kanji)}">${escapeHtml(kanji)}</button></td>
        <td>${state.graph.getLevel(kanji)}</td>
        <td>${count}</td>
        <td>${escapeHtml(formatList(readings.kun) || formatList(readings.on))}</td>
      </tr>
    `;
  }).join("");

  const missingItems = [...analysis.missing.entries()];
  const missingPage = getPage("text-missing", missingItems.length);
  const missingRows = pageItems(missingItems, missingPage).map(([kanji, count]) => `
    <tr><td>${escapeHtml(kanji)}</td><td>${count}</td></tr>
  `).join("");

  el.textResults.innerHTML = `
    <div class="panel-title-row">
      <h2>Text Analysis</h2>
      <span class="meta">known levels ${threshold}-10</span>
    </div>
    <div class="annotated-text">${annotated || "<span class=\"muted\">No text.</span>"}</div>
    <div class="toggles ruby-toggle-row">
      <label><input id="rubyToggle" type="checkbox" ${showRuby ? "checked" : ""}> Ruby hints</label>
    </div>
    ${showRuby ? `<div class="reading-status">${escapeHtml(readingStatusText())}</div>` : ""}
  `;

  el.textUnknown.innerHTML = `
    <div class="panel-title-row">
      <h2>Unknown Kanji</h2>
    </div>
    <table>
      <thead><tr><th>Kanji</th><th>Level</th><th>Count</th><th>Hint</th></tr></thead>
      <tbody>${unknownRows || `<tr><td colspan="4">No unknown kanji.</td></tr>`}</tbody>
    </table>
    ${renderPagination("text-unknown", unknownItems.length)}
    ${missingItems.length ? `
      <h3>Not in graph</h3>
      <table><thead><tr><th>Kanji</th><th>Count</th></tr></thead><tbody>${missingRows}</tbody></table>
      ${renderPagination("text-missing", missingItems.length)}
    ` : ""}
  `;

  el.textHistogram.innerHTML = `
    <div class="panel-title-row">
      <h2>Level Histogram</h2>
    </div>
    ${renderHistogram(analysis.levelCounts, threshold)}
  `;
}

function limitGraphEdges(edgePairs, primary, nodeLimit) {
  if (!nodeLimit || nodeLimit < 1) {
    return edgePairs;
  }

  const allowed = new Set(primary ? [primary] : []);
  const limited = [];

  for (const [source, target] of edgePairs) {
    const additions = [];
    if (!allowed.has(source)) {
      additions.push(source);
    }
    if (!allowed.has(target)) {
      additions.push(target);
    }
    if (allowed.size + additions.length > nodeLimit) {
      continue;
    }
    additions.forEach((node) => allowed.add(node));
    limited.push([source, target]);
  }

  return limited;
}

function analyzeText(text, threshold) {
  const unknown = new Map();
  const known = new Map();
  const missing = new Map();
  const firstUnknown = new Set();
  const seenUnknown = new Set();
  const levelCounts = new Map();

  for (const char of [...text]) {
    if (!isKanji(char)) {
      continue;
    }
    if (!state.graph.has(char)) {
      missing.set(char, (missing.get(char) || 0) + 1);
      continue;
    }

    const level = state.graph.getLevel(char);
    levelCounts.set(level, (levelCounts.get(level) || 0) + 1);
    if (level >= threshold) {
      known.set(char, (known.get(char) || 0) + 1);
    } else {
      unknown.set(char, (unknown.get(char) || 0) + 1);
      if (!seenUnknown.has(char)) {
        firstUnknown.add(char);
        seenUnknown.add(char);
      }
    }
  }

  return { threshold, unknown, known, missing, firstUnknown, levelCounts };
}

function renderAnnotatedText(text, analysis, options) {
  const firstRendered = new Set();
  if (options.showRuby && state.tokenizer) {
    return renderTokenizedText(text, analysis, options, firstRendered);
  }

  return renderSurface(text, analysis, options, firstRendered);
}

function renderTokenizedText(text, analysis, options, firstRendered) {
  let tokens = [];
  try {
    tokens = state.tokenizer.tokenize(text);
  } catch (_error) {
    return renderSurface(text, analysis, { ...options, showRuby: false }, firstRendered);
  }

  let cursor = 0;
  let html = "";
  for (const token of tokens) {
    const surface = token.surface_form || "";
    if (!surface) {
      continue;
    }
    const index = text.indexOf(surface, cursor);
    if (index < 0) {
      continue;
    }
    if (index > cursor) {
      html += renderSurface(text.slice(cursor, index), analysis, { ...options, showRuby: false }, firstRendered);
    }
    html += renderToken(token, analysis, options, firstRendered);
    cursor = index + surface.length;
  }
  if (cursor < text.length) {
    html += renderSurface(text.slice(cursor), analysis, { ...options, showRuby: false }, firstRendered);
  }
  return html;
}

function renderToken(token, analysis, options, firstRendered) {
  const surface = token.surface_form || "";
  const reading = normalizeTokenReading(token);
  if (!reading || !surfaceHasUnknownKanji(surface, analysis) || reading === kanaComparable(surface)) {
    return renderSurface(surface, analysis, { ...options, showRuby: false }, firstRendered);
  }
  return renderRubyByKanjiGroups(surface, reading, analysis, options, firstRendered)
    || renderSurface(surface, analysis, { ...options, showRuby: false }, firstRendered);
}

function renderRubyByKanjiGroups(surface, reading, analysis, options, firstRendered) {
  const groups = groupKanjiLikeRuns(surface);
  if (!groups.some((group) => group.kanjiLike)) {
    return null;
  }
  if (groups.every((group) => group.kanjiLike)) {
    return rubyMarkup(renderSurface(surface, analysis, { ...options, showRuby: false }, firstRendered), reading);
  }

  let readingIndex = 0;
  let html = "";
  for (let index = 0; index < groups.length; index += 1) {
    const group = groups[index];
    if (group.kanjiLike) {
      const next = groups[index + 1];
      let groupReading = reading.slice(readingIndex);
      if (next && !next.kanjiLike) {
        const nextReading = kanaComparable(next.text);
        const nextReadingIndex = nextReading ? reading.indexOf(nextReading, readingIndex) : -1;
        if (nextReadingIndex < readingIndex) {
          return null;
        }
        groupReading = reading.slice(readingIndex, nextReadingIndex);
        readingIndex = nextReadingIndex;
      } else {
        readingIndex = reading.length;
      }

      const rendered = renderSurface(group.text, analysis, { ...options, showRuby: false }, firstRendered);
      html += groupReading ? rubyMarkup(rendered, groupReading) : rendered;
      continue;
    }

    const groupReading = kanaComparable(group.text);
    if (groupReading && reading.startsWith(groupReading, readingIndex)) {
      readingIndex += groupReading.length;
    }
    html += renderSurface(group.text, analysis, { ...options, showRuby: false }, firstRendered);
  }
  return html;
}

function groupKanjiLikeRuns(surface) {
  const groups = [];
  for (const char of [...surface]) {
    const kanjiLike = isKanjiLikeForRuby(char);
    const last = groups[groups.length - 1];
    if (last && last.kanjiLike === kanjiLike) {
      last.text += char;
    } else {
      groups.push({ kanjiLike, text: char });
    }
  }
  return groups;
}

function rubyMarkup(baseHtml, reading) {
  return `<ruby>${baseHtml}<rt>${escapeHtml(reading)}</rt></ruby>`;
}

function renderSurface(surface, analysis, options, firstRendered) {
  return [...surface].map((char) => {
    if (!isKanji(char)) {
      return escapeHtml(char);
    }
    if (!state.graph.has(char)) {
      return `<span class="missing-kanji" title="Not in graph">${escapeHtml(char)}</span>`;
    }
    const level = state.graph.getLevel(char);
    if (level >= analysis.threshold) {
      return `<span class="known-kanji" title="Level ${level}">${escapeHtml(char)}</span>`;
    }

    const isFirst = analysis.firstUnknown.has(char) && !firstRendered.has(char);
    firstRendered.add(char);
    const classes = ["unknown-kanji"];
    if (isFirst) {
      classes.push("first");
    }
    return `<span class="${classes.join(" ")}" title="Level ${level}">${escapeHtml(char)}</span>`;
  }).join("");
}

function normalizeTokenReading(token) {
  const raw = token.reading || token.pronunciation || "";
  if (!raw || raw === "*") {
    return "";
  }
  return katakanaToHiragana(raw);
}

function kanaComparable(value) {
  return katakanaToHiragana(value);
}

function surfaceHasUnknownKanji(surface, analysis) {
  return [...surface].some((char) => isKanji(char) && state.graph.has(char) && state.graph.getLevel(char) < analysis.threshold);
}

function readingStatusText() {
  if (state.tokenizerStatus === "ready") {
    return "Ruby hints use kuromoji word readings.";
  }
  if (state.tokenizerStatus === "loading") {
    return "Loading kuromoji dictionary for word readings...";
  }
  return "Ruby hints need the kuromoji dictionary CDN; text highlighting still works without it.";
}

function renderHistogram(levelCounts, threshold) {
  const levels = Array.from({ length: 10 }, (_, index) => index + 1);
  const maxCount = Math.max(1, ...levels.map((level) => levelCounts.get(level) || 0));
  const bars = levels.map((level) => {
    const count = levelCounts.get(level) || 0;
    const height = Math.max(3, Math.round((count / maxCount) * 112));
    const className = level < threshold ? "bar unknown" : "bar";
    return `<div class="${className}" style="height:${height}px" title="Level ${level}: ${count}"><span>${level}</span></div>`;
  }).join("");
  return `<div class="histogram">${bars}</div>`;
}

function drawSvgGraph(edgePairs, options) {
  if (!edgePairs.length) {
    return `<div class="empty">No graph data for this selection.</div>`;
  }

  const nodes = uniqueNodes(edgePairs);
  const positions = layoutNodes(nodes, edgePairs, options.primary, options.mode);
  const edgeMarkup = edgePairs.map(([source, target]) => {
    const a = positions.get(source);
    const b = positions.get(target);
    if (!a || !b) {
      return "";
    }
    return `<line class="graph-edge" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"></line>`;
  }).join("");

  const nodeMarkup = nodes.map((node) => {
    const pos = positions.get(node);
    const classes = ["graph-node"];
    const labelClasses = ["graph-label"];
    if (node === options.primary) {
      classes.push("primary");
      labelClasses.push("primary");
    } else if (options.componentNodes && options.componentNodes.has(node)) {
      classes.push("component");
    }
    const radius = node === options.primary ? 25 : 22;
    return `
      <g>
        <circle class="${classes.join(" ")}" cx="${pos.x}" cy="${pos.y}" r="${radius}"></circle>
        <text class="${labelClasses.join(" ")}" x="${pos.x}" y="${pos.y + 1}">${escapeHtml(node)}</text>
      </g>
    `;
  }).join("");

  return `
    <svg viewBox="0 0 800 420" role="img" aria-label="Graph with ${nodes.length} nodes and ${edgePairs.length} edges">
      ${edgeMarkup}
      ${nodeMarkup}
    </svg>
  `;
}

function layoutNodes(nodes, edges, primary, mode) {
  if (mode === "example") {
    return new Map([
      ["寺", { x: 400, y: 210 }],
      ["土", { x: 230, y: 120 }],
      ["寸", { x: 230, y: 300 }],
      ["日", { x: 570, y: 120 }],
      ["扌", { x: 570, y: 300 }],
      ["時", { x: 690, y: 155 }],
      ["持", { x: 690, y: 265 }],
    ].filter(([node]) => nodes.includes(node)));
  }

  const positions = new Map();
  const center = nodes.includes(primary) ? primary : nodes[0];
  positions.set(center, { x: 400, y: 210 });
  const rest = nodes.filter((node) => node !== center);
  const radius = rest.length > 18 ? 170 : 145;
  rest.forEach((node, index) => {
    const angle = (-Math.PI / 2) + (2 * Math.PI * index) / Math.max(1, rest.length);
    positions.set(node, {
      x: Math.round(400 + Math.cos(angle) * radius),
      y: Math.round(210 + Math.sin(angle) * radius),
    });
  });

  const components = edges.filter((edge) => edge[1] === center).map((edge) => edge[0]);
  components.forEach((node, index) => {
    const angle = Math.PI + ((index + 1) * Math.PI) / (components.length + 1);
    positions.set(node, {
      x: Math.round(400 + Math.cos(angle) * 110),
      y: Math.round(210 + Math.sin(angle) * 110),
    });
  });

  return positions;
}

function renderChips(items, type) {
  if (!items.length) {
    return `<div class="empty">None</div>`;
  }
  const attr = type === "component" ? "data-component" : "data-kanji";
  return `<div class="chips">${items.map((item) => `<button class="chip" type="button" ${attr}="${escapeAttr(item)}">${escapeHtml(item)}</button>`).join("")}</div>`;
}

function renderPagedChips(items, type, key) {
  if (!items.length) {
    return `<div class="empty">None</div>`;
  }
  const page = getPage(key, items.length);
  return renderChips(pageItems(items, page), type) + renderPagination(key, items.length);
}

function getPage(key, totalItems) {
  const maxPage = Math.max(0, Math.ceil(totalItems / PAGE_SIZE) - 1);
  const page = state.pages[key] || 0;
  const normalized = Math.min(maxPage, Math.max(0, page));
  state.pages[key] = normalized;
  return normalized;
}

function pageItems(items, page) {
  const start = page * PAGE_SIZE;
  return items.slice(start, start + PAGE_SIZE);
}

function renderPagination(key, totalItems) {
  if (totalItems <= PAGE_SIZE) {
    return "";
  }
  const page = getPage(key, totalItems);
  const maxPage = Math.ceil(totalItems / PAGE_SIZE) - 1;
  const start = page * PAGE_SIZE + 1;
  const end = Math.min(totalItems, start + PAGE_SIZE - 1);
  return `
    <div class="pagination">
      <button type="button" data-page-key="${escapeAttr(key)}" data-page="${page - 1}" ${page === 0 ? "disabled" : ""}>Previous</button>
      <span>${start}-${end} of ${totalItems}</span>
      <button type="button" data-page-key="${escapeAttr(key)}" data-page="${page + 1}" ${page >= maxPage ? "disabled" : ""}>Next</button>
    </div>
  `;
}

function resetLookupPages() {
  for (const key of Object.keys(state.pages)) {
    if (key.startsWith("lookup-")) {
      delete state.pages[key];
    }
  }
}

function resetTextPages() {
  for (const key of Object.keys(state.pages)) {
    if (key.startsWith("text-")) {
      delete state.pages[key];
    }
  }
}

function uniqueNodes(edgePairs) {
  const seen = new Set();
  for (const [source, target] of edgePairs) {
    seen.add(source);
    seen.add(target);
  }
  return [...seen];
}

function normalizeSingleInput(value) {
  return [...value.trim()][0] || "";
}

function formatList(items) {
  return items && items.length ? items.join(", ") : "-";
}

function isKanji(char) {
  const code = char.codePointAt(0);
  return code >= 0x4e00 && code <= 0x9fff;
}

function isKanjiLikeForRuby(char) {
  return isKanji(char) || char === "々";
}

function katakanaToHiragana(value) {
  return [...value].map((char) => {
    const code = char.codePointAt(0);
    if (code >= 0x30a1 && code <= 0x30f6) {
      return String.fromCodePoint(code - 0x60);
    }
    return char;
  }).join("");
}

function parsePythonList(value) {
  if (!value || value === "[]") {
    return [];
  }
  const matches = [...value.matchAll(/'([^']*)'|"([^"]*)"/g)].map((match) => match[1] ?? match[2]);
  if (matches.length) {
    return matches;
  }
  return [value];
}

function allByLocalName(root, localName) {
  return [...root.getElementsByTagName("*")].filter((item) => item.localName === localName);
}

function firstByLocalName(root, localName) {
  return allByLocalName(root, localName)[0] || null;
}

function toInt(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}
