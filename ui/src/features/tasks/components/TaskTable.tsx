"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatRelative, humanize } from "@/lib/format";
import { useTaskList } from "../hooks/use-task-list";
import { TaskStatusBadge } from "./TaskStatusBadge";

export function TaskTable() {
  const { data, isPending, error, filtersActive } = useTaskList();

  if (isPending) return <Skeleton className="h-64" />;
  if (error) return <p className="text-sm text-destructive">{error.message}</p>;
  if (!data.items.length) {
    return (
      <Card className="border-dashed">
        <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="text-sm text-muted-foreground">
            {filtersActive ? "No tasks match these filters." : "No tasks yet. Ask the agent to research or write something."}
          </p>
          {filtersActive ? null : (
            <Button asChild>
              <Link href="/tasks/new">New task</Link>
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="py-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Topic</TableHead>
            <TableHead className="w-36">Status</TableHead>
            <TableHead className="w-32">Mode</TableHead>
            <TableHead className="w-28 text-right">Sources</TableHead>
            <TableHead className="w-32 text-right">Updated</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((task) => (
            <TableRow key={task.id}>
              <TableCell className="max-w-0">
                <Link href={`/tasks/${task.id}`} className="block truncate font-medium hover:underline">
                  {task.topic}
                </Link>
                {task.status === "failed" && task.last_error ? (
                  <p className="truncate text-xs text-destructive">{task.last_error}</p>
                ) : null}
              </TableCell>
              <TableCell>
                <TaskStatusBadge status={task.status} running={task.is_running} />
              </TableCell>
              <TableCell>
                <Badge variant="secondary">{task.mode === "research_only" ? "research" : humanize(task.format)}</Badge>
              </TableCell>
              <TableCell className="text-right font-mono text-sm">{task.progress.sources_found}</TableCell>
              <TableCell className="text-right text-sm text-muted-foreground">{formatRelative(task.updated_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
