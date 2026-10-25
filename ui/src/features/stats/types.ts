export type TStageDuration = {
  stage: string;
  avg_duration_s: number;
  p90_duration_s: number;
  samples: number;
};

export type TToolErrorRate = {
  tool: string;
  calls: number;
  errors: number;
  error_rate: number;
};

export type TRecentFailure = {
  task_id: string;
  topic: string;
  failed_stage: string | null;
  error: string | null;
  created_at: string;
  trace_url: string | null;
};

export type TOpsStats = {
  period_days: number;
  tasks_by_status: Record<string, number>;
  stage_durations: TStageDuration[];
  avg_cost_per_task: number;
  total_cost_period: number;
  tool_error_rates: TToolErrorRate[];
  recent_failures: TRecentFailure[];
};
