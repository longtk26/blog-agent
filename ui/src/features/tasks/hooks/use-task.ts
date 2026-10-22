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

export function useLatestRevision(id: string, enabled: boolean) {
  const revisions = useQuery({ queryKey: taskKeys.revisions(id), queryFn: () => tasksApi.revisions(id), enabled });
  const latestId = revisions.data?.items[0]?.id;
  const revision = useQuery({
    queryKey: taskKeys.revision(latestId ?? "none"),
    queryFn: () => tasksApi.revision(latestId as string),
    enabled: Boolean(latestId),
  });
  return { revisions: revisions.data?.items ?? [], revision: revision.data, isPending: revisions.isPending || (Boolean(latestId) && revision.isPending) };
}
