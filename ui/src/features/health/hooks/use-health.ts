import { useQuery } from "@tanstack/react-query";

import { ApiError } from "@/lib/api-client";
import { fetchHealth } from "../api/health-api";
import { healthKeys } from "../query-keys";
import type { THealth } from "../types";

export type THealthSummary = {
  level: "ok" | "warning" | "down" | "loading";
  label: string;
};

function summarize(health: THealth | undefined, error: unknown, isPending: boolean): THealthSummary {
  if (isPending) return { level: "loading", label: "Checking…" };
  if (error || !health) {
    const unreachable = error instanceof ApiError && error.code === "BACKEND_UNREACHABLE";
    return { level: "down", label: unreachable ? "API unreachable" : "API error" };
  }
  if (health.status !== "healthy") return { level: "down", label: "API degraded" };
  if (!health.llm.configured) return { level: "warning", label: "LLM not configured" };
  return { level: "ok", label: "API healthy" };
}

export function useHealth() {
  const query = useQuery({
    queryKey: healthKeys.status(),
    queryFn: fetchHealth,
    refetchInterval: 15 * 1000,
    retry: false,
  });

  return {
    ...query,
    summary: summarize(query.data, query.error, query.isPending),
  };
}
