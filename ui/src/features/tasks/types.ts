// Mirrors api/src/modules/tasks/presenter/dtos and api/src/modules/research/presenter/dtos.
export const TASK_STATUSES = [
  "queued",
  "researching",
  "outlining",
  "drafting",
  "generating_diagram",
  "validating",
  "awaiting_review",
  "revision_requested",
  "approved",
  "publishing",
  "published",
  "partially_published",
  "completed",
  "failed",
  "rejected",
] as const;

export type TTaskStatus = (typeof TASK_STATUSES)[number];
export type TTaskMode = "research_only" | "article";
export type TTaskDepth = "intro" | "intermediate" | "deep_dive";
export type TTaskFormat = "concept" | "tutorial" | "comparison" | "series_part";
export type TIncludeDiagram = "auto" | "yes" | "no";
export type TPublicationTarget = "sanity" | "devto";

export type TTaskBudgets = {
  max_queries: number;
  max_sources: number;
  max_research_rounds: number;
  results_per_query: number;
};

export type TTaskProgress = {
  round: number;
  queries_used: number;
  sources_found: number;
  sources_extracted: number;
  sources_assessed: number;
  claims: number;
};

export type TPlannedQuestion = { id: string; question: string; must_cover: boolean };
export type TPlannedQuery = { query: string; intent: string; question_ids: string[]; preferred_source_types: string[] };
export type TResearchPlan = {
  questions: TPlannedQuestion[];
  queries: TPlannedQuery[];
  must_cover: string[];
  out_of_scope: string[];
};

export type TOutlineSection = {
  key: string;
  heading: string;
  heading_style: "numbered" | "step" | "plain";
  goal: string;
  key_points: string[];
  claim_ids: string[];
  needs: string[];
  est_words: number;
};

export type TOutline = {
  title: string;
  title_options: string[];
  angle: string;
  intro_goal: string;
  next_steps: string;
  must_cover: string[];
  covered_requirements: string[];
  sections: TOutlineSection[];
};

export type TSeries = { name: string; part: number | null; previous_post_id: string | null };

export type TTask = {
  id: string;
  topic: string;
  mode: TTaskMode;
  audience: string | null;
  depth: TTaskDepth;
  language: string;
  format: TTaskFormat;
  series: TSeries | null;
  requirements: string | null;
  angle: string | null;
  include_diagram: TIncludeDiagram;
  review_outline: boolean;
  use_style_examples?: boolean;
  publication_targets: TPublicationTarget[];
  budgets: TTaskBudgets;
  status: TTaskStatus;
  failed_stage: TTaskStatus | null;
  last_error: string | null;
  resumable: boolean;
  research_plan: TResearchPlan | null;
  outline: TOutline | null;
  open_questions: string[];
  progress: TTaskProgress;
  is_running: boolean;
  pending_interrupt: { type: string; [key: string]: unknown } | null;
  trace_url: string | null;
  created_at: string;
  updated_at: string;
};

export type TTaskSummary = Pick<
  TTask,
  "id" | "topic" | "mode" | "format" | "status" | "progress" | "last_error" | "is_running" | "created_at" | "updated_at"
>;

export type TTaskList = { items: TTaskSummary[]; total: number; limit: number; offset: number };

export type TTaskListFilters = {
  status?: TTaskStatus[];
  mode?: TTaskMode;
  archived?: boolean;
  limit?: number;
  offset?: number;
};

export type TCreateTaskPayload = {
  topic: string;
  mode: TTaskMode;
  audience?: string;
  depth: TTaskDepth;
  language: string;
  format: TTaskFormat;
  requirements?: string;
  include_diagram: TIncludeDiagram;
  review_outline: boolean;
  use_style_examples?: boolean;
  publication_targets: TPublicationTarget[];
  series?: { name: string; part?: number };
  budgets?: Partial<TTaskBudgets>;
  clone_from_task_id?: string;
  reuse_sources?: boolean;
};

export type TPromotePayload = {
  angle?: string;
  audience?: string;
  depth?: TTaskDepth;
  format?: TTaskFormat;
  requirements?: string;
};

export type TTaskEvent = {
  id: number;
  type: string;
  from_status: string | null;
  to_status: string | null;
  actor: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type TSourceStatus = "pending" | "extracted" | "assessed" | "low_quality" | "failed";

export type TClaim = {
  id: string;
  question_id: string | null;
  text: string;
  supporting_quote: string;
  quote_verified: boolean;
};

export type TSource = {
  id: string;
  url: string;
  canonical_url: string;
  title: string | null;
  publisher: string | null;
  published_at: string | null;
  retrieved_at: string | null;
  snippet: string | null;
  query: string | null;
  round: number;
  status: TSourceStatus;
  source_type: string | null;
  quality_score: number | null;
  quality_rationale: string | null;
  relevance: number | null;
  notes: string[];
  error: string | null;
  claims: TClaim[];
};

export type TSourceList = { items: TSource[]; total: number };

export type TResearchBrief = {
  id: string;
  task_id: string;
  markdown: string;
  data: {
    summary?: string;
    angles?: { title: string; audience: string; rationale: string }[];
    open_questions?: string[];
  };
  created_at: string;
};

export type TIssueSeverity = "blocker" | "warning" | "info";

export type TValidationIssue = {
  rule: string;
  severity: TIssueSeverity;
  message: string;
  line: number | null;
  section: string | null;
  source: "validator" | "judge";
};

export type TEvaluation = {
  kind: "deterministic" | "judge";
  passed: boolean;
  scores: Record<string, number>;
  issues: TValidationIssue[];
  model: string | null;
  prompt_version: string | null;
  created_at: string;
};

export type TRevisionSummary = {
  id: string;
  revision_number: number;
  parent_revision_id: string | null;
  created_by: "ai" | "owner";
  title: string;
  slug: string;
  content_hash: string;
  word_count: number | null;
  checks_passed: Record<string, boolean>;
  feedback: string | null;
  review_target: string | null;
  sections_changed: string[];
  out_of_scope: string[];
  approved_for: TPublicationTarget[];
  created_at: string;
};

export type TClaimMapEntry = { sentence: string; claim_ids: string[]; support: "supported" | "partial" | "unsupported" };

export type TRevisionReview = {
  round: number | null;
  feedback: string;
  requested_target: string;
  target: string;
  scope_sections: string[];
  reviewed_revision_id: string | null;
  out_of_scope: string[];
};

export type TRevision = {
  id: string;
  task_id: string;
  revision_number: number;
  parent_revision_id: string | null;
  created_by: "ai" | "owner";
  title: string;
  slug: string;
  description: string;
  tags: string[];
  markdown: string;
  content_hash: string;
  metadata: {
    outline?: TOutline;
    claim_map?: Record<string, TClaimMapEntry[]>;
    sections_changed?: string[];
    review?: TRevisionReview;
    self_revisions?: number;
    unsupported_statements?: string[];
    word_count?: number;
    style_guide_version?: string;
    models?: Record<string, string | null>;
  };
  evaluations: TEvaluation[];
  created_at: string;
};
