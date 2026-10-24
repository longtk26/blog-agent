import type { TRevision, TTask } from "@/features/tasks/types";
import { apiClient } from "@/lib/api-client";
import type { TApproval, TApprovalPayload, TOwnerRevisionPayload, TPublication, TReviewPayload } from "../types";

export const reviewApi = {
  saveRevision: (taskId: string, payload: TOwnerRevisionPayload) => apiClient.post<TRevision>(`/tasks/${taskId}/revisions`, payload),
  review: (taskId: string, payload: TReviewPayload) => apiClient.post<TTask>(`/tasks/${taskId}/review`, payload),
  approve: (revisionId: string, payload: TApprovalPayload) =>
    apiClient.post<{ items: TApproval[] }>(`/revisions/${revisionId}/approvals`, payload),
  approvals: (taskId: string) => apiClient.get<{ items: TApproval[] }>(`/tasks/${taskId}/approvals`),
  publish: (revisionId: string, destinations: string[]) =>
    apiClient.post<{ items: TPublication[] }>(`/revisions/${revisionId}/publish`, { destinations }),
  publications: (taskId: string) => apiClient.get<{ items: TPublication[] }>(`/tasks/${taskId}/publications`),
  retryPublication: (taskId: string, destination: string) =>
    apiClient.post<{ items: TPublication[] }>(`/tasks/${taskId}/publications/${destination}/retry`, {}),
  unpublish: (taskId: string, payload: { slug: string; destinations?: string[] }) =>
    apiClient.post<{ items: TPublication[] }>(`/tasks/${taskId}/unpublish`, payload),
  devtoPreview: (revisionId: string) =>
    apiClient.get<{
      title: string;
      body_markdown: string;
      rendered_content_hash: string;
      tags: string[];
      canonical_url: string | null;
      main_image: string | null;
      description: string | null;
    }>(`/revisions/${revisionId}/render/devto`),
};

