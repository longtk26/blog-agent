"use client";

import { Controller } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldError } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useStyleGuideForm } from "../hooks/use-style-guide-form";

export function StyleGuideEditor() {
  const { form, guide, isPending, isSaving, onSubmit } = useStyleGuideForm();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Writing style guide
          {guide ? <Badge variant="outline">{guide.version}</Badge> : null}
        </CardTitle>
        <CardDescription>
          The writer and the editor-judge follow this guide. Every save creates a new version, and each draft records the version it used.
          {guide?.source === "seed" ? " You are seeing the default guide curated from your fine-tuning posts." : null}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <Skeleton className="h-80" />
        ) : (
          <form onSubmit={onSubmit} className="space-y-3">
            <Controller
              name="content"
              control={form.control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <Textarea rows={22} className="font-mono text-xs" aria-invalid={fieldState.invalid} aria-label="Style guide Markdown" {...field} />
                  <FieldError errors={[fieldState.error]} />
                </Field>
              )}
            />
            <div className="flex justify-end">
              <Button type="submit" disabled={isSaving || !form.formState.isDirty}>
                {isSaving ? "Saving…" : "Save new version"}
              </Button>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
