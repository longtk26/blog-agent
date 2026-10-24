import type { TTaskListFilters } from "./types";

export const taskKeys = {
  all: ["tasks"] as const,
  lists: () => [...taskKeys.all, "list"] as const,
  list: (filters: TTaskListFilters) => [...taskKeys.lists(), filters] as const,
  details: () => [...taskKeys.all, "detail"] as const,
  detail: (id: string) => [...taskKeys.details(), id] as const,
  sources: (id: string) => [...taskKeys.detail(id), "sources"] as const,
  brief: (id: string) => [...taskKeys.detail(id), "brief"] as const,
  revisions: (id: string) => [...taskKeys.detail(id), "revisions"] as const,
  approvals: (id: string) => [...taskKeys.detail(id), "approvals"] as const,
  revision: (revisionId: string) => [...taskKeys.all, "revision", revisionId] as const,
};
