"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ActivityIcon,
  CheckCircle2Icon,
  CoinsIcon,
  ExternalLinkIcon,
  TimerIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDateTime, humanize } from "@/lib/format";
import { statsApi } from "../api/stats-api";

export function OpsDashboard() {
  const [days, setDays] = useState<number>(30);
  const { data, isPending, error } = useQuery({
    queryKey: ["ops-stats", days],
    queryFn: () => statsApi.get(days),
  });

  if (isPending) return <Skeleton className="h-150 w-full" />;
  if (error) return <p className="text-sm text-destructive">Failed to load ops stats: {error.message}</p>;
  if (!data) return null;

  const totalTasks = Object.values(data.tasks_by_status).reduce((acc, curr) => acc + curr, 0);

  return (
    <div className="space-y-8">
      {/* Time window selector */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">System Health & Telemetry</h2>
          <p className="text-xs text-muted-foreground">Aggregated across task events, run usage, and publishing logs</p>
        </div>
        <div className="flex items-center gap-1.5 rounded-lg border bg-muted/40 p-1">
          {[7, 30, 90].map((d) => (
            <Button
              key={d}
              variant={days === d ? "default" : "ghost"}
              size="sm"
              className="h-7 px-3 text-xs"
              onClick={() => setDays(d)}
            >
              Last {d} days
            </Button>
          ))}
        </div>
      </div>

      {/* Overview Metric Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-md bg-primary/10 p-2.5 text-primary">
              <ActivityIcon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Total Tasks ({days}d)</p>
              <p className="text-2xl font-bold">{totalTasks}</p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-md bg-emerald-500/10 p-2.5 text-emerald-500">
              <CoinsIcon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Avg Cost / Task</p>
              <p className="text-2xl font-bold">${data.avg_cost_per_task.toFixed(3)}</p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-md bg-amber-500/10 p-2.5 text-amber-500">
              <CoinsIcon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Total Period Spend</p>
              <p className="text-2xl font-bold">${data.total_cost_period.toFixed(2)}</p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-md bg-sky-500/10 p-2.5 text-sky-500">
              <TimerIcon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Tracked Stages</p>
              <p className="text-2xl font-bold">{data.stage_durations.length}</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Task Final Status Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Tasks by Final Status</CardTitle>
          <CardDescription>Execution states across all tasks in this period</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2.5">
            {Object.entries(data.tasks_by_status).map(([status, count]) => {
              const isGood = status === "published" || status === "completed" || status === "approved";
              const isBad = status === "failed" || status === "rejected";
              return (
                <div
                  key={status}
                  className="flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm shadow-sm"
                >
                  <span className="font-medium">{humanize(status)}</span>
                  <Badge variant={isGood ? "default" : isBad ? "destructive" : "secondary"}>
                    {count}
                  </Badge>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Stage Latency & Duration Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Stage Duration & Latency (Avg & P90)</CardTitle>
          <CardDescription>Measured execution times at workflow node boundaries</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Workflow Stage / Node</TableHead>
                  <TableHead className="w-24 text-right">Samples</TableHead>
                  <TableHead className="w-32 text-right">Avg Duration</TableHead>
                  <TableHead className="w-32 text-right">P90 Duration</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.stage_durations.length ? (
                  data.stage_durations.map((stage) => (
                    <TableRow key={stage.stage}>
                      <TableCell className="font-mono text-xs font-medium">
                        {humanize(stage.stage)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs text-muted-foreground">
                        {stage.samples}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs font-semibold">
                        {stage.avg_duration_s.toFixed(2)}s
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs text-amber-600 dark:text-amber-400">
                        {stage.p90_duration_s.toFixed(2)}s
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={4} className="py-6 text-center text-xs text-muted-foreground">
                      No stage duration events recorded in this period.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Tool Error Rates */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Tool Error Rates</CardTitle>
          <CardDescription>Reliability metrics for search, extraction, rendering, and publishers</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {data.tool_error_rates.map((t) => {
              const pct = (t.error_rate * 100).toFixed(1);
              const isClean = t.errors === 0;
              const isCritical = t.error_rate > 0.1;
              return (
                <div key={t.tool} className="flex flex-col justify-between rounded-lg border p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium capitalize">{t.tool}</span>
                    <Badge variant={isClean ? "outline" : isCritical ? "destructive" : "secondary"}>
                      {pct}% error
                    </Badge>
                  </div>
                  <div className="flex items-baseline justify-between text-xs text-muted-foreground">
                    <span>Invocations: {t.calls}</span>
                    <span className={t.errors > 0 ? "text-destructive font-medium" : ""}>
                      Errors: {t.errors}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Recent Failures with Sanitized Error and LangSmith Link */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent Task Failures</CardTitle>
          <CardDescription>Last failed tasks with sanitized errors and direct LangSmith traces</CardDescription>
        </CardHeader>
        <CardContent>
          {data.recent_failures.length ? (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Task Topic</TableHead>
                    <TableHead className="w-36">Failed Stage</TableHead>
                    <TableHead>Sanitized Error</TableHead>
                    <TableHead className="w-36">Date</TableHead>
                    <TableHead className="w-28 text-right">Trace</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.recent_failures.map((f) => (
                    <TableRow key={f.task_id}>
                      <TableCell className="max-w-50 truncate font-medium">
                        <Link href={`/tasks/${f.task_id}`} className="hover:underline">
                          {f.topic}
                        </Link>
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {humanize(f.failed_stage ?? "workflow")}
                      </TableCell>
                      <TableCell className="max-w-[320px]">
                        <p className="truncate font-mono text-xs text-destructive" title={f.error || ""}>
                          {f.error || "Unknown failure"}
                        </p>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                        {formatDateTime(f.created_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        {f.trace_url ? (
                          <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs" asChild>
                            <a href={f.trace_url} target="_blank" rel="noopener noreferrer">
                              Trace <ExternalLinkIcon className="h-3 w-3" />
                            </a>
                          </Button>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-10 text-center space-y-2">
              <CheckCircle2Icon className="h-8 w-8 text-emerald-500" />
              <p className="text-sm font-medium">No recent failures</p>
              <p className="text-xs text-muted-foreground">All tasks in this window succeeded or are pending review.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
