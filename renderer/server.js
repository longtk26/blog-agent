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

function drawioXmlToSvg(xml) {
  let width = 1000;
  let height = 700;
  const wMatch = xml.match(/pageWidth="(\d+)"/);
  const hMatch = xml.match(/pageHeight="(\d+)"/);
  if (wMatch) width = Math.max(500, parseInt(wMatch[1], 10));
  if (hMatch) height = Math.max(400, parseInt(hMatch[1], 10));

  const cellRegex = /<mxCell\s+([^>]+?)(?:\/>|>(.*?)<\/mxCell>)/gs;
  const cells = [];
  let match;
  while ((match = cellRegex.exec(xml)) !== null) {
    const attrsStr = match[1];
    const inner = match[2] || "";
    const getAttr = (name) => {
      const m = attrsStr.match(new RegExp(name + '="([^"]*)"'));
      return m ? m[1] : null;
    };
    const id = getAttr("id");
    if (!id || id === "0" || id === "1") continue;

    let value = getAttr("value") || "";
    value = value.replace(/&#xa;/g, "\n").replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">");

    const style = getAttr("style") || "";
    const vertex = getAttr("vertex") === "1";
    const edge = getAttr("edge") === "1";
    const parent = getAttr("parent") || "1";
    const container = getAttr("container") === "1" || style.includes("swimlane");
    const source = getAttr("source");
    const target = getAttr("target");

    let x = 0, y = 0, cellW = 140, cellH = 60;
    const geomMatch = inner.match(/<mxGeometry\s+([^>]+?)\/?>/);
    if (geomMatch) {
      const gStr = geomMatch[1];
      const gAttr = (name) => {
        const m = gStr.match(new RegExp(name + '="([^"]*)"'));
        return m ? parseFloat(m[1]) : null;
      };
      if (gAttr("x") !== null) x = gAttr("x");
      if (gAttr("y") !== null) y = gAttr("y");
      if (gAttr("width") !== null) cellW = gAttr("width");
      if (gAttr("height") !== null) cellH = gAttr("height");
    }
    cells.push({ id, value, style, vertex, edge, parent, container, source, target, x, y, width: cellW, height: cellH });
  }

  const cellMap = new Map();
  for (const c of cells) {
    cellMap.set(c.id, c);
  }

  for (const c of cells) {
    if (!c.vertex) continue;
    let absX = c.x;
    let absY = c.y;
    let currParentId = c.parent;
    let visited = new Set();
    while (currParentId && currParentId !== "1" && currParentId !== "0" && cellMap.has(currParentId)) {
      if (visited.has(currParentId)) break;
      visited.add(currParentId);
      const p = cellMap.get(currParentId);
      absX += p.x;
      absY += p.y;
      currParentId = p.parent;
    }
    c.absX = absX;
    c.absY = absY;
  }

  let maxX = width;
  let maxY = height;
  for (const c of cells) {
    if (c.vertex) {
      maxX = Math.max(maxX, c.absX + c.width + 50);
      maxY = Math.max(maxY, c.absY + c.height + 50);
    }
  }
  width = Math.max(width, maxX);
  height = Math.max(height, maxY);

  const escapeSvg = (str) => String(str).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const escapedXml = xml.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const getStyleVal = (style, key, fallback) => {
    const m = style.match(new RegExp(key + "=([^;]+)"));
    return m ? m[1] : fallback;
  };

  function getAwsIconInfo(style, value) {
    const lowerVal = (value || "").toLowerCase();
    const lowerStyle = (style || "").toLowerCase();

    if (lowerStyle.includes("ec2") || lowerVal.includes("ec2") || lowerVal.includes("virtual machine") || lowerVal.includes("instance") || (lowerVal.includes("server") && !lowerVal.includes("lambda"))) {
      return { name: "AWS EC2", color: "#FF9900", icon: "ec2" };
    }
    if (lowerStyle.includes("bucket") || lowerStyle.includes("s3") || lowerVal.includes("s3") || lowerVal.includes("bucket")) {
      return { name: "AWS S3", color: "#7AA116", icon: "s3" };
    }
    if (lowerStyle.includes("rds") || lowerVal.includes("rds") || lowerVal.includes("postgres") || lowerVal.includes("mysql") || lowerVal.includes("aurora") || lowerVal.includes("database")) {
      return { name: "AWS RDS", color: "#3B48CC", icon: "rds" };
    }
    if (lowerStyle.includes("dynamodb") || lowerVal.includes("dynamo") || lowerVal.includes("nosql")) {
      return { name: "AWS DynamoDB", color: "#3B48CC", icon: "dynamodb" };
    }
    if (lowerStyle.includes("lambda") || lowerVal.includes("lambda") || lowerVal.includes("serverless") || lowerVal.includes("function")) {
      return { name: "AWS Lambda", color: "#FF9900", icon: "lambda" };
    }
    if (lowerStyle.includes("cloudfront") || lowerVal.includes("cloudfront") || lowerVal.includes("cdn")) {
      return { name: "AWS CloudFront", color: "#8C4FFF", icon: "cloudfront" };
    }
    if (lowerStyle.includes("application_load_balancer") || lowerStyle.includes("alb") || lowerVal.includes("alb") || lowerVal.includes("load balancer") || lowerVal.includes("elb")) {
      return { name: "AWS ALB", color: "#8C4FFF", icon: "alb" };
    }
    if (lowerStyle.includes("nat_gateway") || lowerStyle.includes("nat") || lowerVal.includes("nat gateway") || lowerVal.includes("nat")) {
      return { name: "AWS NAT", color: "#8C4FFF", icon: "nat" };
    }
    if (lowerStyle.includes("internet_gateway") || lowerStyle.includes("igw") || lowerVal.includes("internet gateway") || lowerVal.includes("igw")) {
      return { name: "AWS IGW", color: "#8C4FFF", icon: "igw" };
    }
    if (lowerStyle.includes("eventbridge") || lowerVal.includes("eventbridge") || lowerVal.includes("event bridge")) {
      return { name: "AWS EventBridge", color: "#E7157B", icon: "eventbridge" };
    }
    if (lowerStyle.includes("sqs") || lowerVal.includes("sqs") || lowerVal.includes("queue")) {
      return { name: "AWS SQS", color: "#E7157B", icon: "sqs" };
    }
    if (lowerStyle.includes("user") || lowerVal.includes("user") || lowerVal.includes("client") || lowerVal.includes("browser")) {
      return { name: "User", color: "#94A3B8", icon: "user" };
    }
    return null;
  }

  function renderAwsIconSvg(icon, color) {
    switch (icon) {
      case "ec2":
        return `<rect x="2" y="3" width="20" height="18" rx="3" fill="none" stroke="${color}" stroke-width="2"/>
                <line x1="6" y1="8" x2="18" y2="8" stroke="${color}" stroke-width="1.5"/>
                <line x1="6" y1="13" x2="18" y2="13" stroke="${color}" stroke-width="1.5"/>
                <line x1="6" y1="18" x2="14" y2="18" stroke="${color}" stroke-width="1.5"/>
                <circle cx="17" cy="18" r="1.5" fill="${color}"/>`;
      case "s3":
        return `<ellipse cx="12" cy="6" rx="9" ry="3.5" fill="${color}" fill-opacity="0.3" stroke="${color}" stroke-width="2"/>
                <path d="M 3 6 V 18 C 3 20 21 20 21 18 V 6" fill="none" stroke="${color}" stroke-width="2"/>
                <path d="M 3 12 C 3 14 21 14 21 12" fill="none" stroke="${color}" stroke-width="1.5"/>`;
      case "rds":
      case "dynamodb":
        return `<ellipse cx="12" cy="5" rx="8" ry="3" fill="${color}" fill-opacity="0.3" stroke="${color}" stroke-width="2"/>
                <path d="M 4 5 V 19 C 4 21.5 20 21.5 20 19 V 5" fill="none" stroke="${color}" stroke-width="2"/>
                <path d="M 4 10 C 4 12 20 12 20 10" fill="none" stroke="${color}" stroke-width="1.5"/>
                <path d="M 4 15 C 4 17 20 17 20 15" fill="none" stroke="${color}" stroke-width="1.5"/>`;
      case "lambda":
        return `<circle cx="12" cy="12" r="10" fill="${color}" fill-opacity="0.2" stroke="${color}" stroke-width="2"/>
                <path d="M 7 18 L 11 9 L 14 18 M 10.5 10 L 17 6" fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>`;
      case "cloudfront":
        return `<circle cx="12" cy="12" r="9" fill="${color}" fill-opacity="0.2" stroke="${color}" stroke-width="2"/>
                <ellipse cx="12" cy="12" rx="4" ry="9" fill="none" stroke="${color}" stroke-width="1.5"/>
                <line x1="3" y1="12" x2="21" y2="12" stroke="${color}" stroke-width="1.5"/>`;
      case "alb":
        return `<rect x="3" y="9" width="18" height="6" rx="2" fill="${color}" fill-opacity="0.3" stroke="${color}" stroke-width="2"/>
                <path d="M 12 3 L 12 9 M 7 15 L 7 21 M 17 15 L 17 21" stroke="${color}" stroke-width="2" stroke-linecap="round"/>`;
      case "nat":
      case "igw":
        return `<path d="M 4 20 V 9 A 8 8 0 0 1 20 9 V 20" fill="${color}" fill-opacity="0.2" stroke="${color}" stroke-width="2"/>
                <line x1="8" y1="15" x2="16" y2="15" stroke="${color}" stroke-width="2" stroke-linecap="round"/>
                <path d="M 10 12 L 12 14 L 10 16 M 14 12 L 12 14 L 14 16" fill="none" stroke="${color}" stroke-width="1.5"/>`;
      case "eventbridge":
      case "sqs":
        return `<rect x="3" y="6" width="18" height="12" rx="2" fill="${color}" fill-opacity="0.2" stroke="${color}" stroke-width="2"/>
                <path d="M 3 8 L 12 13 L 21 8" fill="none" stroke="${color}" stroke-width="1.5"/>`;
      case "user":
        return `<circle cx="12" cy="7" r="4" fill="${color}" fill-opacity="0.3" stroke="${color}" stroke-width="2"/>
                <path d="M 5 19 C 5 15 8 13 12 13 C 16 13 19 15 19 19" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round"/>`;
      default:
        return `<circle cx="12" cy="12" r="8" fill="${color}" fill-opacity="0.2" stroke="${color}" stroke-width="2"/>`;
    }
  }

  const svgElements = [];
  svgElements.push(`<rect width="100%" height="100%" fill="#0B0F19" rx="10" />`);

  // Containers / Groups
  for (const c of cells) {
    if (!c.vertex || !c.container) continue;
    let stroke = getStyleVal(c.style, "strokeColor", "#334155");
    let fill = getStyleVal(c.style, "fillColor", "#0F172A");
    const lowerVal = (c.value || "").toLowerCase();
    let badgeText = "";
    if (lowerVal.includes("vpc")) {
      stroke = "#8C4FFF";
      badgeText = "VPC";
    } else if (lowerVal.includes("public")) {
      stroke = "#22C55E";
      badgeText = "PUBLIC";
    } else if (lowerVal.includes("private")) {
      stroke = "#3B82F6";
      badgeText = "PRIVATE";
    }

    svgElements.push(`
      <g id="group_${c.id}">
        <rect x="${c.absX}" y="${c.absY}" width="${c.width}" height="${c.height}" rx="8" fill="${fill}" fill-opacity="0.7" stroke="${stroke}" stroke-width="1.8" stroke-dasharray="5,4" />
        <rect x="${c.absX}" y="${c.absY}" width="${c.width}" height="28" rx="8" fill="${stroke}" fill-opacity="0.25" />
        <text x="${c.absX + 12}" y="${c.absY + 18}" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="700" fill="#F8FAFC">${escapeSvg(c.value.split("\n")[0])}</text>
        ${badgeText ? `<rect x="${c.absX + c.width - 65}" y="${c.absY + 6}" width="55" height="16" rx="4" fill="${stroke}" fill-opacity="0.4" />
        <text x="${c.absX + c.width - 37}" y="${c.absY + 17}" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="9" font-weight="800" fill="#F8FAFC">${badgeText}</text>` : ""}
      </g>`);
  }

  // Edges
  for (const e of cells) {
    if (!e.edge) continue;
    const src = cellMap.get(e.source);
    const tgt = cellMap.get(e.target);
    if (!src || !tgt) continue;

    const srcCx = src.absX + src.width / 2;
    const srcCy = src.absY + src.height / 2;
    const tgtCx = tgt.absX + tgt.width / 2;
    const tgtCy = tgt.absY + tgt.height / 2;

    let x1, y1, x2, y2;
    if (Math.abs(tgtCx - srcCx) >= Math.abs(tgtCy - srcCy)) {
      if (tgtCx >= srcCx) {
        x1 = src.absX + src.width;
        y1 = srcCy;
        x2 = tgt.absX;
        y2 = tgtCy;
      } else {
        x1 = src.absX;
        y1 = srcCy;
        x2 = tgt.absX + tgt.width;
        y2 = tgtCy;
      }
    } else {
      if (tgtCy >= srcCy) {
        x1 = srcCx;
        y1 = src.absY + src.height;
        x2 = tgtCx;
        y2 = tgt.absY;
      } else {
        x1 = srcCx;
        y1 = src.absY;
        x2 = tgtCx;
        y2 = tgt.absY + tgt.height;
      }
    }

    const stroke = getStyleVal(e.style, "strokeColor", "#94A3B8");
    const isDashed = e.style.includes("dashed=1");
    const midX = (x1 + x2) / 2;
    const midY = (y1 + y2) / 2;
    const pathD = `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`;

    svgElements.push(`
      <g id="edge_${e.id}">
        <path d="${pathD}" fill="none" stroke="${stroke}" stroke-width="2" ${isDashed ? 'stroke-dasharray="5,4"' : ""} marker-end="url(#arrow)" />
        ${e.value ? `
          <g transform="translate(${midX}, ${midY})">
            <rect x="-${Math.min(90, Math.max(30, e.value.length * 4))}" y="-10" width="${Math.min(180, Math.max(60, e.value.length * 8))}" height="20" rx="4" fill="#0F172A" stroke="#334155" stroke-width="1" />
            <text x="0" y="3.5" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" fill="#E2E8F0">${escapeSvg(e.value)}</text>
          </g>` : ""}
      </g>`);
  }

  // Nodes
  for (const c of cells) {
    if (!c.vertex || c.container) continue;
    const aws = getAwsIconInfo(c.style, c.value);
    const stroke = aws ? aws.color : getStyleVal(c.style, "strokeColor", "#38BDF8");
    const fill = getStyleVal(c.style, "fillColor", "#1E293B");
    const rawLines = c.value.split("\n").map(l => l.trim()).filter(Boolean);

    if (aws) {
      const badgeSize = 34;
      const badgeX = c.absX + 10;
      const badgeY = c.absY + (c.height - badgeSize) / 2;
      const textX = c.absX + badgeSize + 18;
      
      const cleanLines = rawLines.map(l => l.replace(/\[AWS\s+[^\]]+\]/gi, "").trim()).filter(Boolean);
      let title = aws.name;
      let subtitle = "";
      if (cleanLines.length > 0) {
        if (!cleanLines[0].toLowerCase().includes(aws.name.toLowerCase().replace("aws ", ""))) {
          title = `${aws.name} (${cleanLines[0]})`;
        }
        if (cleanLines.length > 1) {
          subtitle = cleanLines.slice(1).join(" ");
        } else if (!title.includes(cleanLines[0])) {
          subtitle = cleanLines[0];
        }
      }

      svgElements.push(`
        <g id="node_${c.id}">
          <rect x="${c.absX}" y="${c.absY}" width="${c.width}" height="${c.height}" rx="8" fill="${fill}" stroke="${stroke}" stroke-width="2" filter="url(#node-shadow)" />
          <rect x="${badgeX}" y="${badgeY}" width="${badgeSize}" height="${badgeSize}" rx="6" fill="${aws.color}" fill-opacity="0.15" stroke="${aws.color}" stroke-opacity="0.6" stroke-width="1.5" />
          <g transform="translate(${badgeX + (badgeSize - 24) / 2}, ${badgeY + (badgeSize - 24) / 2})">
            ${renderAwsIconSvg(aws.icon, aws.color)}
          </g>
          <text x="${textX}" y="${c.absY + c.height / 2 - (subtitle ? 3 : -4)}" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="700" fill="#F8FAFC">${escapeSvg(title)}</text>
          ${subtitle ? `<text x="${textX}" y="${c.absY + c.height / 2 + 13}" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="10.5" font-weight="500" fill="#94A3B8">${escapeSvg(subtitle)}</text>` : ""}
        </g>`);
    } else {
      const lineHeight = 16;
      const totalTextH = rawLines.length * lineHeight;
      const startY = c.absY + (c.height - totalTextH) / 2 + 12;

      const tspans = rawLines.map((line, idx) => {
        const isBold = idx === 0 && rawLines.length > 1;
        return `<tspan x="${c.absX + c.width / 2}" dy="${idx === 0 ? 0 : lineHeight}" font-weight="${isBold ? "700" : "500"}" fill="${isBold ? "#F8FAFC" : "#CBD5E1"}">${escapeSvg(line)}</tspan>`;
      }).join("");

      svgElements.push(`
        <g id="node_${c.id}">
          <rect x="${c.absX}" y="${c.absY}" width="${c.width}" height="${c.height}" rx="8" fill="${fill}" stroke="${stroke}" stroke-width="2" filter="url(#node-shadow)" />
          <text x="${c.absX + c.width / 2}" y="${startY}" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12">
            ${tspans}
          </text>
        </g>`);
    }
  }

  return `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1" width="100%" height="100%" viewBox="0 0 ${width} ${height}" content="${escapedXml}">
  <defs>
    <filter id="node-shadow" x="-10%" y="-10%" width="120%" height="130%">
      <feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#000000" flood-opacity="0.4"/>
    </filter>
    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#94A3B8"/>
    </marker>
  </defs>
  ${svgElements.join("\n")}
</svg>`;
}

  // Rasterise an SVG produced by the API (generated diagrams are laid out and drawn in Python).
  if (req.method === "POST" && url.pathname === "/render/png") {
    await acquireSlot();
    let browser;
    try {
      const body = await parseJsonBody(req);
      const svg = sanitizeSvg((body.svg || "").trim());
      if (!svg.startsWith("<svg")) {
        return jsonResponse(res, 400, { error: "MISSING_SVG", message: "An <svg> document is required" });
      }
      const scale = Math.min(3, Math.max(1, Number(body.scale) || 2));
      const puppeteer = require("/home/mermaidcli/node_modules/puppeteer");
      browser = await puppeteer.launch({
        executablePath: "/usr/bin/chromium",
        args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
      });
      const page = await browser.newPage();
      await page.setViewport({ width: 800, height: 600, deviceScaleFactor: scale });
      await page.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`);
      const element = await page.$("svg");
      const pngBuf = await element.screenshot({ type: "png", omitBackground: true });
      return jsonResponse(res, 200, { png_base64: pngBuf.toString("base64") });
    } catch (err) {
      if (err.message === "PAYLOAD_TOO_LARGE") {
        return jsonResponse(res, 413, { error: "PAYLOAD_TOO_LARGE", message: "Payload exceeds 2MB limit" });
      }
      return jsonResponse(res, 400, { error: "PNG_RENDER_ERROR", message: err.message });
    } finally {
      if (browser) await browser.close().catch(() => {});
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

      let svg = drawioXmlToSvg(xml);
      svg = sanitizeSvg(svg);

      let pngBase64 = null;
      try {
        const puppeteer = require("/home/mermaidcli/node_modules/puppeteer");
        const browser = await puppeteer.launch({
          executablePath: "/usr/bin/chromium",
          args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        });
        const page = await browser.newPage();
        await page.setContent(svg);
        const pngBuf = await page.screenshot({ type: "png", omitBackground: false });
        pngBase64 = pngBuf.toString("base64");
        await browser.close();
      } catch (pngErr) {
        console.error("Puppeteer PNG error:", pngErr.message);
      }

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
