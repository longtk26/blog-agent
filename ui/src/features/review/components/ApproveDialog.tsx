"use client";

import { AlertCircleIcon, CheckCircle2Icon } from "lucide-react";
import { useState } from "react";
import { Controller, useWatch } from "react-hook-form";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { TPublicationTarget, TRevision, TTask } from "@/features/tasks/types";
import { useApproveForm } from "../hooks/use-review-forms";

const DESTINATIONS: { value: TPublicationTarget; label: string }[] = [
  { value: "sanity", label: "Website (Sanity)" },
  { value: "devto", label: "DEV Community" },
];

type ApproveDialogProps = {
  task: TTask;
  revision: TRevision;
  disabled: boolean;
};

function ApproveForm({ task, revision, onDone }: { task: TTask; revision: TRevision; onDone: () => void }) {
  const blockers = revision.evaluations.flatMap((e) => e.issues).filter((issue) => issue.severity === "blocker");
  const { form, onSubmit, isSubmitting } = useApproveForm(
    task.id,
    revision,
    { destinations: task.publication_targets.length ? task.publication_targets : ["sanity"], blockerCount: blockers.length },
    onDone,
  );
  const destinations = useWatch({ control: form.control, name: "destinations" });
  const devtoMode = useWatch({ control: form.control, name: "devtoMode" });

  return (
    <form onSubmit={onSubmit}>
      <DialogHeader>
        <DialogTitle>Approve r{revision.revision_number} for publishing</DialogTitle>
        <DialogDescription>
          The approval covers exactly this content. Any later edit — yours or the agent&apos;s — voids it.
        </DialogDescription>
      </DialogHeader>
      <dl className="my-4 grid gap-x-3 gap-y-1.5 rounded-lg border p-3 text-sm sm:grid-cols-[90px_1fr]">
        <dt className="text-muted-foreground">Revision</dt>
        <dd>
          r{revision.revision_number} · <span className="font-mono">{revision.content_hash.slice(0, 12)}</span>
        </dd>
        <dt className="text-muted-foreground">Title</dt>
        <dd>{revision.title}</dd>
        <dt className="text-muted-foreground">Slug</dt>
        <dd className="font-mono">{revision.slug}</dd>
      </dl>
      <FieldGroup>
        <Controller
          name="destinations"
          control={form.control}
          render={({ field, fieldState }) => (
            <FieldSet data-invalid={fieldState.invalid}>
              <FieldLegend variant="label">Destinations</FieldLegend>
              <div className="flex gap-6">
                {DESTINATIONS.map((destination) => (
                  <Field key={destination.value} orientation="horizontal" className="w-auto">
                    <Checkbox
                      id={`approve-${destination.value}`}
                      checked={field.value.includes(destination.value)}
                      onCheckedChange={(value) =>
                        field.onChange(value === true ? [...field.value, destination.value] : field.value.filter((d) => d !== destination.value))
                      }
                    />
                    <FieldLabel htmlFor={`approve-${destination.value}`} className="font-normal">
                      {destination.label}
                    </FieldLabel>
                  </Field>
                ))}
              </div>
              <FieldError errors={[fieldState.error]} />
            </FieldSet>
          )}
        />
        {destinations.includes("devto") ? (
          <div className="space-y-2">
            <Controller
              name="devtoMode"
              control={form.control}
              render={({ field }) => (
                <Field>
                  <FieldLabel>DEV Community mode</FieldLabel>
                  <ToggleGroup type="single" variant="outline" value={field.value} onValueChange={(value) => value && field.onChange(value)}>
                    <ToggleGroupItem value="draft">Draft on Dev.to</ToggleGroupItem>
                    <ToggleGroupItem value="published">Publish on Dev.to</ToggleGroupItem>
                  </ToggleGroup>
                  <FieldDescription>Choose whether to push as an unlisted draft or go public immediately.</FieldDescription>
                </Field>
              )}
            />
            {devtoMode === "published" ? (
              <Alert variant="destructive" className="border-amber-500/50 bg-amber-500/10 text-amber-500 dark:border-amber-500/30 dark:bg-amber-500/10">
                <AlertCircleIcon className="size-4 text-amber-500" />
                <AlertTitle className="text-amber-500 font-medium">Warning: Going Public on DEV Community</AlertTitle>
                <AlertDescription className="text-xs text-amber-600 dark:text-amber-400">
                  This will publish live immediately to DEV.to feeds and followers once published. If you prefer to review on DEV before releasing, keep &quot;Draft on Dev.to&quot; selected.
                </AlertDescription>
              </Alert>
            ) : null}
          </div>
        ) : null}
        {blockers.length ? (
          <Controller
            name="acknowledgeBlockers"
            control={form.control}
            render={({ field, fieldState }) => (
              <Alert variant="destructive">
                <AlertTitle>{blockers.length} open blocker issue(s)</AlertTitle>
                <AlertDescription className="space-y-2">
                  <ul className="ml-4 list-disc">
                    {blockers.slice(0, 5).map((issue, index) => (
                      <li key={`${issue.rule}-${index}`}>{issue.message}</li>
                    ))}
                  </ul>
                  <Field orientation="horizontal" data-invalid={fieldState.invalid}>
                    <Checkbox id="approve-ack" checked={field.value} onCheckedChange={(value) => field.onChange(value === true)} />
                    <FieldLabel htmlFor="approve-ack" className="font-normal">
                      I have read these and approve anyway
                    </FieldLabel>
                  </Field>
                  <FieldError errors={[fieldState.error]} />
                </AlertDescription>
              </Alert>
            )}
          />
        ) : null}
      </FieldGroup>
      <DialogFooter className="mt-4">
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Approving…" : `Yes, approve r${revision.revision_number}`}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** E4-S6: opening the dialog is the first click; "Yes, approve rN" is the second. */
export function ApproveDialog({ task, revision, disabled }: ApproveDialogProps) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button disabled={disabled}>
          <CheckCircle2Icon /> Approve
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        {/* Remounted per open so the form starts from the current revision. */}
        {open ? <ApproveForm task={task} revision={revision} onDone={() => setOpen(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}
