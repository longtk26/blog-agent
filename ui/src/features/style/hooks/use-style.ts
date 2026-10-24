import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { styleApi } from "../api/style-api";
import { styleKeys } from "../query-keys";
import type { TOwnerNoteInput } from "../types";

// --- Writing Samples Hooks ---

export function useWritingSamples(approvedOnly?: boolean) {
  return useQuery({
    queryKey: styleKeys.samples(approvedOnly),
    queryFn: () => styleApi.listSamples(approvedOnly),
  });
}

export function useImportSamples() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sources: string[]) => styleApi.importSamples(sources),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: styleKeys.all });
      toast.success(
        `Imported ${data.imported} samples, updated ${data.updated}, skipped ${data.skipped} (${data.total_chunks} chunks)`
      );
    },
    onError: (err: Error) => {
      toast.error(`Import failed: ${err.message}`);
    },
  });
}

export function useToggleSampleApproval() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sampleId, approved }: { sampleId: string; approved: boolean }) =>
      styleApi.toggleApproval(sampleId, approved),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: styleKeys.all });
      toast.success(
        updated.approved_as_style_example
          ? `Enabled "${updated.title}" as style example`
          : `Disabled "${updated.title}" as style example`
      );
    },
    onError: (err: Error) => {
      toast.error(`Failed to update approval: ${err.message}`);
    },
  });
}

export function useDeleteSample() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sampleId: string) => styleApi.deleteSample(sampleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: styleKeys.all });
      toast.success("Writing sample deleted");
    },
    onError: (err: Error) => {
      toast.error(`Delete failed: ${err.message}`);
    },
  });
}

// --- Style Profile Hooks ---

export function useActiveStyleProfile() {
  return useQuery({
    queryKey: styleKeys.profileActive(),
    queryFn: () => styleApi.getActiveProfile(),
  });
}

export function useStyleProfiles() {
  return useQuery({
    queryKey: styleKeys.profiles(),
    queryFn: () => styleApi.listProfiles(),
  });
}

export function useGenerateStyleProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name?: string) => styleApi.generateProfile(name),
    onSuccess: (profile) => {
      queryClient.invalidateQueries({ queryKey: styleKeys.all });
      toast.success(`Generated Style Profile v${profile.version}`);
    },
    onError: (err: Error) => {
      toast.error(`Generation failed: ${err.message}`);
    },
  });
}

export function useUpdateStyleProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      profileId,
      payload,
    }: {
      profileId: string;
      payload: { name?: string; markdown_content?: string; profile_data?: Record<string, unknown> };
    }) => styleApi.updateProfile(profileId, payload),
    onSuccess: (profile) => {
      queryClient.invalidateQueries({ queryKey: styleKeys.all });
      toast.success(`Saved Style Profile v${profile.version}`);
    },
    onError: (err: Error) => {
      toast.error(`Save failed: ${err.message}`);
    },
  });
}

export function useActivateStyleProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (profileId: string) => styleApi.activateProfile(profileId),
    onSuccess: (profile) => {
      queryClient.invalidateQueries({ queryKey: styleKeys.all });
      toast.success(`Activated Style Profile v${profile.version}`);
    },
    onError: (err: Error) => {
      toast.error(`Activation failed: ${err.message}`);
    },
  });
}

// --- Owner Notes Hooks ---

export function useOwnerNotes() {
  return useQuery({
    queryKey: styleKeys.notes(),
    queryFn: () => styleApi.listNotes(),
  });
}

export function useCreateOwnerNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: TOwnerNoteInput) => styleApi.createNote(input),
    onSuccess: (note) => {
      queryClient.invalidateQueries({ queryKey: styleKeys.notes() });
      toast.success(`Created note "${note.title}"`);
    },
    onError: (err: Error) => {
      toast.error(`Failed to create note: ${err.message}`);
    },
  });
}

export function useUpdateOwnerNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ noteId, input }: { noteId: string; input: TOwnerNoteInput }) =>
      styleApi.updateNote(noteId, input),
    onSuccess: (note) => {
      queryClient.invalidateQueries({ queryKey: styleKeys.notes() });
      toast.success(`Updated note "${note.title}"`);
    },
    onError: (err: Error) => {
      toast.error(`Failed to update note: ${err.message}`);
    },
  });
}

export function useDeleteOwnerNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (noteId: string) => styleApi.deleteNote(noteId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: styleKeys.notes() });
      toast.success("Owner note deleted");
    },
    onError: (err: Error) => {
      toast.error(`Failed to delete note: ${err.message}`);
    },
  });
}
