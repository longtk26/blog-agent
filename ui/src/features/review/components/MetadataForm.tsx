"use client";

import { Controller } from "react-hook-form";

import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useMetadataForm } from "../hooks/use-review-forms";
import type { TArticleMetadata } from "../types";

type MetadataFormProps = {
  metadata: TArticleMetadata;
};

export function MetadataForm({ metadata }: MetadataFormProps) {
  const { form } = useMetadataForm(metadata);

  return (
    <FieldGroup>
      <Controller
        name="title"
        control={form.control}
        render={({ field, fieldState }) => (
          <Field data-invalid={fieldState.invalid}>
            <FieldLabel htmlFor="meta-title">Title</FieldLabel>
            <Input id="meta-title" aria-invalid={fieldState.invalid} {...field} />
            <FieldDescription>Also updates the article&apos;s H1.</FieldDescription>
            <FieldError errors={[fieldState.error]} />
          </Field>
        )}
      />
      <Controller
        name="slug"
        control={form.control}
        render={({ field, fieldState }) => (
          <Field data-invalid={fieldState.invalid}>
            <FieldLabel htmlFor="meta-slug">Slug</FieldLabel>
            <Input id="meta-slug" className="font-mono" aria-invalid={fieldState.invalid} {...field} />
            <FieldError errors={[fieldState.error]} />
          </Field>
        )}
      />
      <Controller
        name="description"
        control={form.control}
        render={({ field, fieldState }) => (
          <Field data-invalid={fieldState.invalid}>
            <FieldLabel htmlFor="meta-description">Description</FieldLabel>
            <Textarea id="meta-description" rows={3} aria-invalid={fieldState.invalid} {...field} />
            <FieldDescription>{field.value.length}/160 characters on the site and Dev.to.</FieldDescription>
            <FieldError errors={[fieldState.error]} />
          </Field>
        )}
      />
      <Controller
        name="tags"
        control={form.control}
        render={({ field, fieldState }) => (
          <Field data-invalid={fieldState.invalid}>
            <FieldLabel htmlFor="meta-tags">Tags</FieldLabel>
            <Input id="meta-tags" placeholder="llm, lora, finetuning" aria-invalid={fieldState.invalid} {...field} />
            <FieldDescription>1–4 lowercase words, comma-separated (Dev.to rules).</FieldDescription>
            <FieldError errors={[fieldState.error]} />
          </Field>
        )}
      />
    </FieldGroup>
  );
}
