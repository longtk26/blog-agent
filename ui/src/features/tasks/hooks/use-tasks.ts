import { useQuery } from "@tanstack/react-query";

import { tasksApi } from "../api/tasks-api";
import { taskKeys } from "../query-keys";
import type { TTaskListFilters } from "../types";

export function useTasks(filters: TTaskListFilters) {
  return useQuery({
    queryKey: taskKeys.list(filters),
    queryFn: () => tasksApi.list(filters),
    // Poll only while something is running; the detail page uses SSE instead.
    refetchInterval: (query) => (query.state.data?.items.some((task) => task.is_running) ? 4000 : false),
  });
}
