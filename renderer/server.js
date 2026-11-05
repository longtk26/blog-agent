// Diagram renderer (Epic 7, reworked in E10-S1).
//
//   POST /render/drawio   {xml}  -> {svg, png_base64, sha256}   draw.io desktop CLI, diagram XML embedded in both
//   POST /render/mermaid  {code} -> {svg, png_base64, sha256}   mermaid-cli
//   GET  /health                  -> 200 once a draw.io smoke export has succeeded, 503 otherwise
//
// Internal only (no host port). Every render has a timeout, at most MAX_CONCURRENT run at once, inputs and outputs
// are size-capped and SVGs are sanitised. The API sanitises again on its side.
const http = require("http");
const fs = require("fs");
const path = require("path");
const os = require("os");
const crypto = require("crypto");
const { execFile } = require("child_process");

const PORT = process.env.PORT || 8080;
const MAX_CONCURRENT = Number(process.env.MAX_CONCURRENT || 2);
const TIMEOUT_MS = Number(process.env.RENDER_TIMEOUT_MS || 30000);
const MAX_BODY_BYTES = 2 * 1024 * 1024; // 2 MB in
const MAX_OUTPUT_BYTES = 2 * 1024 * 1024; // 2 MB out, per file
const DRAWIO_BIN = process.env.DRAWIO_BIN || "/opt/drawio/drawio";
// Electron flags: containers have no usable sandbox or GPU.
const ELECTRON_FLAGS = ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"];

let activeRenders = 0;
const waitQueue = [];
let drawioReady = false;
let drawioError = "smoke export not run yet";

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
    waitQueue.shift()();
  } else {
    activeRenders = Math.max(0, activeRenders - 1);
  }
}

function sanitizeSvg(svg) {
  if (!svg) return "";
  let cleaned = svg.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "");
  cleaned = cleaned.replace(/<script[^>]*\/>/gi, "");
  cleaned = cleaned.replace(/\s+on[a-z]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi, "");
  cleaned = cleaned.replace(/(href|xlink:href)\s*=\s*(?:"javascript:[^"]*"|'javascript:[^']*'|javascript:[^\s>]+)/gi, "");
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
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf-8") || "{}"));
      } catch (err) {
        reject(new Error("INVALID_JSON"));
      }
    });
    req.on("error", (err) => reject(err));
  });
}

function run(bin, args, timeoutMs) {
  return new Promise((resolve, reject) => {
    execFile(bin, args, { timeout: timeoutMs, maxBuffer: 4 * 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) {
        const reason = err.killed ? `timed out after ${timeoutMs} ms` : (stderr || stdout || err.message);
        return reject(new Error(String(reason).trim().slice(0, 1000)));
      }
      resolve({ stdout, stderr });
    });
  });
}

function readCapped(file) {
  const size = fs.statSync(file).size;
  if (size > MAX_OUTPUT_BYTES) {
    throw new Error(`OUTPUT_TOO_LARGE: ${path.basename(file)} is ${size} bytes`);
  }
  return fs.readFileSync(file);
}

// --- draw.io ------------------------------------------------------------------------------------

async function drawioExport(input, output, format, deadline) {
  // --theme light: export exactly the colours in the file. The default "auto" wraps SVG colours in CSS
  // light-dark(), which flips our dark diagrams to a light background for readers in dark mode.
  const args = ["-x", "-f", format, "-e", "-b", "10", "--theme", "light"];
  if (format === "png") args.push("-s", "2");
  // SVG: embed referenced images, but not fonts. Embedded fonts add a raster per label (~7x the file size);
  // labels render in the reader's Helvetica/Arial instead.
  if (format === "svg") args.push("--embed-svg-images", "--embed-svg-fonts", "false");
  args.push("-o", output, input, ...ELECTRON_FLAGS);
  const remaining = Math.max(1000, deadline - Date.now());
  await run(DRAWIO_BIN, args, remaining);
  if (!fs.existsSync(output)) {
    throw new Error(`draw.io produced no ${format} output`);
  }
}

async function renderDrawio(xml) {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "drawio-"));
  const input = path.join(tmpDir, "diagram.drawio");
  const svgOut = path.join(tmpDir, "diagram.svg");
  const pngOut = path.join(tmpDir, "diagram.png");
  const deadline = Date.now() + TIMEOUT_MS;
  try {
    fs.writeFileSync(input, xml, "utf-8");
    await drawioExport(input, svgOut, "svg", deadline);
    await drawioExport(input, pngOut, "png", deadline);
    const svg = sanitizeSvg(readCapped(svgOut).toString("utf-8"));
    const png = readCapped(pngOut);
    return {
      svg,
      png_base64: png.toString("base64"),
      sha256: crypto.createHash("sha256").update(svg).digest("hex"),
    };
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

const SMOKE_XML =
  '<mxfile><diagram id="smoke" name="smoke"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>' +
  '<mxCell id="a" value="ok" style="rounded=1;" vertex="1" parent="1"><mxGeometry x="0" y="0" width="80" height="40" as="geometry"/></mxCell>' +
  "</root></mxGraphModel></diagram></mxfile>";

async function smokeTest() {
  if (!fs.existsSync(DRAWIO_BIN)) {
    drawioError = `draw.io binary not found at ${DRAWIO_BIN}`;
    return;
  }
  // Xvfb may still be starting; retry a few times before giving up.
  for (let attempt = 1; attempt <= 5; attempt++) {
    try {
      const out = await renderDrawio(SMOKE_XML);
      if (!out.svg.includes("<svg")) throw new Error("smoke export returned no <svg>");
      drawioReady = true;
      drawioError = null;
      console.log(`draw.io smoke export ok (attempt ${attempt})`);
      return;
    } catch (err) {
      drawioError = err.message;
      console.error(`draw.io smoke export failed (attempt ${attempt}): ${err.message}`);
      await new Promise((r) => setTimeout(r, 1500));
    }
  }
}

// --- mermaid ------------------------------------------------------------------------------------

function mmdcArgs(input, output, extra = []) {
  const args = ["-i", input, "-o", output, "-t", "dark", ...extra];
  if (fs.existsSync("/puppeteer-config.json")) args.push("-p", "/puppeteer-config.json");
  return args;
}

// --- routes -------------------------------------------------------------------------------------

function errorStatus(err) {
  if (err.message === "PAYLOAD_TOO_LARGE") return [413, "PAYLOAD_TOO_LARGE"];
  if (err.message === "INVALID_JSON") return [400, "INVALID_JSON"];
  if (err.message.startsWith("OUTPUT_TOO_LARGE")) return [422, "OUTPUT_TOO_LARGE"];
  return null;
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);

  if (req.method === "GET" && url.pathname === "/health") {
    if (drawioReady) return jsonResponse(res, 200, { status: "ok", drawio: true });
    return jsonResponse(res, 503, { status: "unavailable", drawio: false, error: drawioError });
  }

  if (req.method === "POST" && url.pathname === "/render/drawio") {
    await acquireSlot();
    try {
      const body = await parseJsonBody(req);
      const xml = (body.xml || "").trim();
      if (!xml.startsWith("<mxfile") && !xml.startsWith("<mxGraphModel")) {
        return jsonResponse(res, 400, { error: "MISSING_XML", message: "draw.io XML (<mxfile>) is required" });
      }
      return jsonResponse(res, 200, await renderDrawio(xml));
    } catch (err) {
      const known = errorStatus(err);
      if (known) return jsonResponse(res, known[0], { error: known[1], message: err.message });
      return jsonResponse(res, 422, { error: "DRAWIO_RENDER_ERROR", message: err.message });
    } finally {
      releaseSlot();
    }
  }

  if (req.method === "POST" && url.pathname === "/render/mermaid") {
    await acquireSlot();
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "mmd-"));
    const input = path.join(tmpDir, "chart.mmd");
    const svgOut = path.join(tmpDir, "chart.svg");
    const pngOut = path.join(tmpDir, "chart.png");
    try {
      const body = await parseJsonBody(req);
      const code = (body.code || "").trim();
      if (!code) {
        return jsonResponse(res, 400, { error: "MISSING_CODE", message: "Diagram code is required" });
      }
      fs.writeFileSync(input, code, "utf-8");
      await run("mmdc", mmdcArgs(input, svgOut), TIMEOUT_MS);

      let pngBase64 = null;
      try {
        await run("mmdc", mmdcArgs(input, pngOut, ["-s", "2"]), TIMEOUT_MS);
        if (fs.existsSync(pngOut)) pngBase64 = readCapped(pngOut).toString("base64");
      } catch (pngErr) {
        // PNG is best-effort; the SVG is the primary output.
      }

      const svg = sanitizeSvg(readCapped(svgOut).toString("utf-8"));
      return jsonResponse(res, 200, {
        svg,
        png_base64: pngBase64,
        sha256: crypto.createHash("sha256").update(svg).digest("hex"),
      });
    } catch (err) {
      const known = errorStatus(err);
      if (known) return jsonResponse(res, known[0], { error: known[1], message: err.message });
      return jsonResponse(res, 400, { error: "MERMAID_SYNTAX_ERROR", message: err.message });
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
      releaseSlot();
    }
  }

  jsonResponse(res, 404, { error: "NOT_FOUND" });
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Diagram renderer listening on port ${PORT}`);
  smokeTest();
});
