"use client";

import { ChevronDownIcon } from "lucide-react";
import { Controller } from "react-hook-form";
import type { Control } from "react-hook-form";

import { CopyIcon } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel, FieldSet, FieldLegend } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { TOPIC_EXAMPLES, useCreateTaskForm } from "../hooks/use-create-task-form";
import type { TCreateTaskFormValues } from "../schemas/create-task-schema";

type TextFieldName = "audience" | "language" | "seriesName" | "seriesPart" | "maxQueries" | "maxSources" | "maxRounds";

type TextFieldProps = {
  control: Control<TCreateTaskFormValues>;
  name: TextFieldName;
  label: string;
  placeholder?: string;
  description?: string;
};

function TextField({ control, name, label, placeholder, description }: TextFieldProps) {
  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => (
        <Field data-invalid={fieldState.invalid}>
          <FieldLabel htmlFor={`task-${name}`}>{label}</FieldLabel>
          <Input id={`task-${name}`} placeholder={placeholder} aria-invalid={fieldState.invalid} {...field} />
          {description ? <FieldDescription>{description}</FieldDescription> : null}
          <FieldError errors={[fieldState.error]} />
        </Field>
      )}
    />
  );
}

type SelectFieldProps = {
  control: Control<TCreateTaskFormValues>;
  name: "depth" | "format" | "includeDiagram";
  label: string;
  options: { value: string; label: string }[];
};

function SelectField({ control, name, label, options }: SelectFieldProps) {
  return (
    <Controller
      name={name}
      control={control}
      render={({ field }) => (
        <Field>
          <FieldLabel htmlFor={`task-${name}`}>{label}</FieldLabel>
          <Select value={field.value} onValueChange={field.onChange}>
            <SelectTrigger id={`task-${name}`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      )}
    />
  );
}

export function TaskForm() {
  const { form, onSubmit, applyExample, cloneSource, isSubmitting } = useCreateTaskForm();
  const { control } = form;

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      {cloneSource ? (
        <Alert>
          <CopyIcon />
          <AlertTitle>Cloning “{cloneSource.topic}”</AlertTitle>
          <AlertDescription>
            The form is prefilled from that task. Change what you need; the original stays archived.
            <Controller
              name="reuseSources"
              control={control}
              render={({ field }) => (
                <Field orientation="horizontal" className="mt-2">
                  <Checkbox id="task-reuseSources" checked={field.value} onCheckedChange={(value) => field.onChange(value === true)} />
                  <FieldLabel htmlFor="task-reuseSources" className="font-normal">
                    Reuse its {cloneSource.progress.sources_assessed} assessed sources (they count towards the source budget)
                  </FieldLabel>
                </Field>
              )}
            />
          </AlertDescription>
        </Alert>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {TOPIC_EXAMPLES.map((example) => (
          <Button key={example.label} type="button" variant="outline" size="sm" onClick={() => applyExample(example)}>
            {example.label}
          </Button>
        ))}
      </div>

      <Card>
        <CardContent>
          <FieldGroup>
            <Controller
              name="mode"
              control={control}
              render={({ field }) => (
                <Field>
                  <FieldLabel>What should the agent do?</FieldLabel>
                  <ToggleGroup
                    type="single"
                    variant="outline"
                    value={field.value}
                    onValueChange={(value) => value && field.onChange(value)}
                  >
                    <ToggleGroupItem value="article">Research + write</ToggleGroupItem>
                    <ToggleGroupItem value="research_only">Research only</ToggleGroupItem>
                  </ToggleGroup>
                  <FieldDescription>
                    {field.value === "research_only"
                      ? "Get a research brief first; you can promote it to an article later."
                      : "Research, outline and draft an article for your review."}
                  </FieldDescription>
                </Field>
              )}
            />

            <Controller
              name="topic"
              control={control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="task-topic">Topic</FieldLabel>
                  <Textarea
                    id="task-topic"
                    rows={3}
                    placeholder="e.g. How LoRA fine-tuning works, with the maths and an implementation example"
                    aria-invalid={fieldState.invalid}
                    {...field}
                  />
                  <FieldError errors={[fieldState.error]} />
                </Field>
              )}
            />

            <TextField control={control} name="audience" label="Audience" placeholder="software engineers new to LLM fine-tuning" />

            <div className="grid gap-4 sm:grid-cols-3">
              <SelectField
                control={control}
                name="depth"
                label="Depth"
                options={[
                  { value: "intro", label: "Intro" },
                  { value: "intermediate", label: "Intermediate" },
                  { value: "deep_dive", label: "Deep dive" },
                ]}
              />
              <SelectField
                control={control}
                name="format"
                label="Format"
                options={[
                  { value: "concept", label: "Concept explainer" },
                  { value: "tutorial", label: "Tutorial" },
                  { value: "comparison", label: "Comparison" },
                  { value: "series_part", label: "Series part" },
                ]}
              />
              <SelectField
                control={control}
                name="includeDiagram"
                label="Diagram"
                options={[
                  { value: "auto", label: "When useful" },
                  { value: "yes", label: "Always" },
                  { value: "no", label: "Never" },
                ]}
              />
            </div>

            <Controller
              name="requirements"
              control={control}
              render={({ field, fieldState }) => (
                <Field data-invalid={fieldState.invalid}>
                  <FieldLabel htmlFor="task-requirements">Requirements</FieldLabel>
                  <Textarea
                    id="task-requirements"
                    rows={3}
                    placeholder="Must cover…, include a code example in Python, cite primary sources…"
                    aria-invalid={fieldState.invalid}
                    {...field}
                  />
                  <FieldError errors={[fieldState.error]} />
                </Field>
              )}
            />

            <Controller
              name="reviewOutline"
              control={control}
              render={({ field }) => (
                <Field orientation="horizontal">
                  <Checkbox id="task-reviewOutline" checked={field.value} onCheckedChange={(value) => field.onChange(value === true)} />
                  <FieldLabel htmlFor="task-reviewOutline" className="font-normal">
                    Let me review the outline before drafting
                  </FieldLabel>
                </Field>
              )}
            />

            <Controller
              name="useStyleExamples"
              control={control}
              render={({ field }) => (
                <Field orientation="horizontal">
                  <Checkbox id="task-useStyleExamples" checked={field.value} onCheckedChange={(value) => field.onChange(value === true)} />
                  <FieldLabel htmlFor="task-useStyleExamples" className="font-normal">
                    Use approved writing samples as style references
                  </FieldLabel>
                </Field>
              )}
            />

            <FieldSet>
              <FieldLegend variant="label">Publish to (after your approval)</FieldLegend>
              <div className="flex gap-6">
                {(["publishToSanity", "publishToDevto"] as const).map((name) => (
                  <Controller
                    key={name}
                    name={name}
                    control={control}
                    render={({ field }) => (
                      <Field orientation="horizontal" className="w-auto">
                        <Checkbox id={`task-${name}`} checked={field.value} onCheckedChange={(value) => field.onChange(value === true)} />
                        <FieldLabel htmlFor={`task-${name}`} className="font-normal">
                          {name === "publishToSanity" ? "Website (Sanity)" : "DEV Community"}
                        </FieldLabel>
                      </Field>
                    )}
                  />
                ))}
              </div>
            </FieldSet>
          </FieldGroup>
        </CardContent>
      </Card>

      <Collapsible>
        <CollapsibleTrigger asChild>
          <Button type="button" variant="ghost" size="sm" className="group">
            Advanced options <ChevronDownIcon className="transition-transform group-data-[state=open]:rotate-180" />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <Card className="mt-2">
            <CardContent>
              <FieldGroup>
                <div className="grid gap-4 sm:grid-cols-3">
                  <TextField control={control} name="maxQueries" label="Max searches" placeholder="8" />
                  <TextField control={control} name="maxSources" label="Max sources" placeholder="15" />
                  <TextField control={control} name="maxRounds" label="Max research rounds" placeholder="2" />
                </div>
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="sm:col-span-2">
                    <TextField control={control} name="seriesName" label="Series name" placeholder="Fine-tuning LLMs" />
                  </div>
                  <TextField control={control} name="seriesPart" label="Part" placeholder="3" />
                </div>
                <TextField control={control} name="language" label="Language" description="Language code, e.g. en or vi." />
              </FieldGroup>
            </CardContent>
          </Card>
        </CollapsibleContent>
      </Collapsible>

      <div className="flex justify-end">
        <Button type="submit" size="lg" disabled={isSubmitting}>
          {isSubmitting ? "Starting…" : "Start task"}
        </Button>
      </div>
    </form>
  );
}
