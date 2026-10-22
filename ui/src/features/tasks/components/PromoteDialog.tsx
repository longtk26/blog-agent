"use client";

import { useState } from "react";
import { Controller } from "react-hook-form";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useResearchBrief } from "../hooks/use-task";
import { usePromoteForm } from "../hooks/use-promote-form";
import type { TTask } from "../types";

type PromoteDialogProps = {
  task: TTask;
};

export function PromoteDialog({ task }: PromoteDialogProps) {
  const [open, setOpen] = useState(false);
  const { form, onSubmit, isSubmitting } = usePromoteForm(task, () => setOpen(false));
  const { data: brief } = useResearchBrief(task.id, open);
  const angles = brief?.data.angles ?? [];

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Promote to article</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={onSubmit}>
          <DialogHeader>
            <DialogTitle>Write an article from this research</DialogTitle>
            <DialogDescription>The agent reuses the sources it already found. Nothing is searched again.</DialogDescription>
          </DialogHeader>
          <FieldGroup className="py-4">
            <Controller
              name="angle"
              control={form.control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="promote-angle">Angle</FieldLabel>
                  <Input id="promote-angle" placeholder="e.g. LoRA from first principles" aria-invalid={fieldState.invalid} {...field} />
                  {angles.length ? (
                    <div className="flex flex-wrap gap-1.5">
                      {angles.map((angle) => (
                        <Button key={angle.title} type="button" variant="outline" size="xs" onClick={() => field.onChange(angle.title)}>
                          {angle.title}
                        </Button>
                      ))}
                    </div>
                  ) : null}
                  <FieldError errors={[fieldState.error]} />
                </Field>
              )}
            />
            <Controller
              name="audience"
              control={form.control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="promote-audience">Audience</FieldLabel>
                  <Input id="promote-audience" aria-invalid={fieldState.invalid} {...field} />
                  <FieldError errors={[fieldState.error]} />
                </Field>
              )}
            />
            <Controller
              name="requirements"
              control={form.control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="promote-requirements">Requirements</FieldLabel>
                  <Textarea id="promote-requirements" rows={3} aria-invalid={fieldState.invalid} {...field} />
                  <FieldDescription>Optional. These replace the original requirements.</FieldDescription>
                  <FieldError errors={[fieldState.error]} />
                </Field>
              )}
            />
          </FieldGroup>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Starting…" : "Continue to outline"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
