"use client";

import { CheckCircle2Icon } from "lucide-react";
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
                <FieldDescription>Used by the Dev.to publisher (Epic 8).</FieldDescription>
              </Field>
            )}
          />
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
