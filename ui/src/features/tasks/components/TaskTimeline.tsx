"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { describeEvent } from "../event-format";
import type { TEventTone } from "../event-format";
import type { TTaskEvent } from "../types";

const toneClass: Record<TEventTone, string> = {
  default: "bg-primary",
  success: "bg-success",
  warning: "bg-warning",
  error: "bg-destructive",
  muted: "bg-muted-foreground/40",
};

type TaskTimelineProps = {
  events: TTaskEvent[];
  connected: boolean;
};

export function TaskTimeline({ events, connected }: TaskTimelineProps) {
  const [showAll, setShowAll] = useState(false);
  const views = events.map((event) => ({ event, view: describeEvent(event) }));
  const visible = (showAll ? views : views.filter(({ view }) => !view.noisy)).reverse();

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-2">
          <span className={cn("size-1.5 rounded-full", connected ? "bg-success animate-pulse" : "bg-muted-foreground/40")} />
          {connected ? "Live" : "Not streaming"} · {events.length} events
        </span>
        <Button variant="ghost" size="sm" onClick={() => setShowAll((value) => !value)}>
          {showAll ? "Hide step details" : "Show step details"}
        </Button>
      </div>
      <ScrollArea className="h-[480px] pr-3">
        {visible.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">Waiting for the first event…</p>
        ) : (
          <ol className="relative space-y-4 border-l pl-5">
            {visible.map(({ event, view }) => (
              <li key={event.id} className="relative">
                <span className={cn("absolute top-1.5 -left-[25px] size-2.5 rounded-full ring-4 ring-background", toneClass[view.tone])} />
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <p className={cn("text-sm", view.tone === "muted" && "text-muted-foreground")}>{view.title}</p>
                  <time className="font-mono text-xs text-muted-foreground">{formatTime(event.created_at)}</time>
                </div>
                {view.detail ? <p className="mt-0.5 text-xs break-all text-muted-foreground">{view.detail}</p> : null}
              </li>
            ))}
          </ol>
        )}
      </ScrollArea>
    </div>
  );
}
