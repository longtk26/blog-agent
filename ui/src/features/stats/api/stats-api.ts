import { apiClient } from "@/lib/api-client";
import type { TOpsStats } from "../types";

export const statsApi = {
  get: (days: number = 30) => apiClient.get<TOpsStats>(`/stats?days=${days}`),
};
