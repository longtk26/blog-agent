"use client";

import { useQuery } from "@tanstack/react-query";
import { CoinsIcon, HourglassIcon, LayersIcon, SparklesIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { humanize } from "@/lib/format";
import { tasksApi } from "../api/tasks-api";

type TaskUsagePanelProps = {
  taskId: string;
};

export function TaskUsagePanel({ taskId }: TaskUsagePanelProps) {
  const { data, isPending, error } = useQuery({
    queryKey: ["tasks", taskId, "usage"],
    queryFn: () => tasksApi.usage(taskId),
  });

  if (isPending) return <Skeleton className="h-64" />;
  if (error) return <p className="text-sm text-destructive">Failed to load usage data: {error.message}</p>;
  if (!data || !data.stages?.length) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        No LLM calls or token usage recorded for this task yet.
      </div>
    );
  }

  const totalCost = data.total_cost_usd ?? 0;
  const totalLatencySec = ((data.total_latency_ms ?? 0) / 1000).toFixed(1);
  const totalTokens = data.total_tokens ?? 0;
  const inputTokens = data.total_input_tokens ?? 0;
  const outputTokens = data.total_output_tokens ?? data.output_tokens ?? 0;
  const cachedTokens = data.total_cached_tokens ?? data.cached_tokens ?? 0;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-md bg-primary/10 p-2 text-primary">
              <CoinsIcon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Estimated Cost</p>
              <p className="text-lg font-semibold">${totalCost.toFixed(4)}</p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-md bg-secondary/80 p-2 text-secondary-foreground">
              <HourglassIcon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">LLM Latency</p>
              <p className="text-lg font-semibold">{totalLatencySec}s</p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-md bg-muted p-2 text-foreground">
              <LayersIcon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Total Tokens</p>
              <p className="text-lg font-semibold">{totalTokens.toLocaleString()}</p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-md bg-muted p-2 text-foreground">
              <SparklesIcon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">LLM Invocations</p>
              <p className="text-lg font-semibold">{data.total_calls ?? data.stages.length}</p>
            </div>
          </div>
        </Card>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">Stage & Model Breakdown</h3>
          <p className="text-xs text-muted-foreground">
            In: {inputTokens.toLocaleString()} | Out: {outputTokens.toLocaleString()} | Cached: {cachedTokens.toLocaleString()}
          </p>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Stage / Node</TableHead>
                <TableHead className="w-24 text-right">Calls</TableHead>
                <TableHead>Models</TableHead>
                <TableHead className="text-right">Input</TableHead>
                <TableHead className="text-right">Output</TableHead>
                <TableHead className="text-right">Cached</TableHead>
                <TableHead className="text-right">Latency</TableHead>
                <TableHead className="text-right">Cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.stages.map((stg) => (
                <TableRow key={stg.stage}>
                  <TableCell className="font-mono text-xs font-medium">
                    {humanize(stg.stage)}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">{stg.calls}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {stg.models.map((m) => (
                        <Badge key={m} variant="outline" className="text-[10px]">
                          {m.split(":").pop()?.split("/").pop()}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs text-muted-foreground">
                    {stg.input_tokens.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs text-muted-foreground">
                    {stg.output_tokens.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs text-muted-foreground">
                    {stg.cached_tokens.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {(stg.latency_ms / 1000).toFixed(2)}s
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs font-semibold">
                    ${stg.cost_usd.toFixed(4)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <p className="text-xs text-muted-foreground">
          Costs are estimated based on configured rates per 1M tokens. Cached prompt tokens are billed at cached rates.
        </p>
      </div>
    </div>
  );
}
