"use client";

import { useQuery } from "@tanstack/react-query";
import { diffLines } from "diff";
import { AlertTriangleIcon } from "lucide-react";
import { useMemo } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { tasksApi } from "@/features/tasks/api/tasks-api";
import { taskKeys } from "@/features/tasks/query-keys";
import type { TRevision, TRevisionSummary } from "@/features/tasks/types";
import { cn } from "@/lib/utils";
import { useReviewStore } from "@/store/review-store";

const METADATA_FIELDS = ["title", "slug", "description", "tags"] as const;

type RevisionDiffProps = {
  revision: TRevision;
  revisions: TRevisionSummary[];
};

function DiffLines({ before, after }: { before: string; after: string }) {
  const parts = useMemo(() => diffLines(before, after), [before, after]);
  const unchanged = parts.every((part) => !part.added && !part.removed);
  if (unchanged) return <p className="text-sm text-muted-foreground">The Markdown is identical.</p>;
  return (
    <pre className="max-h-[70vh] overflow-auto rounded-lg border bg-muted/30 p-3 font-mono text-xs leading-5">
      {parts.map((part, index) => {
        const lines = part.value.replace(/\n$/, "").split("\n");
        // Long unchanged runs are collapsed to their first and last lines.
        const shown = !part.added && !part.removed && lines.length > 8 ? [...lines.slice(0, 3), `… ${lines.length - 6} unchanged lines …`, ...lines.slice(-3)] : lines;
        return shown.map((line, lineIndex) => (
          <div
            key={`${index}-${lineIndex}`}
            className={cn(
              "px-2 whitespace-pre-wrap",
              part.added && "bg-emerald-500/15 text-emerald-800 dark:text-emerald-300",
              part.removed && "bg-red-500/15 text-red-800 line-through decoration-red-500/40 dark:text-red-300",
              !part.added && !part.removed && line.startsWith("… ") && "text-center text-muted-foreground italic",
            )}
          >
            <span className="mr-2 select-none text-muted-foreground">{part.added ? "+" : part.removed ? "−" : " "}</span>
            {line}
          </div>
        ));
      })}
    </pre>
  );
}

/** E4-S4: line diff of the Markdown plus metadata changes, between any revision and the selected one. */
export function RevisionDiff({ revision, revisions }: RevisionDiffProps) {
  const diffFromId = useReviewStore((state) => state.diffFromId);
  const setDiffFrom = useReviewStore((state) => state.setDiffFrom);
  const older = revisions.filter((r) => r.revision_number < revision.revision_number);
  const fromId = diffFromId ?? revision.parent_revision_id ?? older[0]?.id ?? null;
  const from = useQuery({
    queryKey: taskKeys.revision(fromId ?? "none"),
    queryFn: () => tasksApi.revision(fromId as string),
    enabled: Boolean(fromId),
  });
  const summary = revisions.find((r) => r.id === revision.id);

  if (!older.length) return <p className="py-8 text-center text-sm text-muted-foreground">r1 is the first revision; there is nothing to compare with.</p>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">Compare</span>
        <Select value={fromId ?? undefined} onValueChange={setDiffFrom}>
          <SelectTrigger size="sm" className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {older.map((r) => (
              <SelectItem key={r.id} value={r.id}>
                r{r.revision_number} · {r.created_by === "ai" ? "AI" : "Owner"}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-muted-foreground">→ r{revision.revision_number}</span>
      </div>

      {summary?.sections_changed.length ? (
        <div className="flex flex-wrap items-center gap-1.5 text-sm">
          <span className="text-muted-foreground">Sections changed (vs. parent):</span>
          {summary.sections_changed.map((name) => (
            <Badge key={name} variant={summary.out_of_scope.includes(name) ? "destructive" : "secondary"}>
              {name}
            </Badge>
          ))}
        </div>
      ) : null}
      {summary?.out_of_scope.length ? (
        <Alert variant="destructive">
          <AlertTriangleIcon />
          <AlertTitle>The AI changed sections you did not ask about</AlertTitle>
          <AlertDescription>
            {summary.out_of_scope.join(", ")} changed although the request was scoped to{" "}
            {revision.metadata.review?.scope_sections.join(", ") || "other sections"}.
          </AlertDescription>
        </Alert>
      ) : null}

      {from.isPending ? (
        <Skeleton className="h-64" />
      ) : from.data ? (
        <>
          <table className="w-full text-sm">
            <tbody>
              {METADATA_FIELDS.filter((field) => JSON.stringify(from.data[field]) !== JSON.stringify(revision[field])).map((field) => (
                <tr key={field} className="border-b align-top">
                  <td className="w-28 py-1.5 pr-2 text-muted-foreground capitalize">{field}</td>
                  <td className="py-1.5 pr-2 text-red-700 line-through dark:text-red-300">{String(from.data[field])}</td>
                  <td className="py-1.5 text-emerald-700 dark:text-emerald-300">{String(revision[field])}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <DiffLines before={from.data.markdown} after={revision.markdown} />
        </>
      ) : null}
    </div>
  );
}
