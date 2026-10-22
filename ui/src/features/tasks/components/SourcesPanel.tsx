"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { useTaskSources } from "../hooks/use-task";
import { SourceItem } from "./SourceItem";

type SourcesPanelProps = {
  taskId: string;
};

export function SourcesPanel({ taskId }: SourcesPanelProps) {
  const { data, isPending } = useTaskSources(taskId);

  if (isPending) return <Skeleton className="h-40" />;
  if (!data?.items.length) {
    return <p className="py-8 text-center text-sm text-muted-foreground">No sources yet.</p>;
  }
  return (
    <div className="space-y-2">
      {data.items.map((source) => (
        <SourceItem key={source.id} source={source} />
      ))}
    </div>
  );
}
