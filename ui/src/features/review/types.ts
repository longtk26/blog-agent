import type { TPublicationTarget } from "@/features/tasks/types";

export type TReviewTarget = "auto" | "research" | "outline" | "draft" | "metadata" | "diagram";
export type TDevtoMode = "draft" | "published";

export type TArticleMetadata = { title: string; slug: string; description: string; tags: string[] };

export type TOwnerRevisionPayload = { base_revision_id: string; markdown: string; metadata: TArticleMetadata };

export type TReviewPayload =
  | { action: "revise"; revision_id: string; feedback: string; scope: { sections: string[]; target: TReviewTarget } }
  | { action: "reject"; reason?: string };

export type TApprovalPayload = {
  destinations: TPublicationTarget[];
  content_hash: string;
  options: { devto_mode: TDevtoMode };
  acknowledge_blockers: boolean;
};

export type TApproval = {
  id: string;
  task_id: string;
  article_revision_id: string;
  content_hash: string;
  destination: TPublicationTarget;
  options: { devto_mode?: TDevtoMode; acknowledged_blockers?: string[] };
  decision: "approved" | "superseded";
  reviewer_id: string;
  reviewed_at: string;
  superseded_at: string | null;
};

export type TReviewMode = "preview" | "edit" | "split" | "diff";
export type TSidebarTab = "issues" | "claims" | "sources" | "metadata";
