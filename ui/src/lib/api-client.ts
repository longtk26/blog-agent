import type { TApiErrorBody } from "@/types/api";

// The browser only talks to the same-origin proxy (src/app/api/agent/[...path]/route.ts),
// which adds the server-only API key. No backend URL or secret is ever shipped to the client.
const API_PREFIX = "/api/agent";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId?: string | null;
  readonly details?: unknown;

  constructor(status: number, body: TApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.requestId = body.request_id;
    this.details = body.details;
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as Partial<TApiErrorBody>;
    return new ApiError(response.status, {
      code: body.code ?? "HTTP_ERROR",
      message: body.message ?? response.statusText,
      request_id: body.request_id,
      details: body.details,
    });
  } catch {
    return new ApiError(response.status, { code: "HTTP_ERROR", message: response.statusText || "Request failed" });
  }
}

async function request<TData>(method: string, path: string, body?: unknown, init?: RequestInit): Promise<TData> {
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  // The API rejects non-JSON state-changing requests (CSRF guard), so always send the header.
  if (method !== "GET") headers.set("Content-Type", "application/json");

  const response = await fetch(`${API_PREFIX}${path}`, {
    ...init,
    method,
    headers,
    credentials: "same-origin",
    body: body === undefined ? (method === "GET" ? undefined : "{}") : JSON.stringify(body),
  });

  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as TData;
  return (await response.json()) as TData;
}

export const apiClient = {
  get: <TData>(path: string, init?: RequestInit) => request<TData>("GET", path, undefined, init),
  post: <TData>(path: string, body?: unknown, init?: RequestInit) => request<TData>("POST", path, body, init),
  put: <TData>(path: string, body?: unknown, init?: RequestInit) => request<TData>("PUT", path, body, init),
  patch: <TData>(path: string, body?: unknown, init?: RequestInit) => request<TData>("PATCH", path, body, init),
  delete: <TData>(path: string, init?: RequestInit) => request<TData>("DELETE", path, undefined, init),
  eventSourceUrl: (path: string) => `${API_PREFIX}${path}`,
};
