"use client";

import { Badge } from "@/components/ui/badge";
import type { TClaimMapEntry, TRevision, TSource } from "@/features/tasks/types";
import { useReviewStore } from "@/store/review-store";
import { INTRO } from "../markdown-sections";

const SUPPORT_VARIANT = { supported: "secondary", partial: "outline", unsupported: "destructive" } as const;

type ClaimsPanelProps = {
  revision: TRevision;
  sources: TSource[];
};

export function ClaimsPanel({ revision, sources }: ClaimsPanelProps) {
  const highlight = useReviewStore((state) => state.highlight);
  const claimMap = revision.metadata.claim_map ?? {};
  const unsupported = revision.metadata.unsupported_statements ?? [];
  const headings = new Map((revision.metadata.outline?.sections ?? []).map((s) => [s.key, s.heading]));
  const sourceOfClaim = new Map(sources.flatMap((source) => source.claims.map((claim) => [claim.id, source] as const)));
  const groups = Object.entries(claimMap).filter(([, entries]) => entries.length);

  // Hover/focus paints the sentence in the preview; click also scrolls the preview to it.
  const hoverProps = (sentence: string) => ({
    onMouseEnter: () => highlight(sentence),
    onClick: () => highlight(sentence, true),
    onMouseLeave: () => highlight(null),
    onFocus: () => highlight(sentence),
    onBlur: () => highlight(null),
  });

  return (
    <div className="space-y-5">
      <p className="text-xs text-muted-foreground">Hover a statement to highlight it in the preview; click to scroll to it.</p>
      {unsupported.length ? (
        <section className="space-y-1.5">
          <h3 className="text-xs font-medium text-muted-foreground uppercase">Flagged by the AI editor</h3>
          <ul className="space-y-1">
            {unsupported.map((statement) => (
              <li key={statement} tabIndex={0} className="cursor-pointer rounded-md px-2 py-1.5 text-sm hover:bg-muted" {...hoverProps(statement)}>
                <Badge variant="destructive" className="mr-1.5">
                  no evidence
                </Badge>
                {statement}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {groups.length ? (
        groups.map(([key, entries]) => (
          <section key={key} className="space-y-1.5">
            <h3 className="text-xs font-medium text-muted-foreground uppercase">{key === "intro" ? INTRO : (headings.get(key) ?? key)}</h3>
            <ul className="space-y-1">
              {entries.map((entry: TClaimMapEntry, index) => {
                const linked = [...new Map(entry.claim_ids.flatMap((id) => {
                  const source = sourceOfClaim.get(id);
                  return source ? [[source.id, source] as const] : [];
                })).values()];
                return (
                  <li key={`${key}-${index}`} tabIndex={0} className="cursor-pointer rounded-md px-2 py-1.5 text-sm hover:bg-muted" {...hoverProps(entry.sentence)}>
                    <Badge variant={SUPPORT_VARIANT[entry.support]} className="mr-1.5">
                      {entry.support}
                    </Badge>
                    {entry.sentence}
                    {linked.length ? (
                      <span className="mt-1 flex flex-wrap gap-x-2 text-xs">
                        {linked.map((source) => (
                          <a key={source.id} href={source.canonical_url} target="_blank" rel="noreferrer noopener" className="text-primary underline underline-offset-2">
                            {source.title ?? source.publisher ?? "source"}
                          </a>
                        ))}
                      </span>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </section>
        ))
      ) : (
        <p className="text-sm text-muted-foreground">No claim map for this revision (owner-edited sections drop their stale claims).</p>
      )}
    </div>
  );
}
