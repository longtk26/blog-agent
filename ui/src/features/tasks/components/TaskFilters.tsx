"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { humanize } from "@/lib/format";
import { useTaskFiltersStore } from "@/store/task-filters-store";
import { TASK_STATUSES } from "../types";
import type { TTaskMode, TTaskStatus } from "../types";

export function TaskFilters() {
  const status = useTaskFiltersStore((state) => state.status);
  const mode = useTaskFiltersStore((state) => state.mode);
  const archived = useTaskFiltersStore((state) => state.archived);
  const setStatus = useTaskFiltersStore((state) => state.setStatus);
  const setMode = useTaskFiltersStore((state) => state.setMode);
  const setArchived = useTaskFiltersStore((state) => state.setArchived);

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Select value={status} onValueChange={(value) => setStatus(value as TTaskStatus | "all")}>
        <SelectTrigger className="w-44" aria-label="Filter by status">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All statuses</SelectItem>
          {TASK_STATUSES.map((value) => (
            <SelectItem key={value} value={value} className="capitalize">
              {humanize(value)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select value={mode} onValueChange={(value) => setMode(value as TTaskMode | "all")}>
        <SelectTrigger className="w-44" aria-label="Filter by mode">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All modes</SelectItem>
          <SelectItem value="research_only">Research only</SelectItem>
          <SelectItem value="article">Article</SelectItem>
        </SelectContent>
      </Select>
      <div className="flex items-center gap-2">
        <Checkbox id="show-archived" checked={archived} onCheckedChange={(value) => setArchived(value === true)} />
        <Label htmlFor="show-archived" className="text-sm font-normal">
          Show archived
        </Label>
      </div>
    </div>
  );
}
