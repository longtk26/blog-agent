"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useHealth } from "../hooks/use-health";
import type { THealthSummary } from "../hooks/use-health";

const dotClass: Record<THealthSummary["level"], string> = {
  ok: "bg-success",
  warning: "bg-warning",
  down: "bg-destructive",
  loading: "bg-muted-foreground animate-pulse",
};

export function HealthIndicator() {
  const { data, summary } = useHealth();

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="outline" asChild>
          <Link href="/settings" className="gap-2">
            <span className={cn("size-2 rounded-full", dotClass[summary.level])} />
            {summary.label}
          </Link>
        </Badge>
      </TooltipTrigger>
      <TooltipContent side="bottom" align="end">
        {data ? (
          <ul className="space-y-0.5 text-xs">
            <li>Database: {data.database.ok ? "ok" : "down"}</li>
            <li>Checkpointer: {data.checkpointer.ok ? "ok" : "down"}</li>
            <li>LLM: {data.llm.default_provider ?? "not configured"}</li>
            <li>Tracing: {data.tracing.enabled ? data.tracing.project : "off"}</li>
          </ul>
        ) : (
          <span className="text-xs">No response from the API</span>
        )}
      </TooltipContent>
    </Tooltip>
  );
}
