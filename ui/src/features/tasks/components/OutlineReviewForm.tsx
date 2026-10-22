"use client";

import { Controller } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useOutlineReviewForm } from "../hooks/use-outline-review-form";
import type { TOutline } from "../types";

type OutlineReviewFormProps = {
  taskId: string;
  outline: TOutline;
};

export function OutlineReviewForm({ taskId, outline }: OutlineReviewFormProps) {
  const { form, sections, onSubmit, isSubmitting } = useOutlineReviewForm(taskId, outline);

  return (
    <form onSubmit={onSubmit} className="space-y-4 rounded-lg border border-warning/50 p-4">
      <div>
        <p className="text-sm font-medium">The agent is waiting for you to approve the outline.</p>
        <p className="text-xs text-muted-foreground">Edit the title or headings if you like, then approve to start drafting.</p>
      </div>
      <FieldGroup>
        <Controller
          name="title"
          control={form.control}
          render={({ field, fieldState }) => (
            <Field data-invalid={fieldState.invalid}>
              <FieldLabel htmlFor="outline-title">Title</FieldLabel>
              <Input id="outline-title" aria-invalid={fieldState.invalid} {...field} />
              <FieldError errors={[fieldState.error]} />
            </Field>
          )}
        />
        {sections.fields.map((section, index) => (
          <div key={section.fieldId} className="grid gap-2 sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
            <Controller
              name={`sections.${index}.heading`}
              control={form.control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor={`outline-heading-${index}`}>Section {index + 1}</FieldLabel>
                  <Input id={`outline-heading-${index}`} aria-invalid={fieldState.invalid} {...field} />
                  <FieldError errors={[fieldState.error]} />
                </Field>
              )}
            />
            <Controller
              name={`sections.${index}.goal`}
              control={form.control}
              render={({ field }) => (
                <Field>
                  <FieldLabel htmlFor={`outline-goal-${index}`}>Goal</FieldLabel>
                  <Input id={`outline-goal-${index}`} {...field} />
                </Field>
              )}
            />
          </div>
        ))}
      </FieldGroup>
      <div className="flex justify-end">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Approving…" : "Approve outline & draft"}
        </Button>
      </div>
    </form>
  );
}
