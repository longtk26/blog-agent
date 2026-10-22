import { Badge } from "@/components/ui/badge";
import type { TResearchPlan } from "../types";

type ResearchPlanCardProps = {
  plan: TResearchPlan | null;
  openQuestions: string[];
};

export function ResearchPlanCard({ plan, openQuestions }: ResearchPlanCardProps) {
  if (!plan) {
    return <p className="py-8 text-center text-sm text-muted-foreground">The agent is still planning its research.</p>;
  }
  const open = new Set(openQuestions);
  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <h3 className="text-sm font-medium">Research questions</h3>
        <ul className="space-y-2">
          {plan.questions.map((question) => (
            <li key={question.id} className="flex gap-3 text-sm">
              <span className="font-mono text-xs text-muted-foreground">{question.id}</span>
              <span className="flex-1">{question.question}</span>
              <span className="flex shrink-0 gap-1">
                {question.must_cover ? <Badge variant="secondary">must cover</Badge> : null}
                {open.has(question.question) ? <Badge variant="outline">open</Badge> : null}
              </span>
            </li>
          ))}
        </ul>
      </section>
      <section className="space-y-2">
        <h3 className="text-sm font-medium">Planned searches</h3>
        <ul className="space-y-1.5">
          {plan.queries.map((query) => (
            <li key={query.query} className="text-sm">
              <span className="font-mono">{query.query}</span>
              <span className="text-muted-foreground"> — {query.intent}</span>
            </li>
          ))}
        </ul>
      </section>
      {plan.out_of_scope.length ? (
        <section className="space-y-2">
          <h3 className="text-sm font-medium">Out of scope</h3>
          <ul className="ml-5 list-disc text-sm text-muted-foreground">
            {plan.out_of_scope.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
