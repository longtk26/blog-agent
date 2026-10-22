import { apiClient } from "@/lib/api-client";
import type {
  TCreateTaskPayload,
  TPromotePayload,
  TResearchBrief,
  TSourceList,
  TTask,
  TTaskList,
  TTaskListFilters,
} from "../types";

function toQuery(filters: TTaskListFilters) {
  const params = new URLSearchParams();
  filters.status?.forEach((status) => params.append("status", status));
  if (filters.mode) params.set("mode", filters.mode);
  if (filters.archived) params.set("archived", "true");
  params.set("limit", String(filters.limit ?? 50));
  params.set("offset", String(filters.offset ?? 0));
  return params.toString();
}

export const tasksApi = {
  list: (filters: TTaskListFilters) => apiClient.get<TTaskList>(`/tasks?${toQuery(filters)}`),
  get: (id: string) => apiClient.get<TTask>(`/tasks/${id}`),
  create: (payload: TCreateTaskPayload) => apiClient.post<TTask>("/tasks", payload),
  cancel: (id: string) => apiClient.post<TTask>(`/tasks/${id}/cancel`),
  retry: (id: string) => apiClient.post<TTask>(`/tasks/${id}/retry`),
  promote: (id: string, payload: TPromotePayload) => apiClient.post<TTask>(`/tasks/${id}/promote`, payload),
  sources: (id: string) => apiClient.get<TSourceList>(`/tasks/${id}/sources`),
  brief: (id: string) => apiClient.get<TResearchBrief>(`/tasks/${id}/research-brief`),
  eventsUrl: (id: string, after: number) => apiClient.eventSourceUrl(`/tasks/${id}/events?after=${after}`),
};
