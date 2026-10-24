import { z } from "zod";

import type { TCreateTaskPayload, TTask } from "../types";

const optionalCount = (max: number) =>
  z
    .string()
    .trim()
    .refine((value) => value === "" || (/^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= max), {
      message: `Enter a number from 1 to ${max}`,
    });

export const createTaskSchema = z.object({
  topic: z.string().trim().min(5, "Describe the topic in at least 5 characters").max(500),
  mode: z.enum(["research_only", "article"]),
  audience: z.string().trim().max(300),
  depth: z.enum(["intro", "intermediate", "deep_dive"]),
  language: z.string().regex(/^[a-z]{2}(-[A-Z]{2})?$/, "Use a language code like en or vi"),
  format: z.enum(["concept", "tutorial", "comparison", "series_part"]),
  requirements: z.string().trim().max(4000),
  includeDiagram: z.enum(["auto", "yes", "no"]),
  diagramFormat: z.enum(["auto", "mermaid", "drawio"]),
  reviewOutline: z.boolean(),
  useStyleExamples: z.boolean(),
  publishToSanity: z.boolean(),
  publishToDevto: z.boolean(),
  seriesName: z.string().trim().max(120),
  seriesPart: optionalCount(100),
  maxQueries: optionalCount(20),
  maxSources: optionalCount(40),
  maxRounds: optionalCount(4),
  reuseSources: z.boolean(),
});

export type TCreateTaskFormValues = z.infer<typeof createTaskSchema>;

export const createTaskDefaults: TCreateTaskFormValues = {
  topic: "",
  mode: "article",
  audience: "",
  depth: "intermediate",
  language: "en",
  format: "concept",
  requirements: "",
  includeDiagram: "auto",
  diagramFormat: "auto",
  reviewOutline: false,
  useStyleExamples: true,
  publishToSanity: true,
  publishToDevto: false,
  seriesName: "",
  seriesPart: "",
  maxQueries: "",
  maxSources: "",
  maxRounds: "",
  reuseSources: false,
};

/** Prefill for "clone this task" (E4-S8). */
export function taskToFormValues(task: TTask): TCreateTaskFormValues {
  return {
    ...createTaskDefaults,
    topic: task.topic,
    mode: task.mode,
    audience: task.audience ?? "",
    depth: task.depth,
    language: task.language,
    format: task.format,
    requirements: task.requirements ?? "",
    includeDiagram: task.include_diagram,
    diagramFormat: task.diagram_format ?? "auto",
    reviewOutline: task.review_outline,
    useStyleExamples: task.use_style_examples ?? true,
    publishToSanity: task.publication_targets.includes("sanity"),
    publishToDevto: task.publication_targets.includes("devto"),
    seriesName: task.series?.name ?? "",
    seriesPart: task.series?.part ? String(task.series.part) : "",
    reuseSources: true,
  };
}

const toNumber = (value: string) => (value === "" ? undefined : Number(value));

export function toCreateTaskPayload(values: TCreateTaskFormValues, cloneFromTaskId?: string): TCreateTaskPayload {
  const budgets = {
    max_queries: toNumber(values.maxQueries),
    max_sources: toNumber(values.maxSources),
    max_research_rounds: toNumber(values.maxRounds),
  };
  const hasBudgets = Object.values(budgets).some((value) => value !== undefined);
  return {
    topic: values.topic,
    mode: values.mode,
    audience: values.audience || undefined,
    depth: values.depth,
    language: values.language,
    format: values.format,
    requirements: values.requirements || undefined,
    include_diagram: values.includeDiagram,
    diagram_format: values.diagramFormat,
    review_outline: values.reviewOutline,
    use_style_examples: values.useStyleExamples,
    publication_targets: [
      ...(values.publishToSanity ? (["sanity"] as const) : []),
      ...(values.publishToDevto ? (["devto"] as const) : []),
    ],
    series: values.seriesName ? { name: values.seriesName, part: toNumber(values.seriesPart) } : undefined,
    budgets: hasBudgets ? JSON.parse(JSON.stringify(budgets)) : undefined,
    ...(cloneFromTaskId ? { clone_from_task_id: cloneFromTaskId, reuse_sources: values.reuseSources } : {}),
  };
}
