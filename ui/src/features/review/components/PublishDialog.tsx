"use client";

import { ExternalLinkIcon, GlobeIcon, Loader2Icon, SendIcon } from "lucide-react";
import { useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field";
import type { TPublicationTarget, TRevision } from "@/features/tasks/types";
import { useReviewActions } from "../hooks/use-review";
import type { TApproval, TPublication } from "../types";

type PublishDialogProps = {
  taskId: string;
  revision: TRevision;
  approvals: TApproval[];
  publications: TPublication[];
  disabled: boolean;
};

export function PublishDialog({ taskId, revision, approvals, publications, disabled }: PublishDialogProps) {
  const [open, setOpen] = useState(false);
  const [destinations, setDestinations] = useState<TPublicationTarget[]>(["sanity"]);
  const { publish } = useReviewActions(taskId);

  const sanityApproval = approvals.find(
    (a) => a.article_revision_id === revision.id && a.destination === "sanity" && a.decision === "approved",
  );
  const isApproved = Boolean(sanityApproval);

  const existingSanityPub = publications.find(
    (p) => p.destination === "sanity" && p.status === "published",
  );
  const isAlreadyPublished = Boolean(existingSanityPub);

  const isPending = publish.isPending;

  const handlePublish = async () => {
    if (!isApproved || destinations.length === 0 || isPending) return;
    try {
      await publish.mutateAsync({
        revisionId: revision.id,
        destinations,
      });
      setOpen(false);
    } catch {
      // toast error handled in useReviewActions
    }
  };

  const liveUrl = `https://leon-pham.vercel.app/posts/${revision.slug}`;
  const studioUrl = `https://demmqb6o.sanity.studio/structure/post;${revision.slug}`;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button disabled={disabled}>
          <SendIcon /> Publish
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <GlobeIcon className="size-5 text-primary" />
            Publish r{revision.revision_number} to Website
          </DialogTitle>
          <DialogDescription>
            Sync this approved revision to Sanity so it appears on your live website.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2 text-sm">
          <dl className="grid gap-x-3 gap-y-1.5 rounded-lg border p-3 text-sm sm:grid-cols-[90px_1fr]">
            <dt className="text-muted-foreground">Revision</dt>
            <dd>
              r{revision.revision_number} · <span className="font-mono">{revision.content_hash.slice(0, 12)}</span>
            </dd>
            <dt className="text-muted-foreground">Title</dt>
            <dd className="font-medium">{revision.title}</dd>
            <dt className="text-muted-foreground">Slug</dt>
            <dd className="font-mono">{revision.slug}</dd>
            <dt className="text-muted-foreground">Live URL</dt>
            <dd>
              <a
                href={liveUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-primary hover:underline"
              >
                {liveUrl} <ExternalLinkIcon className="size-3" />
              </a>
            </dd>
            <dt className="text-muted-foreground">Studio URL</dt>
            <dd>
              <a
                href={studioUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground hover:underline"
              >
                Open in Sanity Studio <ExternalLinkIcon className="size-3" />
              </a>
            </dd>
          </dl>

          <FieldSet>
            <FieldLegend variant="label">Destinations</FieldLegend>
            <div className="flex flex-col gap-2.5 pt-1">
              <Field orientation="horizontal" className="w-auto">
                <Checkbox
                  id="pub-dest-sanity"
                  checked={destinations.includes("sanity")}
                  onCheckedChange={(checked) =>
                    setDestinations((prev) =>
                      checked ? [...prev, "sanity"] : prev.filter((d) => d !== "sanity"),
                    )
                  }
                />
                <FieldLabel htmlFor="pub-dest-sanity" className="font-normal">
                  Website (Sanity) — <span className="text-muted-foreground font-mono">demmqb6o / blogs</span>
                </FieldLabel>
              </Field>
            </div>
          </FieldSet>

          {isAlreadyPublished ? (
            <Alert>
              <AlertTitle>Republishing Article</AlertTitle>
              <AlertDescription>
                This article is already live. Publishing r{revision.revision_number} will update the post content in-place on Sanity while preserving the original <span className="font-mono">publishedAt</span> timestamp.
              </AlertDescription>
            </Alert>
          ) : null}

          {!isApproved ? (
            <Alert variant="destructive">
              <AlertTitle>Approval Required</AlertTitle>
              <AlertDescription>
                Revision r{revision.revision_number} must be approved before it can be published.
              </AlertDescription>
            </Alert>
          ) : null}
        </div>

        <DialogFooter className="mt-2">
          <Button type="button" variant="ghost" onClick={() => setOpen(false)} disabled={isPending}>
            Cancel
          </Button>
          <Button
            type="button"
            disabled={!isApproved || destinations.length === 0 || isPending}
            onClick={handlePublish}
          >
            {isPending ? <Loader2Icon className="animate-spin" /> : <SendIcon />}
            {isPending ? "Publishing…" : isAlreadyPublished ? `Update live post (r${revision.revision_number})` : `Publish now (r${revision.revision_number})`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
