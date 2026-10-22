import { Badge } from "@/components/ui/badge";
import { humanize } from "@/lib/format";
import { cn } from "@/lib/utils";
import { STATUS_TONE } from "../status";
import type { TStatusTone } from "../status";
import type { TTaskStatus } from "../types";

const dotClass: Record<TStatusTone, string> = {
  neutral: "bg-muted-foreground",
  active: "bg-primary animate-pulse",
  attention: "bg-warning",
  success: "bg-success",
  danger: "bg-destructive",
  muted: "bg-muted-foreground/50",
};

type TaskStatusBadgeProps = {
  status: TTaskStatus;
  running?: boolean;
};

export function TaskStatusBadge({ status, running }: TaskStatusBadgeProps) {
  const tone = running ? "active" : STATUS_TONE[status];
  return (
    <Badge variant={tone === "danger" ? "destructive" : "outline"} className={cn("gap-1.5 capitalize", tone === "muted" && "text-muted-foreground")}>
      <span className={cn("size-1.5 rounded-full", dotClass[tone])} />
      {humanize(status)}
    </Badge>
  );
}
