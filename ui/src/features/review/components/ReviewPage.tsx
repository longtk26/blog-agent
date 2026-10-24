"use client";

import { ArrowLeftIcon, Loader2Icon } from "lucide-react";
import Link from "next/link";

import { Container } from "@/components/layout/Container";
import { Stack } from "@/components/layout/Stack";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TaskStatusBadge } from "@/features/tasks/components/TaskStatusBadge";
import type { TTask } from "@/features/tasks/types";
import { useReviewStore } from "@/store/review-store";
import { isDraftDirty } from "../hooks/use-revision-editor";
import { useReview } from "../hooks/use-review";
import { ApproveDialog } from "./ApproveDialog";
import { PublishDialog } from "./PublishDialog";
import { RejectDialog } from "./RejectDialog";
import { RequestRevisionDialog } from "./RequestRevisionDialog";
import { ReviewMain } from "./ReviewMain";
import { ReviewSidebar } from "./ReviewSidebar";
import { RevisionSelector } from "./RevisionSelector";

function readOnlyReason(task: TTask, isLatest: boolean) {
  if (!isLatest) return "You are viewing an older revision. Select the latest revision to edit.";
  if (task.is_running) return "The agent is working on this task; editing unlocks when it pauses.";
  if (task.status === "rejected") return "This task is rejected. Clone it to start again.";
  return `A task in '${task.status.replaceAll("_", " ")}' cannot be edited.`;
}

function StatusNote({ task }: { task: TTask }) {
  if (task.is_running || task.status === "revision_requested") {
    return (
      <Alert>
        <Loader2Icon className="animate-spin" />
        <AlertTitle>The agent is revising</AlertTitle>
        <AlertDescription>A new revision appears here when it is done. Follow progress on the task page.</AlertDescription>
      </Alert>
    );
  }
  if (task.status === "publishing") {
    return (
      <Alert>
        <Loader2Icon className="animate-spin" />
        <AlertTitle>Publishing in progress</AlertTitle>
        <AlertDescription>Assets are being uploaded and the post document is syncing to Sanity.</AlertDescription>
      </Alert>
    );
  }
  if (task.status === "approved") {
    return (
      <Alert>
        <AlertTitle>Approved — ready to publish</AlertTitle>
        <AlertDescription>
          This revision is approved. Click <strong>Publish</strong> to sync it to Sanity. Editing now voids the approval and returns the task to review.
        </AlertDescription>
      </Alert>
    );
  }
  if (task.status === "published") {
    return (
      <Alert>
        <AlertTitle>Published on website</AlertTitle>
        <AlertDescription>
          This post is live on Sanity. Check the Publish tab in the sidebar to view links or unpublish.
        </AlertDescription>
      </Alert>
    );
  }
  if (task.status === "partially_published") {
    return (
      <Alert variant="destructive">
        <AlertTitle>Partially published</AlertTitle>
        <AlertDescription>
          Publishing failed on one or more destinations. Check the Publish tab in the sidebar to review and retry.
        </AlertDescription>
      </Alert>
    );
  }
  if (task.status === "failed") {
    const isPublishFailure = task.failed_stage === "publishing";
    return (
      <Alert variant="destructive">
        <AlertTitle>{isPublishFailure ? "Publishing failed" : "The last revision round failed"}</AlertTitle>
        <AlertDescription>{task.last_error ?? "Retry it from the task page."}</AlertDescription>
      </Alert>
    );
  }
  return null;
}

export function ReviewPage() {
  const review = useReview();
  const draft = useReviewStore((state) => state.draft);
  const { taskId, task, revision, revisions, latest } = review;

  if (review.isPending) {
    return (
      <Container size="xl">
        <Skeleton className="h-[70vh]" />
      </Container>
    );
  }
  if (review.error || !task) {
    return (
      <Container size="xl">
        <p className="py-12 text-center text-sm text-muted-foreground">{review.error?.message ?? "Task not found"}</p>
      </Container>
    );
  }
  if (!revision || !latest) {
    return (
      <Container size="xl">
        <p className="py-12 text-center text-sm text-muted-foreground">
          There is no draft to review yet. <Link href={`/tasks/${taskId}`} className="underline">Back to the task</Link>
        </p>
      </Container>
    );
  }

  const dirty = isDraftDirty(draft, draft?.baseRevisionId === revision.id ? revision : undefined);

  return (
    <Container size="xl">
      <Stack gap="md">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-2">
            <Button variant="ghost" size="sm" asChild className="-ml-2">
              <Link href={`/tasks/${taskId}`}>
                <ArrowLeftIcon /> Task
              </Link>
            </Button>
            <h1 className="text-xl font-semibold tracking-tight">{revision.title}</h1>
            <div className="flex flex-wrap items-center gap-2">
              <TaskStatusBadge status={task.status} running={task.is_running} />
              <RevisionSelector revisions={revisions} currentId={revision.id} dirty={dirty} />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <RejectDialog taskId={taskId} disabled={!review.canReject} />
            <RequestRevisionDialog taskId={taskId} revision={revision} disabled={!review.canReview || dirty} />
            <ApproveDialog task={task} revision={revision} disabled={!review.canReview || dirty} />
            <PublishDialog
              taskId={taskId}
              revision={revision}
              approvals={review.approvals}
              publications={review.publications}
              disabled={
                task.is_running ||
                dirty ||
                !review.approvals.some(
                  (a) => a.article_revision_id === revision.id && a.decision === "approved",
                )
              }
            />
          </div>
        </div>
        <StatusNote task={task} />
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
          <ReviewMain
            taskId={taskId}
            revision={revision}
            revisions={revisions}
            canEdit={review.canEdit}
            readOnlyReason={review.canEdit ? null : readOnlyReason(task, review.isLatest)}
          />
          <ReviewSidebar
            task={task}
            revision={revision}
            sources={review.sources}
            approvals={review.approvals}
            publications={review.publications}
            canEdit={review.canEdit}
          />
        </div>
      </Stack>
    </Container>
  );
}
