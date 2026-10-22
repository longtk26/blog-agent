import { useTaskFiltersStore } from "@/store/task-filters-store";
import { useTasks } from "./use-tasks";

export function useTaskList() {
  const status = useTaskFiltersStore((state) => state.status);
  const mode = useTaskFiltersStore((state) => state.mode);
  const archived = useTaskFiltersStore((state) => state.archived);
  const query = useTasks({
    status: status === "all" ? undefined : [status],
    mode: mode === "all" ? undefined : mode,
    archived,
  });
  return { ...query, filtersActive: status !== "all" || mode !== "all" || archived };
}
