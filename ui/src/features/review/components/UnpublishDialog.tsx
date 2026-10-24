"use client";

import { AlertTriangleIcon, Loader2Icon, Trash2Icon } from "lucide-react";
import { useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { TPublicationTarget } from "@/features/tasks/types";
import { useReviewActions } from "../hooks/use-review";

type UnpublishDialogProps = {
  taskId: string;
  slug: string;
  destination?: TPublicationTarget;
  disabled?: boolean;
};

export function UnpublishDialog({ taskId, slug, destination = "sanity", disabled }: UnpublishDialogProps) {
  const [open, setOpen] = useState(false);
  const [confirmSlug, setConfirmSlug] = useState("");
  const { unpublish } = useReviewActions(taskId);

  const isMatched = confirmSlug.trim() === slug.trim();
  const isPending = unpublish.isPending;

  const handleUnpublish = async () => {
    if (!isMatched || isPending) return;
    try {
      await unpublish.mutateAsync({ slug, destinations: [destination] });
      setOpen(false);
      setConfirmSlug("");
    } catch {
      // toast error handled in useReviewActions
    }
  };

  return (
    <Dialog open={open} onOpenChange={(val) => {
      setOpen(val);
      if (!val) setConfirmSlug("");
    }}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="text-destructive hover:bg-destructive/10 hover:text-destructive"
          disabled={disabled}
        >
          <Trash2Icon /> Unpublish
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangleIcon className="size-5" /> Unpublish from {destination === "sanity" ? "Sanity" : destination}
          </DialogTitle>
          <DialogDescription>
            This action deletes both draft and published documents from Sanity. The post will immediately become inaccessible on the website.
          </DialogDescription>
        </DialogHeader>

        <Alert variant="destructive" className="my-2">
          <AlertTitle>Warning</AlertTitle>
          <AlertDescription>
            To restore the article later, you will need to re-approve and publish a new revision.
          </AlertDescription>
        </Alert>

        <div className="space-y-3 py-2 text-sm">
          <Label htmlFor="unpublish-slug-input">
            Please type <span className="font-mono font-semibold text-foreground">{slug}</span> to confirm:
          </Label>
          <Input
            id="unpublish-slug-input"
            value={confirmSlug}
            onChange={(e) => setConfirmSlug(e.target.value)}
            placeholder={slug}
            autoComplete="off"
            autoFocus
          />
        </div>

        <DialogFooter className="mt-2">
          <Button type="button" variant="ghost" onClick={() => setOpen(false)} disabled={isPending}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={!isMatched || isPending}
            onClick={handleUnpublish}
          >
            {isPending ? <Loader2Icon className="animate-spin" /> : null}
            {isPending ? "Unpublishing…" : "Yes, unpublish post"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
