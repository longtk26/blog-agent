import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { promoteTaskSchema, toPromotePayload } from "../schemas/promote-task-schema";
import type { TPromoteTaskFormValues } from "../schemas/promote-task-schema";
import type { TTask } from "../types";
import { usePromoteTask } from "./use-task-actions";

export function usePromoteForm(task: TTask, onDone: () => void) {
  const promote = usePromoteTask(task.id);
  const form = useForm<TPromoteTaskFormValues>({
    resolver: zodResolver(promoteTaskSchema),
    defaultValues: { angle: "", audience: task.audience ?? "", requirements: task.requirements ?? "" },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    await promote.mutateAsync(toPromotePayload(values));
    onDone();
  });

  return { form, onSubmit, isSubmitting: promote.isPending };
}
