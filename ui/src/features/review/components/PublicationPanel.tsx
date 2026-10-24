"use client";

import {
  AlertCircleIcon,
  CheckCircle2Icon,
  ExternalLinkIcon,
  GlobeIcon,
  Loader2Icon,
  RefreshCwIcon,
  Share2Icon,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TRevision, TTask } from "@/features/tasks/types";
import { formatDateTime } from "@/lib/format";
import { useReviewActions } from "../hooks/use-review";
import type { TApproval, TPublication, TPublicationStatus } from "../types";
import { UnpublishDialog } from "./UnpublishDialog";

type PublicationPanelProps = {
  task: TTask;
  revision: TRevision;
  approvals?: TApproval[];
  publications: TPublication[];
};

function StatusBadge({ status }: { status: TPublicationStatus }) {
  switch (status) {
    case "published":
      return (
        <Badge variant="default" className="bg-emerald-600 hover:bg-emerald-700">
          <CheckCircle2Icon className="mr-1 size-3" /> Published
        </Badge>
      );
    case "pending":
      return (
        <Badge variant="secondary">
          <Loader2Icon className="mr-1 size-3 animate-spin" /> Publishing…
        </Badge>
      );
    case "failed":
      return (
        <Badge variant="destructive">
          <AlertCircleIcon className="mr-1 size-3" /> Failed
        </Badge>
      );
    case "unpublished":
      return <Badge variant="outline">Unpublished</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

export function PublicationPanel({ task, revision, approvals, publications }: PublicationPanelProps) {
  const { retryPublication } = useReviewActions(task.id);
  const sanityPub = publications.find((p) => p.destination === "sanity");
  const devtoPub = publications.find((p) => p.destination === "devto");

  const sanityLiveUrl = sanityPub?.destination_url ?? `https://leon-pham.vercel.app/posts/${revision.slug}`;
  const studioUrl =
    (sanityPub?.destination_meta?.studio_url as string | undefined) ??
    `https://demmqb6o.sanity.studio/structure/post;${revision.slug}`;

  // Find devto approval to display configured mode
  const devtoApproval = approvals?.find(
    (a) => a.destination === "devto" && a.decision === "approved",
  );
  const devtoMode =
    (devtoApproval?.options?.devto_mode as string | undefined) ||
    (devtoApproval?.options?.mode as string | undefined) ||
    "draft";

  const devtoRemoteUrl = devtoPub?.destination_url || devtoPub?.remote_url || "https://dev.to/dashboard";
  const isDevtoDraft = devtoMode === "draft";

  return (
    <div className="space-y-4 py-2">
      <div>
        <h3 className="text-sm font-semibold tracking-tight">Destinations & Publications</h3>
        <p className="text-xs text-muted-foreground">
          Track publishing outcomes, view live post URLs, and manage live status.
        </p>
      </div>

      {/* Website (Sanity) */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <GlobeIcon className="size-4 text-primary" />
              <CardTitle className="text-sm font-medium">Website (Sanity)</CardTitle>
            </div>
            {sanityPub ? (
              <StatusBadge status={sanityPub.status} />
            ) : (
              <Badge variant="outline">Not published</Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-xs">
          {sanityPub ? (
            <>
              <dl className="grid grid-cols-[100px_1fr] gap-x-2 gap-y-1.5 border-t pt-2.5">
                <dt className="text-muted-foreground">Status</dt>
                <dd className="font-medium capitalize">{sanityPub.status}</dd>

                {sanityPub.published_at ? (
                  <>
                    <dt className="text-muted-foreground">Published</dt>
                    <dd title={sanityPub.published_at}>{formatDateTime(sanityPub.published_at)}</dd>
                  </>
                ) : null}

                {sanityPub.unpublished_at ? (
                  <>
                    <dt className="text-muted-foreground">Unpublished</dt>
                    <dd title={sanityPub.unpublished_at}>{formatDateTime(sanityPub.unpublished_at)}</dd>
                  </>
                ) : null}

                <dt className="text-muted-foreground">Attempts</dt>
                <dd>{sanityPub.attempt_count} / 3</dd>

                {sanityPub.rendered_content_hash ? (
                  <>
                    <dt className="text-muted-foreground">Content Hash</dt>
                    <dd className="font-mono">{sanityPub.rendered_content_hash.slice(0, 12)}</dd>
                  </>
                ) : null}

                <dt className="text-muted-foreground">Live URL</dt>
                <dd>
                  <a
                    href={sanityLiveUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 font-mono text-primary hover:underline break-all"
                  >
                    {sanityLiveUrl} <ExternalLinkIcon className="size-3 shrink-0" />
                  </a>
                </dd>

                <dt className="text-muted-foreground">Sanity Studio</dt>
                <dd>
                  <a
                    href={studioUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground hover:underline"
                  >
                    Open document in Studio <ExternalLinkIcon className="size-3 shrink-0" />
                  </a>
                </dd>
              </dl>

              {sanityPub.status === "failed" && sanityPub.last_error ? (
                <Alert variant="destructive" className="mt-2 text-xs">
                  <AlertTitle className="text-xs">Publishing Error</AlertTitle>
                  <AlertDescription className="break-all font-mono text-xs">
                    {sanityPub.last_error}
                  </AlertDescription>
                </Alert>
              ) : null}

              <div className="flex flex-wrap items-center justify-end gap-2 border-t pt-3">
                {sanityPub.status === "failed" ? (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={retryPublication.isPending || task.is_running}
                    onClick={() => retryPublication.mutate("sanity")}
                  >
                    {retryPublication.isPending ? (
                      <Loader2Icon className="animate-spin" />
                    ) : (
                      <RefreshCwIcon />
                    )}
                    Retry Publish
                  </Button>
                ) : null}

                {sanityPub.status === "published" ? (
                  <UnpublishDialog
                    taskId={task.id}
                    slug={revision.slug}
                    destination="sanity"
                    disabled={task.is_running}
                  />
                ) : null}
              </div>
            </>
          ) : (
            <div className="space-y-2 border-t pt-2.5 text-muted-foreground">
              <p>
                No publish attempts recorded yet. Once approved, click the{" "}
                <span className="font-medium text-foreground">Publish</span> button in the action bar to push to Sanity.
              </p>
              <div className="rounded-md bg-muted/50 p-2.5 text-xs font-mono space-y-1">
                <div>Target Dataset: demmqb6o / blogs</div>
                <div>Live Path: /posts/{revision.slug}</div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* DEV Community (Dev.to) (Epic 8) */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Share2Icon className="size-4 text-primary" />
              <CardTitle className="text-sm font-medium">DEV Community (dev.to)</CardTitle>
            </div>
            <div className="flex items-center gap-1.5">
              <Badge variant="secondary" className="capitalize text-xs">
                {devtoMode}
              </Badge>
              {devtoPub ? (
                <StatusBadge status={devtoPub.status} />
              ) : (
                <Badge variant="outline">Not published</Badge>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-xs">
          {devtoPub ? (
            <>
              <dl className="grid grid-cols-[100px_1fr] gap-x-2 gap-y-1.5 border-t pt-2.5">
                <dt className="text-muted-foreground">Status</dt>
                <dd className="font-medium capitalize">{devtoPub.status}</dd>

                <dt className="text-muted-foreground">Mode</dt>
                <dd className="capitalize">{devtoMode}</dd>

                {devtoPub.published_at ? (
                  <>
                    <dt className="text-muted-foreground">Last Sync</dt>
                    <dd title={devtoPub.published_at}>{formatDateTime(devtoPub.published_at)}</dd>
                  </>
                ) : null}

                <dt className="text-muted-foreground">Attempts</dt>
                <dd>{devtoPub.attempt_count} / 3</dd>

                {devtoPub.rendered_content_hash ? (
                  <>
                    <dt className="text-muted-foreground">Content Hash</dt>
                    <dd className="font-mono">{devtoPub.rendered_content_hash.slice(0, 12)}</dd>
                  </>
                ) : null}

                <dt className="text-muted-foreground">
                  {isDevtoDraft ? "Edit URL" : "Remote URL"}
                </dt>
                <dd>
                  <a
                    href={devtoRemoteUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 font-mono text-primary hover:underline break-all"
                  >
                    {isDevtoDraft ? "Open Dev.to Dashboard" : devtoRemoteUrl}{" "}
                    <ExternalLinkIcon className="size-3 shrink-0" />
                  </a>
                </dd>
              </dl>

              {devtoPub.status === "failed" && devtoPub.last_error ? (
                <Alert variant="destructive" className="mt-2 text-xs">
                  <AlertTitle className="text-xs">Publishing Error</AlertTitle>
                  <AlertDescription className="break-all font-mono text-xs">
                    {devtoPub.last_error}
                  </AlertDescription>
                </Alert>
              ) : null}

              <div className="flex flex-wrap items-center justify-end gap-2 border-t pt-3">
                {devtoPub.status === "failed" ? (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={retryPublication.isPending || task.is_running}
                    onClick={() => retryPublication.mutate("devto")}
                  >
                    {retryPublication.isPending ? (
                      <Loader2Icon className="animate-spin" />
                    ) : (
                      <RefreshCwIcon />
                    )}
                    Retry Dev.to
                  </Button>
                ) : null}

                {devtoPub.status === "published" ? (
                  <UnpublishDialog
                    taskId={task.id}
                    slug={revision.slug}
                    destination="devto"
                    disabled={task.is_running}
                  />
                ) : null}
              </div>
            </>
          ) : (
            <div className="space-y-2 border-t pt-2.5 text-muted-foreground">
              <p>
                No Dev.to publication recorded yet. When approved for DEV Community, publishing pushes a {devtoMode} post to dev.to.
              </p>
              <div className="rounded-md bg-muted/50 p-2.5 text-xs font-mono space-y-1">
                <div>Target: https://dev.to/api/articles</div>
                <div>Approved Mode: {devtoMode}</div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
