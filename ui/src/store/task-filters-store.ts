import { create } from "zustand";
import { devtools } from "zustand/middleware";

import type { TTaskMode, TTaskStatus } from "@/features/tasks/types";

type TTaskFiltersState = {
  status: TTaskStatus | "all";
  mode: TTaskMode | "all";
  archived: boolean;
  setStatus: (status: TTaskStatus | "all") => void;
  setMode: (mode: TTaskMode | "all") => void;
  setArchived: (archived: boolean) => void;
};

export const useTaskFiltersStore = create<TTaskFiltersState>()(
  devtools(
    (set) => ({
      status: "all",
      mode: "all",
      archived: false,
      setStatus: (status) => set({ status }, false, "taskFilters/setStatus"),
      setMode: (mode) => set({ mode }, false, "taskFilters/setMode"),
      setArchived: (archived) => set({ archived }, false, "taskFilters/setArchived"),
    }),
    { name: "task-filters-store" },
  ),
);
