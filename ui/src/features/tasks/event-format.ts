import { humanize } from "@/lib/format";
import type { TTaskEvent } from "./types";

export type TEventTone = "default" | "success" | "warning" | "error" | "muted";

export type TEventView = {
  title: string;
  detail?: string;
  tone: TEventTone;
  noisy?: boolean;
};

const str = (value: unknown) => (value === undefined || value === null ? "" : String(value));

export function describeEvent(event: TTaskEvent): TEventView {
  const p = event.payload;
  switch (event.type) {
    case "status_changed":
      return {
        title: `Status: ${event.from_status ? `${humanize(event.from_status)} → ` : ""}${humanize(str(event.to_status))}`,
        detail: p.reason ? humanize(str(p.reason)) : str(p.error) || undefined,
        tone: event.to_status === "failed" ? "error" : event.to_status === "completed" ? "success" : "default",
      };
    case "plan_ready":
      return { title: `Research plan ready: ${str(p.questions)} questions, ${str(p.queries)} queries`, tone: "success" };
    case "query_issued":
      return { title: `Searched “${str(p.query)}”`, detail: `${str(p.results)} results`, tone: "default" };
    case "search_failed":
      return { title: `Search failed: “${str(p.query)}”`, detail: str(p.message), tone: "warning" };
    case "source_found":
      return { title: `Found: ${str(p.title) || str(p.url)}`, detail: str(p.url), tone: "muted" };
    case "source_extracted":
      return { title: `Read: ${str(p.title) || "page"}`, detail: `${Number(p.chars ?? 0).toLocaleString()} characters`, tone: "muted" };
    case "source_failed":
      return { title: `Could not use ${str(p.url)}`, detail: str(p.message), tone: "warning" };
    case "source_assessed": {
      const quality = Number(p.quality ?? 0).toFixed(2);
      return {
        title: `Assessed: ${str(p.title) || "source"}`,
        detail: `quality ${quality} · ${str(p.claims)} claims (${str(p.verified_claims)} verified quotes)${p.low_quality ? " · low quality" : ""}`,
        tone: p.low_quality ? "warning" : "default",
      };
    }
    case "coverage_checked": {
      const gaps = Array.isArray(p.gaps) ? p.gaps : [];
      return {
        title: `Coverage after round ${str(p.round)}`,
        detail: gaps.length ? `Unanswered: ${gaps.join(", ")}` : "Every question has evidence",
        tone: gaps.length ? "warning" : "success",
      };
    }
    case "follow_up_planned":
      return {
        title: `Follow-up round ${str(p.round)}`,
        detail: Array.isArray(p.queries) ? p.queries.join(" · ") : undefined,
        tone: "default",
      };
    case "brief_ready":
      return { title: "Research brief ready", detail: `${str(p.findings)} key findings`, tone: "success" };
    case "outline_ready":
      return { title: `Outline ready: “${str(p.title)}”`, detail: `${str(p.sections)} sections`, tone: "success" };
    case "outline_approved":
      return { title: p.edited ? "You edited and approved the outline" : "You approved the outline", tone: "success" };
    case "section_drafted":
      return { title: `Drafted: ${str(p.heading)}`, detail: `${str(p.words)} words`, tone: "default" };
    case "draft_assembled":
      return { title: `Draft assembled: ${str(p.title)}`, detail: `${str(p.words)} words`, tone: "default" };
    case "validation_done":
      return {
        title: "Automated checks",
        detail: `${str(p.blockers)} blockers · ${str(p.warnings)} warnings`,
        tone: Number(p.blockers) > 0 ? "warning" : "success",
      };
    case "judge_done": {
      const scores = (p.scores ?? {}) as Record<string, number>;
      const lowest = Math.min(...Object.values(scores));
      return {
        title: p.will_revise ? "Editor review: revising" : "Editor review",
        detail: `lowest score ${Number.isFinite(lowest) ? lowest : "?"}/5`,
        tone: p.needs_revision ? "warning" : "success",
      };
    }
    case "self_revision":
      return {
        title: `Self-revision round ${str(p.round)}`,
        detail: Array.isArray(p.sections) && p.sections.length ? `rewrote ${p.sections.join(", ")}` : "metadata only",
        tone: "default",
      };
    case "revision_saved":
      return { title: `Saved revision r${str(p.revision_number)}`, detail: `hash ${str(p.content_hash)}`, tone: "success" };
    case "paused": {
      const interrupts = Array.isArray(p.interrupts) ? (p.interrupts as Record<string, unknown>[]) : [];
      const kind = str(interrupts[0]?.type);
      const titles: Record<string, string> = {
        awaiting_promotion: "Paused — research complete, waiting for you",
        outline_review: "Paused — approve the outline to start drafting",
        awaiting_review: "Draft ready — waiting for your review",
      };
      return { title: titles[kind] ?? "Paused", tone: "warning" };
    }
    case "publishing_started":
      return {
        title: `Publishing to ${humanize(str(p.destination))}`,
        detail: p.revision_id ? `revision ${str(p.revision_id).slice(0, 8)}` : undefined,
        tone: "default",
      };
    case "asset_uploaded":
      return {
        title: `Uploaded ${str(p.filename) || str(p.asset_id)}`,
        detail: p.total ? `${str(p.index)} of ${str(p.total)} assets` : undefined,
        tone: "muted",
        noisy: true,
      };
    case "publish_succeeded":
      return {
        title: `Published to ${humanize(str(p.destination))}`,
        detail: str(p.url) || undefined,
        tone: "success",
      };
    case "publish_failed":
      return {
        title: `Publish failed: ${humanize(str(p.destination))}`,
        detail: str(p.error) || undefined,
        tone: "error",
      };
    case "unpublished":
      return {
        title: `Unpublished from ${humanize(str(p.destination))}`,
        detail: p.slug ? `slug: ${str(p.slug)}` : undefined,
        tone: "warning",
      };
    case "error":
      return { title: `Error in ${str(p.node) || str(p.stage) || "workflow"}`, detail: str(p.message), tone: "error" };
    case "info":
      return { title: str(p.message), tone: "muted" };
    case "node_started":
      return { title: `Started ${humanize(str(p.node))}`, tone: "muted", noisy: true };
    case "node_finished":
      return { title: `Finished ${humanize(str(p.node))}`, detail: `${(Number(p.duration_ms ?? 0) / 1000).toFixed(1)} s`, tone: "muted", noisy: true };
    case "budget_update":
      return { title: "Progress update", tone: "muted", noisy: true };
    default:
      return { title: humanize(event.type), tone: "muted" };
  }
}
