"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { TRevisionSummary } from "@/features/tasks/types";
import { formatRelative } from "@/lib/format";
import { useReviewStore } from "@/store/review-store";

type RevisionSelectorProps = {
  revisions: TRevisionSummary[];
  currentId: string;
  dirty: boolean;
};

function label(revision: TRevisionSummary) {
  return `r${revision.revision_number} · ${revision.created_by === "ai" ? "AI" : "Owner"} · ${formatRelative(revision.created_at)} · ${revision.content_hash.slice(0, 6)}`;
}

export function RevisionSelector({ revisions, currentId, dirty }: RevisionSelectorProps) {
  const selectRevision = useReviewStore((state) => state.selectRevision);
  const discardDraft = useReviewStore((state) => state.discardDraft);
  const latestId = revisions[0]?.id;
  const current = revisions.find((revision) => revision.id === currentId);

  const onChange = (id: string) => {
    if (dirty && !window.confirm("You have unsaved edits on the latest revision. Switch anyway? They stay saved in this browser.")) return;
    if (!dirty) discardDraft();
    selectRevision(id === latestId ? null : id);
  };

  return (
    <Select value={currentId} onValueChange={onChange}>
      <SelectTrigger className="w-auto max-w-full font-mono text-xs" aria-label="Revision">
        {/* The trigger shows the compact label; feedback and scope warnings appear in the list only. */}
        <SelectValue>{current ? `${label(current)}${current.id === latestId ? " · latest" : ""}` : null}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {revisions.map((revision) => (
          <SelectItem key={revision.id} value={revision.id} className="items-start">
            <span className="flex flex-col gap-0.5">
              <span className="font-mono text-xs">
                {label(revision)}
                {revision.id === latestId ? " · latest" : ""}
                {revision.approved_for.length ? ` · approved: ${revision.approved_for.join(", ")}` : ""}
              </span>
              {revision.feedback ? (
                <span className="max-w-80 truncate text-xs text-muted-foreground">“{revision.feedback}”</span>
              ) : null}
              {revision.out_of_scope.length ? (
                <span className="text-xs text-destructive">Changed outside the request: {revision.out_of_scope.join(", ")}</span>
              ) : null}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
