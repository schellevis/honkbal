import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOTS = [
  path.resolve(__dirname, "fixtures"),
  path.resolve(__dirname, "../../frontend"),
  // Production serveert de service worker op /sw.js (root), maar de bron staat in
  // frontend/js/sw.js. Voeg frontend/js toe als root zodat /sw.js (en /js/*.js via
  // de frontend-root) net als in productie resolven.
  path.resolve(__dirname, "../js"),
  path.resolve(__dirname, "../static"),
];

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".svg": "image/svg+xml",
};

const PORT = process.env.PORT || 4173;

const server = http.createServer((req, res) => {
  let urlPath = req.url.split("?")[0];
  if (urlPath === "/" || urlPath === "") urlPath = "/index.html";

  // Resolve against roots in order
  let filePath = null;
  for (const root of ROOTS) {
    const candidate = path.join(root, urlPath);
    // Security: ensure it stays within root
    if (!candidate.startsWith(root)) continue;
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
      filePath = candidate;
      break;
    }
  }

  if (!filePath) {
    res.writeHead(404);
    res.end("Not found");
    return;
  }

  const ext = path.extname(filePath);
  const mime = MIME[ext] || "application/octet-stream";
  res.writeHead(200, {
    "Content-Type": mime,
    "Service-Worker-Allowed": "/",
    "Cache-Control": "no-store",
  });
  fs.createReadStream(filePath).pipe(res);
});

server.listen(PORT, () => {
  console.log(`Static server running at http://localhost:${PORT}`);
});
