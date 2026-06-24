/**
 * Minimal DOM/localStorage stub for node:test — no jsdom dependency.
 * Covers exactly what favorites.js / scores.js / standings.js / settings.js / loadmore.js use.
 */

class StubClassList {
  constructor() { this._set = new Set(); }
  add(cls) { this._set.add(cls); }
  remove(cls) { this._set.delete(cls); }
  contains(cls) { return this._set.has(cls); }
  toggle(cls, force) {
    if (force === undefined) {
      if (this._set.has(cls)) { this._set.delete(cls); return false; }
      this._set.add(cls); return true;
    }
    if (force) { this._set.add(cls); return true; }
    this._set.delete(cls); return false;
  }
}

class StubElement {
  constructor(tag) {
    this.tagName = tag ? tag.toUpperCase() : "DIV";
    this.dataset = {};
    this.classList = new StubClassList();
    this._children = [];
    this._listeners = {};
    this.style = {};
    this._innerHTML = "";
    this._textContent = "";
    this.value = "";
    this.type = "";
    this.checked = false;
    this.name = "";
    this._id = "";
  }

  get id() { return this._id; }
  set id(v) { this._id = v; }

  get innerHTML() { return this._innerHTML; }
  set innerHTML(v) { this._innerHTML = v; this._children = []; }

  get textContent() { return this._textContent; }
  set textContent(v) { this._textContent = v; this._innerHTML = v; }

  get children() { return this._children; }

  appendChild(child) {
    this._children.push(child);
    if (child && child._parent !== undefined) child._parent = this;
    return child;
  }

  insertAdjacentHTML(pos, html) {
    // Parse-less: just record raw strings for ordering tests.
    // Also create stub elements for data-away-team/data-home-team matching.
    this._insertedBlocks = this._insertedBlocks || [];
    this._insertedBlocks.push(html);
    // Try to extract stub rows so applyFavoriteHighlights can work in unit tests.
    const rows = parseStubRows(html);
    for (const r of rows) this._children.push(r);
  }

  querySelector(sel) {
    return this._querySelectorAll(sel)[0] || null;
  }

  querySelectorAll(sel) {
    return this._querySelectorAll(sel);
  }

  _querySelectorAll(sel) {
    const results = [];
    this._walk(this, sel, results);
    return results;
  }

  _walk(node, sel, results) {
    if (node !== this && matchesSelector(node, sel)) results.push(node);
    for (const child of node._children || []) this._walk(child, sel, results);
  }

  matches(sel) { return matchesSelector(this, sel); }

  addEventListener(evt, fn) {
    if (!this._listeners[evt]) this._listeners[evt] = [];
    this._listeners[evt].push(fn);
  }

  dispatchEvent(evt) {
    const handlers = this._listeners[evt.type] || [];
    for (const h of handlers) h(evt);
  }

  remove() {}
  setAttribute(k, v) { this[`_attr_${k}`] = v; }
  getAttribute(k) { return this[`_attr_${k}`] ?? null; }
  closest(sel) { return null; }
}

function parseStubRows(html) {
  // Extract data-away-team / data-home-team from raw HTML strings for unit test assertions.
  const rows = [];
  const re = /<tr([^>]*)>/gi;
  let m;
  while ((m = re.exec(html)) !== null) {
    const attrs = m[1];
    const away = /data-away-team="([^"]*)"/.exec(attrs)?.[1];
    const home = /data-home-team="([^"]*)"/.exec(attrs)?.[1];
    if (away !== undefined || home !== undefined) {
      const el = new StubElement("tr");
      if (away !== undefined) el.dataset.awayTeam = away;
      if (home !== undefined) el.dataset.homeTeam = home;
      rows.push(el);
    }
  }
  return rows;
}

function matchesSelector(node, sel) {
  if (!(node instanceof StubElement)) return false;
  sel = sel.trim();

  // [data-attr] presence
  if (/^\[data-([a-zA-Z-]+)\]$/.test(sel)) {
    const attr = sel.slice(1, -1).replace(/^data-/, "").replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    return node.dataset[attr] !== undefined;
  }

  // [data-attr="val"]
  if (/^\[data-([a-zA-Z-]+)="([^"]*)"\]$/.test(sel)) {
    const [, rawAttr, val] = sel.match(/^\[data-([a-zA-Z-]+)="([^"]*)"\]$/);
    const attr = rawAttr.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    return node.dataset[attr] === val;
  }

  // compound: [data-a][data-b] (AND)
  if (sel.startsWith("[") && sel.includes("][")) {
    const parts = sel.match(/\[([^\]]+)\]/g) || [];
    return parts.every((p) => matchesSelector(node, p));
  }

  // .class
  if (/^\.[a-zA-Z_-][\w-]*$/.test(sel)) {
    return node.classList.contains(sel.slice(1));
  }

  // tag
  if (/^[a-zA-Z]+$/.test(sel)) {
    return node.tagName === sel.toUpperCase();
  }

  // tag.class
  if (/^[a-zA-Z]+\.[a-zA-Z_-][\w-]*$/.test(sel)) {
    const [tag, cls] = sel.split(".");
    return node.tagName === tag.toUpperCase() && node.classList.contains(cls);
  }

  // type=checkbox  (input[type="checkbox"])
  if (sel === 'input[type="checkbox"]') {
    return node.tagName === "INPUT" && node.type === "checkbox";
  }

  return false;
}

class StubStorage {
  constructor() { this._map = new Map(); }
  getItem(k) { return this._map.has(k) ? this._map.get(k) : null; }
  setItem(k, v) { this._map.set(k, String(v)); }
  removeItem(k) { this._map.delete(k); }
  clear() { this._map.clear(); }
  get length() { return this._map.size; }
  key(i) { return [...this._map.keys()][i] ?? null; }
  [Symbol.iterator]() { return this._map.entries(); }
}

class StubDocument {
  constructor() {
    this.body = new StubElement("body");
    this._elements = {};
  }
  createElement(tag) { return new StubElement(tag); }
  getElementById(id) { return this._elements[id] || null; }
  registerElement(el) { if (el.id) this._elements[el.id] = el; }
  querySelectorAll(sel) { return this.body.querySelectorAll(sel); }
  querySelector(sel) { return this.body.querySelector(sel); }
}

const _storageListeners = [];

class StubWindow {
  constructor() { this._listeners = {}; }
  addEventListener(evt, fn) {
    if (evt === "storage") _storageListeners.push(fn);
    if (!this._listeners[evt]) this._listeners[evt] = [];
    this._listeners[evt].push(fn);
  }
  removeEventListener() {}
  dispatchEvent(evt) {
    const handlers = this._listeners[evt.type] || [];
    for (const h of handlers) h(evt);
  }
}

let _orig = {};

export function installDom() {
  _storageListeners.length = 0;
  const doc = new StubDocument();
  const win = new StubWindow();
  const storage = new StubStorage();
  _orig.document = globalThis.document;
  _orig.window = globalThis.window;
  _orig.localStorage = globalThis.localStorage;
  _orig.dispatchEvent = globalThis.dispatchEvent;
  _orig.addEventListener = globalThis.addEventListener;
  globalThis.document = doc;
  globalThis.window = win;
  globalThis.localStorage = storage;
  globalThis.dispatchEvent = (evt) => win.dispatchEvent(evt);
  globalThis.addEventListener = (t, fn) => win.addEventListener(t, fn);
}

export function restoreDom() {
  for (const [k, v] of Object.entries(_orig)) {
    if (v === undefined) delete globalThis[k];
    else globalThis[k] = v;
  }
  _orig = {};
  _storageListeners.length = 0;
}

export function dispatchStorageEvent(key, newValue) {
  const evt = { type: "storage", key, newValue };
  for (const fn of _storageListeners) fn(evt);
}

export function storageListenerCount() {
  return _storageListeners.length;
}

export function makeRow({ away, home }) {
  const el = new StubElement("tr");
  el.dataset.awayTeam = away;
  el.dataset.homeTeam = home;
  return el;
}
