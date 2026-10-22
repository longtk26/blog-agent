import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { tasksApi } from "../api/tasks-api";
import { taskKeys } from "../query-keys";
import type { TTaskEvent } from "../types";

const REFRESH_TYPES = new Set([
  "status_changed",
  "plan_ready",
  "source_found",
  "source_extracted",
  "source_failed",
  "source_assessed",
  "brief_ready",
  "budget_update",
  "paused",
  "error",
]);

/** Live task timeline over SSE. Replays history first, then streams new events.
 *  The server ends the stream when the task is at rest; it reopens whenever `live` turns true. */
export function useTaskEvents(taskId: string, live: boolean) {
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<TTaskEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const lastIdRef = useRef(0);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const source = new EventSource(tasksApi.eventsUrl(taskId, lastIdRef.current));

    const scheduleRefresh = () => {
      // Throttle: one refetch of detail + sources per second at most.
      if (refreshTimer.current) return;
      refreshTimer.current = setTimeout(() => {
        refreshTimer.current = null;
        queryClient.invalidateQueries({ queryKey: taskKeys.detail(taskId) });
      }, 1000);
    };

    source.onopen = () => setConnected(true);
    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as TTaskEvent;
      if (event.id <= lastIdRef.current) return;
      lastIdRef.current = event.id;
      setEvents((previous) => [...previous, event]);
      if (REFRESH_TYPES.has(event.type)) scheduleRefresh();
    };
    source.addEventListener("end", () => {
      source.close();
      setConnected(false);
      queryClient.invalidateQueries({ queryKey: taskKeys.detail(taskId) });
    });
    source.onerror = () => setConnected(false);

    return () => {
      source.close();
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
      refreshTimer.current = null;
    };
  }, [taskId, live, queryClient]);

  return { events, connected };
}
