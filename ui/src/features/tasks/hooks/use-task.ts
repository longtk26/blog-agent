import { useQuery } from "@tanstack/react-query";

import { ApiError } from "@/lib/api-client";
import { tasksApi } from "../api/tasks-api";
import { taskKeys } from "../query-keys";

export function useTask(id: string) {
  return useQuery({ queryKey: taskKeys.detail(id), queryFn: () => tasksApi.get(id) });
}

export function useTaskSources(id: string) {
  return useQuery({ queryKey: taskKeys.sources(id), queryFn: () => tasksApi.sources(id) });
}

export function useResearchBrief(id: string, enabled: boolean) {
  return useQuery({
    queryKey: taskKeys.brief(id),
    queryFn: () => tasksApi.brief(id),
    enabled,
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 1,
  });
}
