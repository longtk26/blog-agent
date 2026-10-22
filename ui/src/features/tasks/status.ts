import type { TTask, TTaskStatus } from "./types";

export type TStatusTone = "neutral" | "active" | "attention" | "success" | "danger" | "muted";

export const STATUS_TONE: Record<TTaskStatus, TStatusTone> = {
  queued: "neutral",
  researching: "active",
  outlining: "active",
  drafting: "active",
  generating_diagram: "active",
  validating: "active",
  revision_requested: "active",
  publishing: "active",
  awaiting_review: "attention",
  approved: "attention",
  partially_published: "attention",
  completed: "success",
  published: "success",
  failed: "danger",
  rejected: "muted",
};

export function isTaskLive(task: Pick<TTask, "status" | "is_running">) {
  return task.is_running || task.status === "queued";
}
