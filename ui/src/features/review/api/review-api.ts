import type { TRevision, TTask } from "@/features/tasks/types";
import { apiClient } from "@/lib/api-client";
import type { TApproval, TApprovalPayload, TOwnerRevisionPayload, TReviewPayload } from "../types";

export const reviewApi = {
  saveRevision: (taskId: string, payload: TOwnerRevisionPayload) => apiClient.post<TRevision>(`/tasks/${taskId}/revisions`, payload),
  review: (taskId: string, payload: TReviewPayload) => apiClient.post<TTask>(`/tasks/${taskId}/review`, payload),
  approve: (revisionId: string, payload: TApprovalPayload) =>
    apiClient.post<{ items: TApproval[] }>(`/revisions/${revisionId}/approvals`, payload),
  approvals: (taskId: string) => apiClient.get<{ items: TApproval[] }>(`/tasks/${taskId}/approvals`),
};
