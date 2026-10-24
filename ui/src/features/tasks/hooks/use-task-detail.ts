import { useParams } from "next/navigation";

import { isTaskLive } from "../status";
import { useTask } from "./use-task";
import { useTaskEvents } from "./use-task-events";

export function useTaskDetail() {
  const { id } = useParams<{ id: string }>();
  const query = useTask(id);
  const task = query.data;
  const live = task ? isTaskLive(task) : true;
  const { events, connected } = useTaskEvents(id, live);
  const hasBrief = events.some((event) => event.type === "brief_ready") || task?.status === "completed";
  const hasDraft =
    events.some((event) => event.type === "revision_saved") ||
    ["awaiting_review", "revision_requested", "approved", "published", "partially_published"].includes(task?.status ?? "");

  return { id, task, error: query.error, isPending: query.isPending, events, connected, hasBrief, hasDraft };
}
