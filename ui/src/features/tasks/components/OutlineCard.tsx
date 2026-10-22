import { Badge } from "@/components/ui/badge";
import type { TTask } from "../types";
import { OutlineReviewForm } from "./OutlineReviewForm";

type OutlineCardProps = {
  task: TTask;
};

export function OutlineCard({ task }: OutlineCardProps) {
  const outline = task.outline;
  if (!outline) return null;
  if (task.pending_interrupt?.type === "outline_review" && !task.is_running) {
    return <OutlineReviewForm taskId={task.id} outline={outline} />;
  }
  const covered = new Set(outline.covered_requirements);
  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-medium">Outline: {outline.title}</h3>
        <p className="text-sm text-muted-foreground">{outline.angle}</p>
      </div>
      <ol className="space-y-3">
        {outline.sections.map((section, index) => (
          <li key={section.key} className="rounded-md border p-3 text-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-medium">
                {index + 1}. {section.heading}
              </p>
              <span className="font-mono text-xs text-muted-foreground">~{section.est_words} words</span>
            </div>
            <p className="text-muted-foreground">{section.goal}</p>
            <div className="mt-2 flex flex-wrap gap-1">
              {section.needs.map((need) => (
                <Badge key={need} variant="secondary">
                  {need.replaceAll("_", " ")}
                </Badge>
              ))}
              <Badge variant="outline">{section.claim_ids.length} evidence</Badge>
            </div>
          </li>
        ))}
      </ol>
      {outline.must_cover.length ? (
        <p className="text-xs text-muted-foreground">
          Must cover:{" "}
          {outline.must_cover.map((item) => `${item} ${covered.has(item) ? "✓" : "✗"}`).join(" · ")}
        </p>
      ) : null}
    </section>
  );
}
