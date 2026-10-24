import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { diagramApi } from "../api/diagram-api";
import { taskKeys } from "@/features/tasks/query-keys";
import type { TDiagramAsset } from "../types";

export const diagramKeys = {
  all: ["diagrams"] as const,
  list: (taskId: string) => [...diagramKeys.all, "list", taskId] as const,
};

export function useDiagrams(taskId: string) {
  const queryClient = useQueryClient();

  const diagramsQuery = useQuery({
    queryKey: diagramKeys.list(taskId),
    queryFn: () => diagramApi.list(taskId),
    enabled: Boolean(taskId),
  });

  const switchFormatMutation = useMutation({
    mutationFn: ({ slotId, targetFormat }: { slotId: string; targetFormat: "drawio" | "mermaid" }) =>
      diagramApi.switchFormat(taskId, slotId, targetFormat),
    onSuccess: (updated) => {
      queryClient.setQueryData(diagramKeys.list(taskId), (old: TDiagramAsset[] | undefined) =>
        Array.isArray(old) ? old.map((d) => (d.slot_id === updated.slot_id ? updated : d)) : [updated]
      );
      toast.success(`Switched format to ${updated.format}`);
    },
    onError: (err: Error) => {
      toast.error(err?.message || "Failed to switch diagram format");
    },
  });

  const uploadMutation = useMutation({
    mutationFn: ({ slotId, file }: { slotId: string; file: File }) =>
      diagramApi.upload(taskId, slotId, file),
    onSuccess: (updated) => {
      queryClient.setQueryData(diagramKeys.list(taskId), (old: TDiagramAsset[] | undefined) =>
        Array.isArray(old) ? old.map((d) => (d.slot_id === updated.slot_id ? updated : d)) : [updated]
      );
      queryClient.invalidateQueries({ queryKey: taskKeys.revisions(taskId) });
      toast.success("Diagram replaced successfully");
    },
    onError: (err: Error) => {
      toast.error(err?.message || "Failed to replace diagram");
    },
  });

  const regenerateMutation = useMutation({
    mutationFn: ({ slotId, feedback }: { slotId: string; feedback: string }) =>
      diagramApi.regenerate(taskId, slotId, feedback),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: diagramKeys.list(taskId) });
      queryClient.invalidateQueries({ queryKey: taskKeys.detail(taskId) });
      queryClient.invalidateQueries({ queryKey: taskKeys.revisions(taskId) });
      toast.success("Diagram regeneration requested");
    },
    onError: (err: Error) => {
      toast.error(err?.message || "Failed to regenerate diagram");
    },
  });

  return {
    diagrams: diagramsQuery.data ?? [],
    isLoading: diagramsQuery.isLoading,
    refetch: diagramsQuery.refetch,
    switchFormat: switchFormatMutation.mutate,
    isSwitching: switchFormatMutation.isPending,
    upload: uploadMutation.mutate,
    isUploading: uploadMutation.isPending,
    regenerate: regenerateMutation.mutate,
    isRegenerating: regenerateMutation.isPending,
  };
}
