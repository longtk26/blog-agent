"use client";

import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import type { TIssueSeverity, TRevision, TValidationIssue } from "@/features/tasks/types";
import { humanize } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useReviewStore } from "@/store/review-store";

const SEVERITIES: { key: TIssueSeverity; label: string }[] = [
  { key: "blocker", label: "Blockers" },
  { key: "warning", label: "Warnings" },
  { key: "info", label: "Info" },
];

type IssuesPanelProps = {
  revision: TRevision;
};

export function IssuesPanel({ revision }: IssuesPanelProps) {
  const jumpTo = useReviewStore((state) => state.jumpTo);
  const issues = revision.evaluations.flatMap((evaluation) => evaluation.issues);
  const judge = revision.evaluations.find((evaluation) => evaluation.kind === "judge");
  const onSelect = (issue: TValidationIssue) =>
    jumpTo({ section: issue.section, line: issue.source === "validator" ? issue.line : null });

  return (
    <div className="space-y-5">
      {judge ? (
        <section className="space-y-1.5">
          <h3 className="text-xs font-medium text-muted-foreground uppercase">Editor scores</h3>
          {Object.entries(judge.scores).map(([name, score]) => (
            <div key={name} className="grid grid-cols-[120px_1fr_20px] items-center gap-2 text-xs">
              <span className="truncate text-muted-foreground capitalize">{humanize(name)}</span>
              <Progress value={(score / 5) * 100} className={cn(score < 3 && "[&>*]:bg-destructive")} />
              <span className="font-mono">{score}</span>
            </div>
          ))}
        </section>
      ) : (
        <p className="text-xs text-muted-foreground">
          {revision.created_by === "owner" ? "Owner revisions run the automated checks only (no AI editor)." : "No editor review."}
        </p>
      )}
      {SEVERITIES.map(({ key, label }) => {
        const group = issues.filter((issue) => issue.severity === key);
        return (
          <section key={key} className="space-y-1.5">
            <h3 className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase">
              {label}
              <Badge variant={key === "blocker" && group.length ? "destructive" : "outline"}>{group.length}</Badge>
            </h3>
            {group.length ? (
              <ul className="space-y-1">
                {group.map((issue, index) => (
                  <li key={`${issue.rule}-${index}`}>
                    <button
                      type="button"
                      onClick={() => onSelect(issue)}
                      className="w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                    >
                      <span className="mb-0.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                        <span className="font-mono">{issue.rule}</span>
                        {issue.section ? <span>· {issue.section}</span> : null}
                        {issue.line ? <span>· line {issue.line}</span> : null}
                        <span>· {issue.source === "judge" ? "AI editor" : "check"}</span>
                      </span>
                      {issue.message}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>
        );
      })}
    </div>
  );
}
