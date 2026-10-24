"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLinkIcon, InfoIcon, Share2Icon } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { TRevision } from "@/features/tasks/types";
import { reviewApi } from "../api/review-api";

type DevtoPreviewProps = {
  revision: TRevision;
};

export function DevtoPreview({ revision }: DevtoPreviewProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["devto-preview", revision.id],
    queryFn: () => reviewApi.devtoPreview(revision.id),
  });

  if (isLoading) {
    return (
      <div className="space-y-4 py-4">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Preview Unavailable</AlertTitle>
        <AlertDescription>
          Failed to generate Dev.to transformed preview: {String(error ?? "No data returned")}
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-4 py-2">
      <Alert className="border-primary/20 bg-primary/5">
        <InfoIcon className="size-4 text-primary" />
        <AlertTitle className="text-sm font-semibold flex items-center gap-2">
          <Share2Icon className="size-4" />
          Dev.to Markdown Transformation Preview
        </AlertTitle>
        <AlertDescription className="text-xs text-muted-foreground mt-1">
          This preview shows the exact Markdown that will be pushed to the DEV Community API. The leading H1 is stripped, LaTeX is converted to clean code blocks, Mermaid blocks are replaced with images, and a canonical URL link is appended. Styling on dev.to will match the reader&apos;s personal theme.
        </AlertDescription>
      </Alert>

      {/* Dev.to Metadata Card */}
      <div className="rounded-lg border bg-card p-4 text-xs space-y-2.5">
        <div className="grid grid-cols-[110px_1fr] gap-x-2 gap-y-1.5 items-center">
          <span className="text-muted-foreground font-medium">DEV Post Title:</span>
          <span className="font-semibold text-sm">{data.title}</span>

          <span className="text-muted-foreground font-medium">Tags (max 4):</span>
          <div className="flex flex-wrap gap-1.5">
            {data.tags.map((tag) => (
              <Badge key={tag} variant="secondary" className="font-mono text-xs">
                #{tag}
              </Badge>
            ))}
          </div>

          {data.canonical_url ? (
            <>
              <span className="text-muted-foreground font-medium">Canonical URL:</span>
              <a
                href={data.canonical_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-mono text-primary hover:underline break-all"
              >
                {data.canonical_url} <ExternalLinkIcon className="size-3 shrink-0" />
              </a>
            </>
          ) : null}

          {data.main_image ? (
            <>
              <span className="text-muted-foreground font-medium">Cover (Raster):</span>
              <span className="font-mono truncate">{data.main_image}</span>
            </>
          ) : null}

          <span className="text-muted-foreground font-medium">Content Hash:</span>
          <span className="font-mono text-muted-foreground">{data.rendered_content_hash.slice(0, 12)}</span>
        </div>
      </div>

      {/* Rendered Markdown Body */}
      <div className="rounded-lg border bg-background p-6">
        <article className="prose dark:prose-invert max-w-none text-sm leading-relaxed">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              img: ({ src, alt }) => (
                <span className="my-4 block">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={src}
                    alt={alt || ""}
                    className="rounded-md border max-h-96 max-w-full object-contain mx-auto"
                  />
                  {alt ? <span className="block text-center text-xs text-muted-foreground mt-1">{alt}</span> : null}
                </span>
              ),
              pre: ({ children }) => (
                <pre className="my-3 overflow-x-auto rounded-md bg-zinc-900 p-3 text-xs text-zinc-100 font-mono">
                  {children}
                </pre>
              ),
              code: ({ children, className }) => {
                const isInline = !className;
                if (isInline) {
                  return (
                    <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-emerald-500 dark:text-emerald-400">
                      {children}
                    </code>
                  );
                }
                return <code>{children}</code>;
              },
            }}
          >
            {data.body_markdown}
          </ReactMarkdown>
        </article>
      </div>
    </div>
  );
}
