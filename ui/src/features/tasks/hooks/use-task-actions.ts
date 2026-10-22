import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { tasksApi } from "../api/tasks-api";
import { taskKeys } from "../query-keys";
import type { TCreateTaskPayload, TPromotePayload, TTask } from "../types";

function useTaskMutation<TVariables>(
  mutationFn: (variables: TVariables) => Promise<TTask>,
  successMessage: string,
) {
  const queryClient = useQueryClient();
  return useMutation<TTask, Error, TVariables>({
    mutationFn,
    onSuccess: (task) => {
      queryClient.setQueryData(taskKeys.detail(task.id), task);
      queryClient.invalidateQueries({ queryKey: taskKeys.lists() });
      toast.success(successMessage);
    },
    onError: (error) => toast.error(error.message),
  });
}

export function useCreateTask() {
  return useTaskMutation((payload: TCreateTaskPayload) => tasksApi.create(payload), "Task started");
}

export function useCancelTask() {
  return useTaskMutation((id: string) => tasksApi.cancel(id), "Task cancelled");
}

export function useRetryTask() {
  return useTaskMutation((id: string) => tasksApi.retry(id), "Retrying from the last checkpoint");
}

export function usePromoteTask(id: string) {
  return useTaskMutation((payload: TPromotePayload) => tasksApi.promote(id, payload), "Promoted to an article");
}
