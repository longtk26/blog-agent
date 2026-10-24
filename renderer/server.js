const http = require("http");
const fs = require("fs");
const path = require("path");
const os = require("os");
const crypto = require("crypto");
const { execFile } = require("child_process");

const PORT = process.env.PORT || 8080;
const MAX_CONCURRENT = 2;
const TIMEOUT_MS = 30000;
const MAX_BODY_BYTES = 2 * 1024 * 1024; // 2MB

let activeRenders = 0;
const waitQueue = [];

function acquireSlot() {
  return new Promise((resolve) => {
    if (activeRenders < MAX_CONCURRENT) {
      activeRenders++;
      resolve();
    } else {
      waitQueue.push(resolve);
    }
  });
}

function releaseSlot() {
  if (waitQueue.length > 0) {
    const next = waitQueue.shift();
    next();
  } else {
    activeRenders = Math.max(0, activeRenders - 1);
  }
}

function sanitizeSvg(svg) {
  if (!svg) return "";
  // 1. Remove <script> tags
  let cleaned = svg.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "");
  cleaned = cleaned.replace(/<script[^>]*\/>/gi, "");
  // 2. Remove on* event handlers
  cleaned = cleaned.replace(/\s+on[a-z]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi, "");
  // 3. Remove javascript: pseudo-protocol
  cleaned = cleaned.replace(/(href|xlink:href)\s*=\s*(?:"javascript:[^"]*"|'javascript:[^']*'|javascript:[^\s>]+)/gi, "");
  // 4. Strip external hrefs
  cleaned = cleaned.replace(/(href|xlink:href)\s*=\s*["']([^"']+)["']/gi, (match, attr, url) => {
    if (url.startsWith("#") || url.startsWith("data:image/")) {
      return `${attr}="${url}"`;
    }
    return `${attr}="#"`;
  });
  return cleaned;
}

function jsonResponse(res, statusCode, data) {
  const body = JSON.stringify(data);
  res.writeHead(statusCode, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(body),
  });
  res.end(body);
}

function parseJsonBody(req) {
  return new Promise((resolve, reject) => {
    let bytesReceived = 0;
    const chunks = [];

    req.on("data", (chunk) => {
      bytesReceived += chunk.length;
      if (bytesReceived > MAX_BODY_BYTES) {
        reject(new Error("PAYLOAD_TOO_LARGE"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });

    req.on("end", () => {
      try {
        const bodyStr = Buffer.concat(chunks).toString("utf-8");
        const parsed = JSON.parse(bodyStr || "{}");
        resolve(parsed);
      } catch (err) {
        reject(new Error("INVALID_JSON"));
      }
    });

    req.on("error", (err) => reject(err));
  });
}

function runMmdc(args) {
  return new Promise((resolve, reject) => {
    const proc = execFile("mmdc", args, { timeout: TIMEOUT_MS }, (err, stdout, stderr) => {
      if (err) {
        const msg = (stderr || stdout || err.message).trim();
        return reject(new Error(msg));
      }
      resolve({ stdout, stderr });
    });
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);

  if (req.method === "GET" && url.pathname === "/health") {
    return jsonResponse(res, 200, { status: "ok" });
  }

  if (req.method === "POST" && url.pathname === "/render/mermaid") {
    await acquireSlot();
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "mmd-"));
    const inputFile = path.join(tmpDir, "chart.mmd");
    const outputSvg = path.join(tmpDir, "chart.svg");
    const outputPng = path.join(tmpDir, "chart.png");

    try {
      const body = await parseJsonBody(req);
      const code = (body.code || "").trim();
      if (!code) {
        return jsonResponse(res, 400, { error: "MISSING_CODE", message: "Diagram code is required" });
      }

      fs.writeFileSync(inputFile, code, "utf-8");

      // 1. Render SVG
      const mmdcArgsSvg = ["-i", inputFile, "-o", outputSvg, "-t", "dark"];
      if (fs.existsSync("/puppeteer-config.json")) {
        mmdcArgsSvg.push("-p", "/puppeteer-config.json");
      }
      await runMmdc(mmdcArgsSvg);

      // 2. Render PNG (2x scale)
      let pngBase64 = null;
      try {
        const mmdcArgsPng = ["-i", inputFile, "-o", outputPng, "-s", "2", "-t", "dark"];
        if (fs.existsSync("/puppeteer-config.json")) {
          mmdcArgsPng.push("-p", "/puppeteer-config.json");
        }
        await runMmdc(mmdcArgsPng);
        if (fs.existsSync(outputPng)) {
          pngBase64 = fs.readFileSync(outputPng).toString("base64");
        }
      } catch (pngErr) {
        // PNG export is optional/best-effort
      }

      const rawSvg = fs.readFileSync(outputSvg, "utf-8");
      const cleanSvg = sanitizeSvg(rawSvg);
      const sha256 = crypto.createHash("sha256").update(cleanSvg).digest("hex");

      return jsonResponse(res, 200, {
        svg: cleanSvg,
        png_base64: pngBase64,
        sha256: sha256,
      });
    } catch (err) {
      if (err.message === "PAYLOAD_TOO_LARGE") {
        return jsonResponse(res, 413, { error: "PAYLOAD_TOO_LARGE", message: "Payload exceeds 2MB limit" });
      }
      return jsonResponse(res, 400, { error: "MERMAID_SYNTAX_ERROR", message: err.message });
    } finally {
      try {
        fs.rmSync(tmpDir, { recursive: true, force: true });
      } catch (cleanupErr) {}
      releaseSlot();
    }
  }

  if (req.method === "POST" && url.pathname === "/render/drawio") {
    await acquireSlot();
    try {
      const body = await parseJsonBody(req);
      const xml = (body.xml || "").trim();
      if (!xml) {
        return jsonResponse(res, 400, { error: "MISSING_XML", message: "XML content is required" });
      }

      // Check if drawio desktop CLI is available
      let svg = "";
      let pngBase64 = null;

      // Extract width, height and generate SVG embedding the diagram XML
      const escapedXml = xml.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      
      // Parse width/height if available in mxGraphModel
      let width = 1200;
      let height = 800;
      const wMatch = xml.match(/pageWidth="(\d+)"/);
      const hMatch = xml.match(/pageHeight="(\d+)"/);
      if (wMatch) width = Math.max(400, parseInt(wMatch[1], 10));
      if (hMatch) height = Math.max(300, parseInt(hMatch[1], 10));

      svg = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1" width="100%" height="100%" viewBox="0 0 ${width} ${height}" content="${escapedXml}">
  <defs>
    <style>
      .title { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 20px; font-weight: bold; fill: #F8FAFC; }
      .box { rx: 6; stroke-width: 2; }
      .text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 13px; fill: #F8FAFC; }
    </style>
  </defs>
  <rect width="100%" height="100%" fill="#0F172A" rx="8" />
  <text x="50%" y="50%" class="text" text-anchor="middle" dominant-baseline="middle" fill="#94A3B8">draw.io diagram embedded (opens in diagrams.net)</text>
</svg>`;

      svg = sanitizeSvg(svg);
      const sha256 = crypto.createHash("sha256").update(svg).digest("hex");

      return jsonResponse(res, 200, {
        svg: svg,
        png_base64: pngBase64,
        sha256: sha256,
      });
    } catch (err) {
      if (err.message === "PAYLOAD_TOO_LARGE") {
        return jsonResponse(res, 413, { error: "PAYLOAD_TOO_LARGE", message: "Payload exceeds 2MB limit" });
      }
      return jsonResponse(res, 400, { error: "DRAWIO_RENDER_ERROR", message: err.message });
    } finally {
      releaseSlot();
    }
  }

  jsonResponse(res, 404, { error: "NOT_FOUND" });
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Diagram renderer listening on port ${PORT}`);
});
