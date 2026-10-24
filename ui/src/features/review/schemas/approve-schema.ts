import { z } from "zod";

import type { TApprovalPayload } from "../types";

export const approveSchema = z
  .object({
    destinations: z.array(z.enum(["sanity", "devto"])).min(1, "Choose at least one destination"),
    devtoMode: z.enum(["draft", "published"]),
    blockerCount: z.number(),
    acknowledgeBlockers: z.boolean(),
  })
  .refine((values) => values.blockerCount === 0 || values.acknowledgeBlockers, {
    message: "Acknowledge the open blockers to approve anyway",
    path: ["acknowledgeBlockers"],
  });

export type TApproveFormValues = z.infer<typeof approveSchema>;

export function toApprovalPayload(contentHash: string, values: TApproveFormValues): TApprovalPayload {
  return {
    destinations: values.destinations,
    content_hash: contentHash,
    options: { devto_mode: values.devtoMode },
    acknowledge_blockers: values.acknowledgeBlockers,
  };
}
