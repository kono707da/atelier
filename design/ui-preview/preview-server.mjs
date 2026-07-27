import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const port = Number(process.env.PORT || 4177);
const types = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".png": "image/png",
  ".webp": "image/webp",
  ".json": "application/json; charset=utf-8",
};

const server = http.createServer((request, response) => {
  const requestUrl = new URL(request.url || "/", `http://${request.headers.host}`);
  const relative = requestUrl.pathname === "/" ? "index.html" : requestUrl.pathname.slice(1);
  const resolved = path.resolve(root, relative);

  if (!resolved.startsWith(root)) {
    response.writeHead(403);
    response.end("Forbidden");
    return;
  }

  fs.readFile(resolved, (error, content) => {
    if (error) {
      response.writeHead(error.code === "ENOENT" ? 404 : 500);
      response.end(error.code === "ENOENT" ? "Not found" : "Server error");
      return;
    }
    response.writeHead(200, {
      "Content-Type": types[path.extname(resolved)] || "application/octet-stream",
      "Cache-Control": "no-store",
    });
    response.end(content);
  });
});

server.listen(port, "127.0.0.1", () => {
  console.log(`Atelier UI preview: http://127.0.0.1:${port}`);
});

