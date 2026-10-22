"use client";

import { MarkdownView } from "@/components/markdown/MarkdownView";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime, humanize } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useLatestRevision } from "../hooks/use-task";
import type { TValidationIssue } from "../types";

type DraftPanelProps = {
  taskId: string;
  enabled: boolean;
};

const severityOrder = { blocker: 0, warning: 1, info: 2 } as const;

function IssueList({ issues }: { issues: TValidationIssue[] }) {
  if (!issues.length) return <p className="text-sm text-muted-foreground">No issues.</p>;
  return (
    <ul className="space-y-1.5">
      {[...issues]
        .sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity])
        .map((issue, index) => (
          <li key={`${issue.rule}-${index}`} className="flex gap-2 text-sm">
            <Badge variant={issue.severity === "blocker" ? "destructive" : "outline"} className="shrink-0">
              {issue.severity}
            </Badge>
            <span>
              {issue.section ? <span className="text-muted-foreground">{issue.section} — </span> : null}
              {issue.message}
            </span>
          </li>
        ))}
    </ul>
  );
}

export function DraftPanel({ taskId, enabled }: DraftPanelProps) {
  const { revision, isPending } = useLatestRevision(taskId, enabled);

  if (!enabled) return <p className="py-8 text-center text-sm text-muted-foreground">The draft appears after writing and checks finish.</p>;
  if (isPending) return <Skeleton className="h-96" />;
  if (!revision) return <p className="py-8 text-center text-sm text-muted-foreground">No revision yet.</p>;

  const deterministic = revision.evaluations.find((e) => e.kind === "deterministic");
  const judge = revision.evaluations.find((e) => e.kind === "judge");
  const unsupported = revision.metadata.unsupported_statements ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="secondary">r{revision.revision_number}</Badge>
        <span>{revision.created_by === "ai" ? "AI" : "Owner"}</span>
        <span>· {formatDateTime(revision.created_at)}</span>
        <span className="font-mono">· {revision.content_hash.slice(0, 12)}</span>
        <span>· {revision.metadata.word_count ?? "?"} words</span>
        <span>· {revision.metadata.self_revisions ?? 0} self-revisions</span>
      </div>

      <dl className="grid gap-2 rounded-lg border p-3 text-sm sm:grid-cols-[120px_1fr]">
        <dt className="text-muted-foreground">Title</dt>
        <dd>{revision.title}</dd>
        <dt className="text-muted-foreground">Slug</dt>
        <dd className="font-mono">{revision.slug}</dd>
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
      </dl>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="space-y-2">
          <h3 className="text-sm font-medium">
            Automated checks {deterministic ? (deterministic.passed ? "· passed" : "· blockers found") : null}
          </h3>
          <IssueList issues={deterministic?.issues ?? []} />
        </section>
        <section className="space-y-2">
          <h3 className="text-sm font-medium">Editor review {judge ? (judge.passed ? "· passed" : "· needs attention") : null}</h3>
          <div className="space-y-1.5">
            {Object.entries(judge?.scores ?? {}).map(([name, score]) => (
              <div key={name} className="grid grid-cols-[140px_1fr_24px] items-center gap-2 text-xs">
                <span className="text-muted-foreground capitalize">{humanize(name)}</span>
                <Progress value={(score / 5) * 100} className={cn(score < 3 && "[&>*]:bg-destructive")} />
                <span className="font-mono">{score}</span>
              </div>
            ))}
          </div>
          <IssueList issues={judge?.issues ?? []} />
        </section>
      </div>

      {unsupported.length ? (
        <section className="space-y-2">
          <h3 className="text-sm font-medium">Statements without evidence</h3>
          <ul className="ml-5 list-disc text-sm text-muted-foreground">
            {unsupported.map((statement) => (
              <li key={statement}>{statement}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="rounded-lg border p-4">
        <p className="mb-3 text-xs text-muted-foreground">Basic preview — the site-accurate preview and editor arrive in Epic 4.</p>
        <MarkdownView markdown={revision.markdown} />
      </section>
    </div>
  );
}
