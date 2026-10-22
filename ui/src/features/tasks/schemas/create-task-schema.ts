import { z } from "zod";

import type { TCreateTaskPayload } from "../types";

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
  reviewOutline: z.boolean(),
  publishToSanity: z.boolean(),
  publishToDevto: z.boolean(),
  seriesName: z.string().trim().max(120),
  seriesPart: optionalCount(100),
  maxQueries: optionalCount(20),
  maxSources: optionalCount(40),
  maxRounds: optionalCount(4),
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
  reviewOutline: false,
  publishToSanity: true,
  publishToDevto: false,
  seriesName: "",
  seriesPart: "",
  maxQueries: "",
  maxSources: "",
  maxRounds: "",
};

const toNumber = (value: string) => (value === "" ? undefined : Number(value));

export function toCreateTaskPayload(values: TCreateTaskFormValues): TCreateTaskPayload {
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
    review_outline: values.reviewOutline,
    publication_targets: [
      ...(values.publishToSanity ? (["sanity"] as const) : []),
      ...(values.publishToDevto ? (["devto"] as const) : []),
    ],
    series: values.seriesName ? { name: values.seriesName, part: toNumber(values.seriesPart) } : undefined,
    budgets: hasBudgets ? JSON.parse(JSON.stringify(budgets)) : undefined,
  };
}
