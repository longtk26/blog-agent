"use client";

import { ExternalLinkIcon } from "lucide-react";
import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import type { TSource } from "@/features/tasks/types";
import { cn } from "@/lib/utils";
import { sectionsCiting, splitSections } from "../markdown-sections";

type ReviewSourcesPanelProps = {
  markdown: string;
  sources: TSource[];
};

export function ReviewSourcesPanel({ markdown, sources }: ReviewSourcesPanelProps) {
  const rows = useMemo(() => {
    const sections = splitSections(markdown);
    return sources
      .filter((source) => source.status === "assessed" || source.status === "low_quality")
      .map((source) => ({ source, citedIn: sectionsCiting(sections, [source.canonical_url, source.url]) }))
      .sort((a, b) => b.citedIn.length - a.citedIn.length || (b.source.quality_score ?? 0) - (a.source.quality_score ?? 0));
  }, [markdown, sources]);

  if (!rows.length) return <p className="text-sm text-muted-foreground">No assessed sources.</p>;

  return (
    <ul className="space-y-2">
      {rows.map(({ source, citedIn }) => (
        <li key={source.id} className={cn("rounded-md border p-2.5 text-sm", !citedIn.length && "opacity-60")}>
          <div className="flex items-start justify-between gap-2">
            <span className="font-medium">{source.title ?? source.canonical_url}</span>
            <a
              href={source.canonical_url}
              target="_blank"
              rel="noreferrer noopener"
              className="shrink-0 text-muted-foreground hover:text-foreground"
              aria-label={`Open ${source.title ?? "source"}`}
            >
              <ExternalLinkIcon className="size-4" />
            </a>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            {source.publisher ? <span>{source.publisher}</span> : null}
            {source.source_type ? <Badge variant="outline">{source.source_type.replace(/_/g, " ")}</Badge> : null}
            {source.quality_score !== null ? (
              <Badge variant={source.status === "low_quality" ? "destructive" : "secondary"}>quality {source.quality_score.toFixed(2)}</Badge>
            ) : null}
          </div>
          <p className="mt-1.5 text-xs">
            {citedIn.length ? (
              <>
                <span className="text-muted-foreground">Cited in </span>
                {citedIn.join(", ")}
              </>
            ) : (
              <span className="text-muted-foreground">Not cited in this revision</span>
            )}
          </p>
        </li>
      ))}
    </ul>
  );
}
