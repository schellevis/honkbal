export function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function el(tag, attrs = {}, children = []) {
  const parts = [`<${tag}`];
  for (const [k, v] of Object.entries(attrs)) {
    parts.push(` ${k}="${escapeHtml(v)}"`);
  }
  parts.push(">");
  for (const c of children) parts.push(c);
  parts.push(`</${tag}>`);
  return parts.join("");
}
