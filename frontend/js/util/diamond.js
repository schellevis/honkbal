export function basesSvg(onFirst, onSecond, onThird) {
  // Diamond layout: 2B at top-center, 1B at right, 3B at left
  // viewBox 24x24, each base a rotated rect (diamond shape)
  const base = (cx, cy, occupied) =>
    `<rect x="${cx - 4}" y="${cy - 4}" width="8" height="8" transform="rotate(45,${cx},${cy})" fill="${occupied ? "currentColor" : "none"}" stroke="currentColor" stroke-width="1.5"/>`;

  // viewBox 28×28 met de honken zo geplaatst dat de 45°-geroteerde rects (halve
  // diagonaal √2·8/2 ≈ 5.66 + halve streek) met marge binnen de box blijven.
  // De vorige 24×24-box klipte de buitenpunten van alle drie de honken.
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28" width="20" height="20" class="stp-bases" aria-hidden="true">` +
    base(14, 8, onSecond) +   // 2B: top
    base(21, 16, onFirst) +   // 1B: right
    base(7, 16, onThird) +    // 3B: left
    `</svg>`;
  return svg;
}

export function outsSvg(outs) {
  const circle = (cx, filled) =>
    `<circle cx="${cx}" cy="4" r="3" fill="${filled ? "currentColor" : "none"}" stroke="currentColor" stroke-width="1.5"/>`;

  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 8" width="24" height="8" class="stp-outs" aria-hidden="true">` +
    circle(4, outs >= 1) +
    circle(12, outs >= 2) +
    circle(20, outs >= 3) +
    `</svg>`;
  return svg;
}
