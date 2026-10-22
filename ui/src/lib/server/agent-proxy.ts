import "server-only";

import type { TApiErrorBody } from "@/types/api";

// Server-only settings, read at request time (never NEXT_PUBLIC_, so they are not baked into the bundle).
function backendUrl() {
  return (process.env.AGENT_API_URL ?? "http://127.0.0.1:8100").replace(/\/+$/, "");
}

const FORWARDED_REQUEST_HEADERS = ["accept", "content-type", "last-event-id", "x-request-id"];
const FORWARDED_RESPONSE_HEADERS = ["content-type", "cache-control", "x-request-id", "content-disposition"];
const STATE_CHANGING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function jsonError(status: number, code: string, message: string) {
  const body: TApiErrorBody = { code, message };
  return Response.json(body, { status });
}

// Same-origin check: the proxy holds the API key, so another site in the browser must not be able to drive it.
function isCrossSite(request: Request) {
  const fetchSite = request.headers.get("sec-fetch-site");
  if (fetchSite && fetchSite !== "same-origin" && fetchSite !== "none") return true;

  const origin = request.headers.get("origin");
  if (!origin) return false;
  try {
    return new URL(origin).host !== request.headers.get("host");
  } catch {
    return true;
  }
}

export async function proxyToAgent(request: Request, path: string[]) {
  if (STATE_CHANGING.has(request.method) && isCrossSite(request)) {
    return jsonError(403, "FORBIDDEN", "Cross-site requests are not allowed");
  }
  if (path.some((segment) => segment === ".." || segment === "." || segment.includes("\\"))) {
    return jsonError(400, "BAD_REQUEST", "Invalid path");
  }

  const incoming = new URL(request.url);
  const target = `${backendUrl()}/${path.map(encodeURIComponent).join("/")}${incoming.search}`;

  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const apiKey = process.env.AGENT_API_KEY;
  if (apiKey) headers.set("x-agent-key", apiKey);

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
      signal: request.signal,
      redirect: "manual",
      cache: "no-store",
    });
  } catch (error) {
    if (request.signal.aborted) return new Response(null, { status: 499 });
    console.error("agent proxy: backend unreachable", { target: backendUrl(), error: String(error) });
    return jsonError(502, "BACKEND_UNREACHABLE", "Blog Agent API is not reachable");
  }

  const responseHeaders = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  if (upstream.headers.get("content-type")?.startsWith("text/event-stream")) {
    responseHeaders.set("cache-control", "no-cache, no-transform");
    responseHeaders.set("x-accel-buffering", "no");
  }

  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}
