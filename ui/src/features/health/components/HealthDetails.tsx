"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Grid } from "@/components/layout/Grid";
import { useHealth } from "../hooks/use-health";

type StatusRowProps = {
  label: string;
  value: string;
  ok: boolean;
};

function StatusRow({ label, value, ok }: StatusRowProps) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <Badge variant={ok ? "secondary" : "destructive"} className="font-mono">
        {value}
      </Badge>
    </div>
  );
}

export function HealthDetails() {
  const { data, error, isPending } = useHealth();

  if (isPending) {
    return (
      <Grid cols={2}>
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </Grid>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>API unreachable</CardTitle>
          <CardDescription>
            {error instanceof Error ? error.message : "No response"}. Start the stack with{" "}
            <code className="font-mono">make up</code> (or <code className="font-mono">make dev</code>).
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Grid cols={2}>
      <Card>
        <CardHeader>
          <CardTitle>Runtime</CardTitle>
          <CardDescription>
            {data.app} · env <span className="font-mono">{data.env}</span>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <StatusRow label="Database" value={data.database.ok ? "ok" : "down"} ok={data.database.ok} />
          <StatusRow label="Checkpointer" value={data.checkpointer.ok ? "ok" : "down"} ok={data.checkpointer.ok} />
          <StatusRow
            label="LangSmith tracing"
            value={data.tracing.enabled ? (data.tracing.project ?? "on") : "off"}
            ok
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Models</CardTitle>
          <CardDescription>Set per role with LLM_&lt;ROLE&gt;_MODEL, or LLM_DEFAULT_MODEL.</CardDescription>
        </CardHeader>
        <CardContent>
          {Object.entries(data.llm.roles).map(([role, model]) => (
            <StatusRow key={role} label={role} value={model ?? "not configured"} ok={model !== null} />
          ))}
        </CardContent>
      </Card>
    </Grid>
  );
}
