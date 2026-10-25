"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ThumbsDownIcon, ThumbsUpIcon } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { reviewApi } from "../api/review-api";

type RevisionFeedbackProps = {
  taskId: string;
  revisionId: string;
  revisionNumber: number;
};

export function RevisionFeedback({ taskId, revisionId, revisionNumber }: RevisionFeedbackProps) {
  const [open, setOpen] = useState(false);
  const [rating, setRating] = useState<"positive" | "negative">("positive");
  const [comment, setComment] = useState("");
  const [submittedRating, setSubmittedRating] = useState<"positive" | "negative" | null>(null);

  const mutation = useMutation({
    mutationFn: (vars: { score: number; comment?: string }) =>
      reviewApi.submitFeedback(taskId, revisionId, vars),
    onSuccess: () => {
      setSubmittedRating(rating);
      setOpen(false);
      setComment("");
      toast.success(
        `Feedback (${rating === "positive" ? "👍 Positive" : "👎 Negative"}) logged to LangSmith trace`
      );
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed to submit feedback");
    },
  });

  const handleOpenDialog = (selectedRating: "positive" | "negative") => {
    setRating(selectedRating);
    setOpen(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate({
      score: rating === "positive" ? 1.0 : 0.0,
      comment: comment.trim() || undefined,
    });
  };

  return (
    <>
      <div className="flex items-center gap-1 rounded-md border bg-muted/30 p-0.5">
        <Button
          variant="ghost"
          size="sm"
          className={`h-7 w-7 p-0 ${
            submittedRating === "positive"
              ? "text-emerald-500 bg-emerald-500/10"
              : "text-muted-foreground hover:text-foreground"
          }`}
          title="Rate revision positively (Thumbs Up)"
          onClick={() => handleOpenDialog("positive")}
        >
          <ThumbsUpIcon className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className={`h-7 w-7 p-0 ${
            submittedRating === "negative"
              ? "text-rose-500 bg-rose-500/10"
              : "text-muted-foreground hover:text-foreground"
          }`}
          title="Rate revision negatively (Thumbs Down)"
          onClick={() => handleOpenDialog("negative")}
        >
          <ThumbsDownIcon className="h-3.5 w-3.5" />
        </Button>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                {rating === "positive" ? (
                  <>
                    <ThumbsUpIcon className="h-4 w-4 text-emerald-500" /> Positive Feedback
                  </>
                ) : (
                  <>
                    <ThumbsDownIcon className="h-4 w-4 text-rose-500" /> Negative Feedback
                  </>
                )}
                <span>— r{revisionNumber}</span>
              </DialogTitle>
              <DialogDescription>
                Provide optional notes on this revision. Your feedback is recorded on the root LangSmith trace for quality tracking.
              </DialogDescription>
            </DialogHeader>

            <div className="my-4 space-y-3">
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant={rating === "positive" ? "default" : "outline"}
                  size="sm"
                  className="gap-1.5"
                  onClick={() => setRating("positive")}
                >
                  <ThumbsUpIcon className="h-3.5 w-3.5" /> Good revision
                </Button>
                <Button
                  type="button"
                  variant={rating === "negative" ? "destructive" : "outline"}
                  size="sm"
                  className="gap-1.5"
                  onClick={() => setRating("negative")}
                >
                  <ThumbsDownIcon className="h-3.5 w-3.5" /> Needs improvement
                </Button>
              </div>

              <Textarea
                placeholder="What went well or what was wrong? (e.g. style was too formal, claims were well-supported...)"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={3}
                className="text-sm"
              />
            </div>

            <DialogFooter className="gap-2 sm:gap-0">
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "Submitting..." : "Send Feedback"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
