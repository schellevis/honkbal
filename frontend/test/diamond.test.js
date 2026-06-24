import { test } from "node:test";
import assert from "node:assert/strict";
import { basesSvg, outsSvg } from "../js/util/diamond.js";

test("basesSvg with first and third occupied (two filled, one empty)", () => {
  const svg = basesSvg(true, false, true);
  // Count filled diamonds (currentColor) and empty ones (fill="none")
  const filled = (svg.match(/fill="currentColor"/g) || []).length;
  const empty = (svg.match(/fill="none"/g) || []).length;
  assert.equal(filled, 2);
  assert.equal(empty, 1);
  assert.ok(svg.includes("<svg"));
});

test("basesSvg with no runners (all empty)", () => {
  const svg = basesSvg(false, false, false);
  const filled = (svg.match(/fill="currentColor"/g) || []).length;
  assert.equal(filled, 0);
  const empty = (svg.match(/fill="none"/g) || []).length;
  assert.equal(empty, 3);
});

// Regressie: de drie 45°-geroteerde honk-diamanten mogen niet buiten de viewBox
// vallen, anders worden hun punten geklipt (zie scores-badge bug). Een 8×8 rect
// 45° geroteerd reikt vanuit zijn centrum √2·8/2 ≈ 5.66 + half de streekbreedte.
test("basesSvg diamonds fit within the viewBox (no clipping)", () => {
  const svg = basesSvg(true, true, true);
  const vb = svg.match(/viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"/);
  assert.ok(vb, "viewBox van de vorm '0 0 W H'");
  const width = Number(vb[1]);
  const height = Number(vb[2]);

  const rects = [...svg.matchAll(/rotate\(45,\s*([\d.]+),\s*([\d.]+)\)/g)];
  assert.equal(rects.length, 3, "drie honk-rechthoeken");

  // Halve diagonaal van een 8×8 rect + halve streek (1.5) langs de diagonaal.
  const reach = (8 * Math.SQRT2) / 2 + (1.5 / 2) * Math.SQRT2;
  for (const [, cxStr, cyStr] of rects) {
    const cx = Number(cxStr);
    const cy = Number(cyStr);
    assert.ok(cx - reach >= 0, `linkerpunt binnen viewBox (cx=${cx})`);
    assert.ok(cx + reach <= width, `rechterpunt binnen viewBox (cx=${cx})`);
    assert.ok(cy - reach >= 0, `bovenpunt binnen viewBox (cy=${cy})`);
    assert.ok(cy + reach <= height, `onderpunt binnen viewBox (cy=${cy})`);
  }
});

test("outsSvg with 2 outs (two filled, one empty)", () => {
  const svg = outsSvg(2);
  // Filled circles: fill="currentColor"
  const filled = (svg.match(/fill="currentColor"/g) || []).length;
  const empty = (svg.match(/fill="none"/g) || []).length;
  assert.equal(filled, 2);
  assert.equal(empty, 1);
  assert.ok(svg.includes("<svg"));
});

test("outsSvg with 0 outs (all empty)", () => {
  const svg = outsSvg(0);
  const filled = (svg.match(/fill="currentColor"/g) || []).length;
  assert.equal(filled, 0);
});
