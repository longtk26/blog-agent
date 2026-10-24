"use client";

import { WandSparklesIcon } from "lucide-react";
import { useState } from "react";
import { Controller, useWatch } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { TRevision } from "@/features/tasks/types";
import { useRequestRevisionForm } from "../hooks/use-review-forms";
import { splitSections } from "../markdown-sections";
import { REVIEW_TARGETS } from "../schemas/request-revision-schema";

type RequestRevisionDialogProps = {
  taskId: string;
  revision: TRevision;
  disabled: boolean;
};

export function RequestRevisionDialog({ taskId, revision, disabled }: RequestRevisionDialogProps) {
  const [open, setOpen] = useState(false);
  const { form, onSubmit, isSubmitting } = useRequestRevisionForm(taskId, revision.id, () => setOpen(false));
  const target = useWatch({ control: form.control, name: "target" });
  const sections = splitSections(revision.markdown);
  const scoped = target !== "metadata" && target !== "outline";

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" disabled={disabled}>
          <WandSparklesIcon /> Request revision
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl">
        <form onSubmit={onSubmit}>
          <DialogHeader>
            <DialogTitle>Ask the agent to revise r{revision.revision_number}</DialogTitle>
            <DialogDescription>
              Only the part you point at is redone; other sections stay byte-identical. The result is a new revision for you to review.
            </DialogDescription>
          </DialogHeader>
          <FieldGroup className="py-4">
            <Controller
              name="feedback"
              control={form.control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="revise-feedback">Feedback</FieldLabel>
                  <Textarea
                    id="revise-feedback"
                    rows={5}
                    placeholder="e.g. Section 2 needs a concrete memory calculation for a 7B model."
                    aria-invalid={fieldState.invalid}
                    {...field}
                  />
                  <FieldError errors={[fieldState.error]} />
                </Field>
              )}
            />
            <Controller
              name="target"
              control={form.control}
              render={({ field }) => (
                <Field>
                  <FieldLabel htmlFor="revise-target">What should change?</FieldLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="revise-target">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {REVIEW_TARGETS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FieldDescription>{REVIEW_TARGETS.find((option) => option.value === field.value)?.hint}</FieldDescription>
                </Field>
              )}
            />
            {scoped ? (
              <Controller
                name="sections"
                control={form.control}
                render={({ field }) => (
                  <FieldSet>
                    <FieldLegend variant="label">Sections (optional)</FieldLegend>
                    <FieldDescription>Leave empty to let the agent pick the sections from your feedback.</FieldDescription>
                    <div className="grid max-h-48 gap-2 overflow-y-auto sm:grid-cols-2">
                      {sections.map((section) => {
                        const checked = field.value.includes(section.heading);
                        return (
                          <Field key={section.heading} orientation="horizontal" className="w-auto">
                            <Checkbox
                              id={`revise-section-${section.line}`}
                              checked={checked}
                              onCheckedChange={(value) =>
                                field.onChange(value === true ? [...field.value, section.heading] : field.value.filter((s) => s !== section.heading))
                              }
                            />
                            <FieldLabel htmlFor={`revise-section-${section.line}`} className="font-normal">
                              {section.heading}
                            </FieldLabel>
                          </Field>
                        );
                      })}
                    </div>
                  </FieldSet>
                )}
              />
            ) : null}
          </FieldGroup>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Sending…" : "Request revision"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
