"use client";

import { Badge } from "@/components/ui/badge";
import type { TRevision } from "@/features/tasks/types";
import { formatDateTime } from "@/lib/format";
import { useReviewStore } from "@/store/review-store";
import type { TApproval } from "../types";
import { MetadataForm } from "./MetadataForm";

type MetadataPanelProps = {
  revision: TRevision;
  approvals: TApproval[];
  canEdit: boolean;
};

export function MetadataPanel({ revision, approvals, canEdit }: MetadataPanelProps) {
  const draft = useReviewStore((state) => state.draft);
  const editing = Boolean(canEdit && draft && draft.baseRevisionId === revision.id);
  const forRevision = approvals.filter((approval) => approval.article_revision_id === revision.id);

  return (
    <div className="space-y-6">
      {editing && draft ? (
        // Keyed by base revision so a new revision starts a fresh form.
        <MetadataForm key={draft.baseRevisionId} metadata={draft.metadata} />
      ) : (
        <dl className="grid gap-x-3 gap-y-2 text-sm sm:grid-cols-[90px_1fr]">
          <dt className="text-muted-foreground">Title</dt>
          <dd>{revision.title}</dd>
          <dt className="text-muted-foreground">Slug</dt>
          <dd className="font-mono break-all">{revision.slug}</dd>
          <dt className="text-muted-foreground">Description</dt>
          <dd>{revision.description}</dd>
          <dt className="text-muted-foreground">Tags</dt>
          <dd className="flex flex-wrap gap-1">
            {revision.tags.map((tag) => (
              <Badge key={tag} variant="outline">
                {tag}
              </Badge>
            ))}
          </dd>
          <dt className="text-muted-foreground">Hash</dt>
          <dd className="font-mono text-xs break-all">{revision.content_hash}</dd>
        </dl>
      )}
      {!editing && canEdit ? <p className="text-xs text-muted-foreground">Open the Edit tab to change the metadata.</p> : null}

      <section className="space-y-2">
        <h3 className="text-xs font-medium text-muted-foreground uppercase">Approvals of r{revision.revision_number}</h3>
        {forRevision.length ? (
          <ul className="space-y-1.5 text-sm">
            {forRevision.map((approval) => (
              <li key={approval.id} className="flex flex-wrap items-center gap-1.5">
                <Badge variant={approval.decision === "approved" ? "default" : "outline"}>{approval.destination}</Badge>
                <span className={approval.decision === "superseded" ? "text-muted-foreground line-through" : undefined}>
                  {approval.decision} {formatDateTime(approval.reviewed_at)}
                </span>
                {approval.options.devto_mode ? <span className="text-xs text-muted-foreground">({approval.options.devto_mode})</span> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Not approved.</p>
        )}
      </section>
    </div>
  );
}
