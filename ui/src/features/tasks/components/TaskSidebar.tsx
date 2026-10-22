import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTime, humanize } from "@/lib/format";
import type { TTask } from "../types";
import { ProgressSummary } from "./ProgressSummary";

type TaskSidebarProps = {
  task: TTask;
};

function Row({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div className="flex justify-between gap-4 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right">{value}</dd>
    </div>
  );
}

export function TaskSidebar({ task }: TaskSidebarProps) {
  return (
    <div className="space-y-4">
      {task.status === "failed" && task.last_error ? (
        <Alert variant="destructive">
          <AlertTitle>Failed during {humanize(task.failed_stage ?? "workflow")}</AlertTitle>
          <AlertDescription className="break-words">
            {task.last_error}
            {task.resumable ? " — you can retry from the last checkpoint." : null}
          </AlertDescription>
        </Alert>
      ) : null}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Progress</CardTitle>
        </CardHeader>
        <CardContent>
          <ProgressSummary progress={task.progress} budgets={task.budgets} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Request</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="space-y-1.5">
            <Row label="Mode" value={humanize(task.mode)} />
            <Row label="Format" value={humanize(task.format)} />
            <Row label="Depth" value={humanize(task.depth)} />
            <Row label="Audience" value={task.audience} />
            <Row label="Angle" value={task.angle} />
            <Row label="Language" value={task.language} />
            <Row label="Publish to" value={task.publication_targets.join(", ") || "—"} />
            <Row label="Created" value={formatDateTime(task.created_at)} />
          </dl>
          {task.requirements ? <p className="mt-3 text-sm whitespace-pre-wrap text-muted-foreground">{task.requirements}</p> : null}
        </CardContent>
      </Card>
      {task.open_questions.length ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Open questions</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="ml-5 list-disc space-y-1 text-sm">
              {task.open_questions.map((question) => (
                <li key={question}>{question}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
