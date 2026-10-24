import { apiClient } from "@/lib/api-client";
import type {
  TImportSamplesResult,
  TOwnerNote,
  TOwnerNoteInput,
  TStyleProfile,
  TWritingSample,
} from "../types";

export const styleApi = {
  // Writing Samples
  importSamples: (sources: string[]) =>
    apiClient.post<TImportSamplesResult>("/samples/import", { sources }),

  listSamples: (approvedOnly: boolean = false) =>
    apiClient.get<TWritingSample[]>(`/samples${approvedOnly ? "?approved_only=true" : ""}`),

  toggleApproval: (sampleId: string, approved: boolean) =>
    apiClient.patch<TWritingSample>(`/samples/${sampleId}/approval`, { approved }),

  deleteSample: (sampleId: string) =>
    apiClient.delete<{ deleted: boolean; id: string }>(`/samples/${sampleId}`),

  // Style Profiles
  getActiveProfile: () =>
    apiClient.get<TStyleProfile>("/style-profile"),

  listProfiles: () =>
    apiClient.get<TStyleProfile[]>("/style-profiles"),

  getProfile: (profileId: string) =>
    apiClient.get<TStyleProfile>(`/style-profile/${profileId}`),

  generateProfile: (name?: string) =>
    apiClient.post<TStyleProfile>("/style-profile/generate", { name }),

  updateProfile: (profileId: string, payload: { name?: string; markdown_content?: string; profile_data?: Record<string, unknown> }) =>
    apiClient.put<TStyleProfile>(`/style-profile/${profileId}`, payload),

  activateProfile: (profileId: string) =>
    apiClient.post<TStyleProfile>(`/style-profile/${profileId}/activate`),

  // Owner Notes
  listNotes: () =>
    apiClient.get<TOwnerNote[]>("/notes"),

  getNote: (noteId: string) =>
    apiClient.get<TOwnerNote>(`/notes/${noteId}`),

  createNote: (input: TOwnerNoteInput) =>
    apiClient.post<TOwnerNote>("/notes", input),

  updateNote: (noteId: string, input: TOwnerNoteInput) =>
    apiClient.put<TOwnerNote>(`/notes/${noteId}`, input),

  deleteNote: (noteId: string) =>
    apiClient.delete<{ deleted: boolean; id: string }>(`/notes/${noteId}`),
};
