import { apiClient } from "@/lib/api-client";
import type { THealth } from "../types";

export function fetchHealth() {
  return apiClient.get<THealth>("/health");
}
