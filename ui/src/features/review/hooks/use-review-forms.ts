import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";

import type { TRevision } from "@/features/tasks/types";
import { useReviewStore } from "@/store/review-store";
import { approveSchema, toApprovalPayload } from "../schemas/approve-schema";
import type { TApproveFormValues } from "../schemas/approve-schema";
import { metadataSchema, toArticleMetadata, toMetadataFormValues } from "../schemas/metadata-schema";
import type { TMetadataFormValues } from "../schemas/metadata-schema";
import { requestRevisionDefaults, requestRevisionSchema, toReviewPayload } from "../schemas/request-revision-schema";
import type { TRequestRevisionFormValues } from "../schemas/request-revision-schema";
import type { TArticleMetadata } from "../types";
import { useReviewActions } from "./use-review";

export function useRequestRevisionForm(taskId: string, revisionId: string, onDone: () => void) {
  const { review } = useReviewActions(taskId);
  const form = useForm<TRequestRevisionFormValues>({
    resolver: zodResolver(requestRevisionSchema),
    defaultValues: requestRevisionDefaults,
  });
  const onSubmit = form.handleSubmit(async (values) => {
    await review.mutateAsync(toReviewPayload(revisionId, values));
    form.reset(requestRevisionDefaults);
    onDone();
  });
  return { form, onSubmit, isSubmitting: review.isPending };
}

export function useRejectTask(taskId: string, onDone: () => void) {
  const { review } = useReviewActions(taskId);
  const reject = async (reason: string) => {
    await review.mutateAsync({ action: "reject", reason: reason.trim() || undefined });
    onDone();
  };
  return { reject, isSubmitting: review.isPending };
}

export function useApproveForm(
  taskId: string,
  revision: TRevision,
  defaults: Pick<TApproveFormValues, "destinations" | "blockerCount">,
  onDone: () => void,
) {
  const { approve } = useReviewActions(taskId);
  const form = useForm<TApproveFormValues>({
    resolver: zodResolver(approveSchema),
    defaultValues: { ...defaults, devtoMode: "draft", acknowledgeBlockers: false },
  });
  const onSubmit = form.handleSubmit(async (values) => {
    await approve.mutateAsync({ revisionId: revision.id, payload: toApprovalPayload(revision.content_hash, values) });
    onDone();
  });
  return { form, onSubmit, isSubmitting: approve.isPending };
}

/** Metadata form bound to the editor draft: valid edits flow into the review store as the owner types. */
export function useMetadataForm(metadata: TArticleMetadata) {
  const updateMetadata = useReviewStore((state) => state.updateMetadata);
  const setMetadataValid = useReviewStore((state) => state.setMetadataValid);
  const form = useForm<TMetadataFormValues>({
    resolver: zodResolver(metadataSchema),
    defaultValues: toMetadataFormValues(metadata),
    mode: "onChange",
  });
  const values = useWatch({ control: form.control });

  useEffect(() => {
    const parsed = metadataSchema.safeParse(values);
    setMetadataValid(parsed.success);
    if (parsed.success) updateMetadata(toArticleMetadata(parsed.data));
  }, [values, updateMetadata, setMetadataValid]);
  // Unmounted (sidebar tab switched): the store keeps the last valid metadata, so saving is safe again.
  useEffect(() => () => setMetadataValid(true), [setMetadataValid]);

  return { form };
}
