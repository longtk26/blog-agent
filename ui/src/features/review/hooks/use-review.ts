import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useEffect } from "react";
import { toast } from "sonner";

import { tasksApi } from "@/features/tasks/api/tasks-api";
import { useTask, useTaskSources } from "@/features/tasks/hooks/use-task";
import { useTaskEvents } from "@/features/tasks/hooks/use-task-events";
import { taskKeys } from "@/features/tasks/query-keys";
import { isTaskLive } from "@/features/tasks/status";
import type { TTaskStatus } from "@/features/tasks/types";
import { ApiError } from "@/lib/api-client";
import { useReviewStore } from "@/store/review-store";
import { reviewApi } from "../api/review-api";
import type { TApprovalPayload, TOwnerRevisionPayload, TReviewPayload } from "../types";
import { clearStoredDraft } from "./use-revision-editor";

const EDITABLE: TTaskStatus[] = ["awaiting_review", "approved", "published", "partially_published"];

/** Server data for the review page (React Query) plus the selection from the review store. */
export function useReview() {
  const { id: taskId } = useParams<{ id: string }>();
  const openTask = useReviewStore((state) => state.openTask);
  const selectedRevisionId = useReviewStore((state) => state.selectedRevisionId);
  useEffect(() => openTask(taskId), [openTask, taskId]);

  const taskQuery = useTask(taskId);
  const task = taskQuery.data;
  const { events, connected } = useTaskEvents(taskId, task ? isTaskLive(task) : true);
  const revisionsQuery = useQuery({ queryKey: taskKeys.revisions(taskId), queryFn: () => tasksApi.revisions(taskId) });
  const revisions = revisionsQuery.data?.items ?? [];
  const latest = revisions[0];
  const currentId = selectedRevisionId ?? latest?.id;
  const revisionQuery = useQuery({
    queryKey: taskKeys.revision(currentId ?? "none"),
    queryFn: () => tasksApi.revision(currentId as string),
    enabled: Boolean(currentId),
  });
  const sources = useTaskSources(taskId);
  const approvals = useQuery({ queryKey: taskKeys.approvals(taskId), queryFn: () => reviewApi.approvals(taskId) });
  const publications = useQuery({ queryKey: taskKeys.publications(taskId), queryFn: () => reviewApi.publications(taskId) });

  const revision = revisionQuery.data;
  const isLatest = Boolean(revision && latest && revision.id === latest.id);
  const idle = Boolean(task && !task.is_running);
  const waitingForReview = task?.pending_interrupt?.type === "awaiting_review";

  return {
    taskId,
    task,
    events,
    connected,
    revisions,
    latest,
    revision,
    sources: sources.data?.items ?? [],
    approvals: approvals.data?.items ?? [],
    publications: publications.data?.items ?? [],
    isLatest,
    canEdit: Boolean(task && isLatest && idle && EDITABLE.includes(task.status)),
    canReview: Boolean(task && isLatest && idle && task.status === "awaiting_review" && waitingForReview),
    canReject: Boolean(task && !["rejected", "publishing", "published", "partially_published"].includes(task.status)),
    isPending: taskQuery.isPending || revisionsQuery.isPending || (Boolean(currentId) && revisionQuery.isPending),
    error: taskQuery.error ?? revisionsQuery.error,
  };
}

function errorMessage(error: Error) {
  if (error instanceof ApiError && error.code === "STALE_REVISION") return `${error.message}.`;
  return error.message;
}

export function useReviewActions(taskId: string) {
  const queryClient = useQueryClient();
  const discardDraft = useReviewStore((state) => state.discardDraft);
  const selectRevision = useReviewStore((state) => state.selectRevision);
  const setMode = useReviewStore((state) => state.setMode);
  const refresh = () => queryClient.invalidateQueries({ queryKey: taskKeys.detail(taskId) });
  const onError = (error: Error) => {
    toast.error(errorMessage(error));
    if (error instanceof ApiError && error.status === 409) refresh();
  };

  const save = useMutation({
    mutationFn: (payload: TOwnerRevisionPayload) => reviewApi.saveRevision(taskId, payload),
    onSuccess: (revision, payload) => {
      clearStoredDraft(taskId, payload.base_revision_id);
      discardDraft();
      selectRevision(null);
      setMode("preview");
      queryClient.setQueryData(taskKeys.revision(revision.id), revision);
      refresh();
      toast.success(`Saved as r${revision.revision_number}`);
    },
    onError,
  });

  const review = useMutation({
    mutationFn: (payload: TReviewPayload) => reviewApi.review(taskId, payload),
    onSuccess: (task, payload) => {
      queryClient.setQueryData(taskKeys.detail(taskId), task);
      refresh();
      queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
      toast.success(payload.action === "revise" ? "Revision requested — the agent is working on it" : "Task rejected and archived");
    },
    onError,
  });

  const approve = useMutation({
    mutationFn: ({ revisionId, payload }: { revisionId: string; payload: TApprovalPayload }) => reviewApi.approve(revisionId, payload),
    onSuccess: (result) => {
      refresh();
      queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
      toast.success(`Approved for ${result.items.map((a) => a.destination).join(" and ")}`);
    },
    onError,
  });

  const publish = useMutation({
    mutationFn: ({ revisionId, destinations }: { revisionId: string; destinations: string[] }) =>
      reviewApi.publish(revisionId, destinations),
    onSuccess: (result) => {
      refresh();
      queryClient.invalidateQueries({ queryKey: taskKeys.publications(taskId) });
      queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
      toast.success(`Published to ${result.items.map((p) => p.destination).join(", ")}`);
    },
    onError,
  });

  const retryPublication = useMutation({
    mutationFn: (destination: string) => reviewApi.retryPublication(taskId, destination),
    onSuccess: (result) => {
      refresh();
      queryClient.invalidateQueries({ queryKey: taskKeys.publications(taskId) });
      queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
      toast.success(`Retried publishing to ${result.items.map((p) => p.destination).join(", ")}`);
    },
    onError,
  });

  const unpublish = useMutation({
    mutationFn: (payload: { slug: string; destinations?: string[] }) => reviewApi.unpublish(taskId, payload),
    onSuccess: (result) => {
      refresh();
      queryClient.invalidateQueries({ queryKey: taskKeys.publications(taskId) });
      queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
      toast.success(`Unpublished ${result.items.map((p) => p.destination).join(", ")}`);
    },
    onError,
  });

  return { save, review, approve, publish, retryPublication, unpublish };
}
