import { apiClient } from "@/lib/api-client";
import type { TStyleGuide } from "../types";

export const styleGuideApi = {
  get: () => apiClient.get<TStyleGuide>("/settings/style-guide"),
  update: (content: string) => apiClient.put<TStyleGuide>("/settings/style-guide", { content }),
};
