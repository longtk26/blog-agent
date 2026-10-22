import { zodResolver } from "@hookform/resolvers/zod";
import { useFieldArray, useForm } from "react-hook-form";
import { z } from "zod";

import type { TOutline } from "../types";
import { useApproveOutline } from "./use-task-actions";

const outlineReviewSchema = z.object({
  title: z.string().trim().min(3).max(200),
  sections: z.array(
    z.object({
      key: z.string(),
      heading: z.string().trim().min(2, "Heading is required").max(200),
      goal: z.string().trim().max(1000),
    }),
  ),
});

export type TOutlineReviewValues = z.infer<typeof outlineReviewSchema>;

export function useOutlineReviewForm(taskId: string, outline: TOutline) {
  const approve = useApproveOutline(taskId);
  const form = useForm<TOutlineReviewValues>({
    resolver: zodResolver(outlineReviewSchema),
    defaultValues: {
      title: outline.title,
      sections: outline.sections.map(({ key, heading, goal }) => ({ key, heading, goal })),
    },
  });
  const sections = useFieldArray({ control: form.control, name: "sections", keyName: "fieldId" });

  const onSubmit = form.handleSubmit(async (values) => {
    const edited = values.sections.map((section) => ({
      ...outline.sections.find((original) => original.key === section.key)!,
      heading: section.heading,
      goal: section.goal,
    }));
    const changed = values.title !== outline.title || JSON.stringify(edited) !== JSON.stringify(outline.sections);
    await approve.mutateAsync(changed ? { title: values.title, sections: edited } : undefined);
  });

  return { form, sections, onSubmit, isSubmitting: approve.isPending };
}
