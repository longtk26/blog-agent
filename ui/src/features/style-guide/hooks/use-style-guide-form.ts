import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { styleGuideApi } from "../api/style-guide-api";
import { styleGuideKeys } from "../query-keys";

const styleGuideSchema = z.object({
  content: z.string().trim().min(50, "The style guide needs at least 50 characters").max(20000),
});

type TStyleGuideFormValues = z.infer<typeof styleGuideSchema>;

export function useStyleGuideForm() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: styleGuideKeys.active(), queryFn: styleGuideApi.get });
  const form = useForm<TStyleGuideFormValues>({ resolver: zodResolver(styleGuideSchema), defaultValues: { content: "" } });
  const { reset } = form;

  useEffect(() => {
    if (query.data) reset({ content: query.data.content });
  }, [query.data, reset]);

  const save = useMutation({
    mutationFn: (values: TStyleGuideFormValues) => styleGuideApi.update(values.content),
    onSuccess: (guide) => {
      queryClient.setQueryData(styleGuideKeys.active(), guide);
      toast.success(`Saved style guide ${guide.version}`);
    },
    onError: (error) => toast.error(error.message),
  });

  return {
    form,
    guide: query.data,
    isPending: query.isPending,
    isSaving: save.isPending,
    onSubmit: form.handleSubmit((values) => save.mutate(values)),
  };
}
