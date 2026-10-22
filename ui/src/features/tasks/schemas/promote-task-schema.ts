import { z } from "zod";

import type { TPromotePayload } from "../types";

export const promoteTaskSchema = z.object({
  angle: z.string().trim().max(300),
  audience: z.string().trim().max(300),
  requirements: z.string().trim().max(4000),
});

export type TPromoteTaskFormValues = z.infer<typeof promoteTaskSchema>;

export function toPromotePayload(values: TPromoteTaskFormValues): TPromotePayload {
  return {
    angle: values.angle || undefined,
    audience: values.audience || undefined,
    requirements: values.requirements || undefined,
  };
}
