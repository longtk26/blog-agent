import { z } from "zod";

import type { TReviewPayload, TReviewTarget } from "../types";

export const REVIEW_TARGETS: { value: TReviewTarget; label: string; hint: string }[] = [
  { value: "auto", label: "Let the agent decide", hint: "Classifies the feedback into one of the stages below" },
  { value: "draft", label: "Rewrite sections", hint: "Rewrites only the selected sections" },
  { value: "research", label: "More research", hint: "Searches for new evidence, then rewrites the selected sections" },
  { value: "outline", label: "Restructure", hint: "New outline, then a full redraft" },
  { value: "metadata", label: "Metadata only", hint: "Title, description, slug or tags" },
  { value: "diagram", label: "Diagram", hint: "Rewrites the section holding the diagram (full diagram tools in Epic 7)" },
];

export const requestRevisionSchema = z.object({
  feedback: z.string().trim().min(3, "Tell the agent what to change").max(4000),
  target: z.enum(["auto", "research", "outline", "draft", "metadata", "diagram"]),
  sections: z.array(z.string()).max(20),
});

export type TRequestRevisionFormValues = z.infer<typeof requestRevisionSchema>;

export const requestRevisionDefaults: TRequestRevisionFormValues = { feedback: "", target: "auto", sections: [] };

export function toReviewPayload(revisionId: string, values: TRequestRevisionFormValues): TReviewPayload {
  return {
    action: "revise",
    revision_id: revisionId,
    feedback: values.feedback.trim(),
    scope: { target: values.target, sections: values.target === "metadata" || values.target === "outline" ? [] : values.sections },
  };
}
