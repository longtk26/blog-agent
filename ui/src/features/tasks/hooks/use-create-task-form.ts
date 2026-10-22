import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";

import { createTaskDefaults, createTaskSchema, toCreateTaskPayload } from "../schemas/create-task-schema";
import type { TCreateTaskFormValues } from "../schemas/create-task-schema";
import { useCreateTask } from "./use-task-actions";

export type TTopicExample = { label: string; values: Partial<TCreateTaskFormValues> };

export const TOPIC_EXAMPLES: TTopicExample[] = [
  {
    label: "LoRA fine-tuning explained",
    values: {
      topic: "How LoRA fine-tuning works, including the mathematics and an implementation example",
      audience: "software engineers who are new to LLM fine-tuning",
      depth: "deep_dive",
      format: "concept",
      requirements: "Include an editable draw.io diagram and credible references; distinguish verified facts from uncertain claims.",
    },
  },
  {
    label: "Research: vector databases",
    values: {
      topic: "Vector databases compared: pgvector vs dedicated engines for RAG workloads",
      mode: "research_only",
      format: "comparison",
    },
  },
  {
    label: "Tutorial: LangGraph human-in-the-loop",
    values: {
      topic: "Building a human-in-the-loop approval step with LangGraph interrupts and a Postgres checkpointer",
      format: "tutorial",
      depth: "intermediate",
    },
  },
];

export function useCreateTaskForm() {
  const router = useRouter();
  const createTask = useCreateTask();
  const form = useForm<TCreateTaskFormValues>({
    resolver: zodResolver(createTaskSchema),
    defaultValues: createTaskDefaults,
  });

  const applyExample = (example: TTopicExample) => {
    form.reset({ ...createTaskDefaults, ...example.values });
  };

  const onSubmit = form.handleSubmit(async (values) => {
    const task = await createTask.mutateAsync(toCreateTaskPayload(values));
    router.push(`/tasks/${task.id}`);
  });

  return { form, onSubmit, applyExample, isSubmitting: createTask.isPending };
}
