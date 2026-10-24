"use client";

import { CopyIcon, ExternalLinkIcon, PencilRulerIcon, RotateCcwIcon, SquareIcon } from "lucide-react";
import Link from "next/link";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { useCancelTask, useRetryTask } from "../hooks/use-task-actions";
import type { TTask, TTaskStatus } from "../types";
import { PromoteDialog } from "./PromoteDialog";

const NOT_CANCELLABLE: TTaskStatus[] = ["rejected", "published", "partially_published", "approved", "publishing"];

type TaskActionsProps = {
  task: TTask;
};

export function TaskActions({ task }: TaskActionsProps) {
  const cancel = useCancelTask();
  const retry = useRetryTask();
  const canRetry = task.status === "failed" && task.resumable && !task.is_running;
  const canPromote = task.status === "completed" && task.mode === "research_only" && !task.is_running;
  const canCancel = !NOT_CANCELLABLE.includes(task.status);
  const canReview = ["awaiting_review", "revision_requested", "approved", "published", "partially_published"].includes(task.status);

  return (
    <div className="flex flex-wrap items-center gap-2">
      {task.trace_url ? (
        <Button variant="ghost" size="sm" asChild>
          <a href={task.trace_url} target="_blank" rel="noreferrer noopener">
            LangSmith trace <ExternalLinkIcon />
          </a>
        </Button>
      ) : null}
      {canRetry ? (
        <Button variant="outline" onClick={() => retry.mutate(task.id)} disabled={retry.isPending}>
          <RotateCcwIcon /> Retry
        </Button>
      ) : null}
      {canPromote ? <PromoteDialog task={task} /> : null}
      {task.status === "rejected" ? (
        <Button variant="outline" asChild>
          <Link href={`/tasks/new?from=${task.id}`}>
            <CopyIcon /> Clone
          </Link>
        </Button>
      ) : null}
      {canReview ? (
        <Button asChild>
          <Link href={`/tasks/${task.id}/review`}>
            <PencilRulerIcon /> Review
          </Link>
        </Button>
      ) : null}
      {canCancel ? (
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="outline" disabled={cancel.isPending}>
              <SquareIcon /> Cancel
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Cancel this task?</AlertDialogTitle>
              <AlertDialogDescription>
                The agent stops and the task is archived. Its research and sources are kept.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep running</AlertDialogCancel>
              <AlertDialogAction variant="destructive" onClick={() => cancel.mutate(task.id)}>
                Cancel task
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      ) : null}
    </div>
  );
}
