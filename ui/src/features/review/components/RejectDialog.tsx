"use client";

import { ArchiveXIcon } from "lucide-react";
import { useState } from "react";

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
import { Field, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { useRejectTask } from "../hooks/use-review-forms";

type RejectDialogProps = {
  taskId: string;
  disabled: boolean;
};

export function RejectDialog({ taskId, disabled }: RejectDialogProps) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const { reject, isSubmitting } = useRejectTask(taskId, () => setOpen(false));

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" disabled={disabled}>
          <ArchiveXIcon /> Reject
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Reject this draft?</AlertDialogTitle>
          <AlertDialogDescription>
            The workflow ends and the task is archived with its revisions and sources. You can clone it into a new task later.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <Field>
          <FieldLabel htmlFor="reject-reason">Reason (optional)</FieldLabel>
          <Textarea id="reject-reason" rows={3} maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} />
        </Field>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep reviewing</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={isSubmitting}
            onClick={(event) => {
              event.preventDefault();
              void reject(reason);
            }}
          >
            Reject task
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
