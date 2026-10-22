import { Progress } from "@/components/ui/progress";
import type { TTaskBudgets, TTaskProgress } from "../types";

type ProgressSummaryProps = {
  progress: TTaskProgress;
  budgets: TTaskBudgets;
};

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-mono text-sm">{value}</dd>
    </div>
  );
}

export function ProgressSummary({ progress, budgets }: ProgressSummaryProps) {
  const assessedRatio = progress.sources_found ? (progress.sources_assessed / progress.sources_found) * 100 : 0;
  return (
    <div className="space-y-3">
      <Progress value={assessedRatio} aria-label="Sources assessed" />
      <dl className="grid grid-cols-2 gap-3">
        <Stat label="Round" value={`${progress.round} / ${budgets.max_research_rounds}`} />
        <Stat label="Queries" value={`${progress.queries_used} / ${budgets.max_queries}`} />
        <Stat label="Sources" value={`${progress.sources_found} / ${budgets.max_sources}`} />
        <Stat label="Assessed" value={`${progress.sources_assessed}`} />
        <Stat label="Claims" value={`${progress.claims}`} />
        <Stat label="Read" value={`${progress.sources_extracted}`} />
      </dl>
    </div>
  );
}
