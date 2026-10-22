"use client";

import { CopyIcon } from "lucide-react";
import { toast } from "sonner";

import { MarkdownView } from "@/components/markdown/MarkdownView";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useResearchBrief } from "../hooks/use-task";

type ResearchBriefViewProps = {
  taskId: string;
  enabled: boolean;
};

export function ResearchBriefView({ taskId, enabled }: ResearchBriefViewProps) {
  const { data, isPending, error } = useResearchBrief(taskId, enabled);

  if (!enabled || error) {
    return <p className="py-8 text-center text-sm text-muted-foreground">The brief appears when research is complete.</p>;
  }
  if (isPending) return <Skeleton className="h-64" />;

  const copy = async () => {
    await navigator.clipboard.writeText(data.markdown);
    toast.success("Brief copied as Markdown");
  };

  return (
    <div className="space-y-2">
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={copy}>
          <CopyIcon /> Copy Markdown
        </Button>
      </div>
      <MarkdownView markdown={data.markdown} />
    </div>
  );
}
