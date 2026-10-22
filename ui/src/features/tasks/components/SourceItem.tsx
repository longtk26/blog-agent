"use client";

import { CheckIcon, ChevronDownIcon, TriangleAlertIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { humanize } from "@/lib/format";
import type { TSource } from "../types";

type SourceItemProps = {
  source: TSource;
};

export function SourceItem({ source }: SourceItemProps) {
  const quality = source.quality_score !== null ? source.quality_score.toFixed(2) : null;
  return (
    <Collapsible className="rounded-lg border p-3">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <a
            href={source.canonical_url}
            target="_blank"
            rel="noreferrer noopener"
            className="line-clamp-1 text-sm font-medium hover:underline"
          >
            {source.title || source.canonical_url}
          </a>
          <p className="truncate text-xs text-muted-foreground">
            {[source.publisher, source.published_at, `round ${source.round}`].filter(Boolean).join(" · ")}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {source.source_type ? <Badge variant="secondary">{humanize(source.source_type)}</Badge> : null}
            {quality ? <Badge variant="outline">quality {quality}</Badge> : null}
            {source.status !== "assessed" ? (
              <Badge variant={source.status === "failed" ? "destructive" : "outline"}>{humanize(source.status)}</Badge>
            ) : null}
            {source.claims.length ? <Badge variant="outline">{source.claims.length} claims</Badge> : null}
          </div>
        </div>
        <CollapsibleTrigger className="rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label="Toggle details">
          <ChevronDownIcon className="size-4" />
        </CollapsibleTrigger>
      </div>
      <CollapsibleContent className="mt-3 space-y-3 border-t pt-3 text-sm">
        {source.error ? <p className="text-destructive">{source.error}</p> : null}
        {source.quality_rationale ? <p className="text-muted-foreground">{source.quality_rationale}</p> : null}
        {source.notes.length ? (
          <ul className="ml-5 list-disc space-y-1">
            {source.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : null}
        {source.claims.map((claim) => (
          <div key={claim.id} className="space-y-1 rounded-md bg-muted/50 p-2">
            <p className="flex items-start gap-2">
              {claim.quote_verified ? (
                <CheckIcon className="mt-0.5 size-4 shrink-0 text-success" aria-label="Quote verified" />
              ) : (
                <TriangleAlertIcon className="mt-0.5 size-4 shrink-0 text-warning" aria-label="Quote not found in page" />
              )}
              <span>
                {claim.question_id ? <span className="mr-1 font-mono text-xs text-muted-foreground">{claim.question_id}</span> : null}
                {claim.text}
              </span>
            </p>
            <blockquote className="border-l-2 pl-3 text-xs text-muted-foreground italic">“{claim.supporting_quote}”</blockquote>
          </div>
        ))}
        {source.query ? <p className="text-xs text-muted-foreground">Found via “{source.query}”</p> : null}
      </CollapsibleContent>
    </Collapsible>
  );
}
