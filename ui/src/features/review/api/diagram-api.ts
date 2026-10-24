import { apiClient } from "@/lib/api-client";
import type { TDiagramAsset } from "../types";

export const diagramApi = {
  list: (taskId: string) => apiClient.get<TDiagramAsset[]>(`/tasks/${taskId}/diagrams`),

  switchFormat: (taskId: string, slotId: string, targetFormat: "drawio" | "mermaid") =>
    apiClient.post<TDiagramAsset>(`/tasks/${taskId}/diagrams/${slotId}/switch-format`, {
      target_format: targetFormat,
    }),

  upload: (taskId: string, slotId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.post<TDiagramAsset>(`/tasks/${taskId}/diagrams/${slotId}/upload`, formData);
  },

  regenerate: (taskId: string, slotId: string, feedback: string) =>
    apiClient.post<TDiagramAsset>(`/tasks/${taskId}/diagrams/${slotId}/regenerate`, {
      feedback,
    }),
};
