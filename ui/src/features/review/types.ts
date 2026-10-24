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
  options: { devto_mode?: TDevtoMode; mode?: TDevtoMode; acknowledged_blockers?: string[] };
  decision: "approved" | "superseded";
  reviewer_id: string;
  reviewed_at: string;
  superseded_at: string | null;
};

export type TPublicationStatus = "pending" | "published" | "failed" | "unpublished";

export type TPublication = {
  id: string;
  task_id: string;
  destination: TPublicationTarget;
  article_revision_id: string;
  rendered_content_hash: string;
  destination_id: string | null;
  destination_url: string | null;
  remote_document_id?: string | null;
  remote_url?: string | null;
  destination_meta: {
    studio_url?: string;
    cover_image_key?: string;
    image_count?: number;
    tag_count?: number;
    [key: string]: unknown;
  };
  status: TPublicationStatus;
  attempt_count: number;
  last_error: string | null;
  published_at: string | null;
  unpublished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TReviewMode = "preview" | "devto" | "edit" | "split" | "diff";
export type TSidebarTab = "issues" | "claims" | "sources" | "metadata" | "diagrams" | "publish";

export type TDiagramAsset = {
  id: string;
  task_id: string;
  article_revision_id: string | null;
  slot_id: string;
  format: "drawio" | "mermaid";
  spec: {
    type?: string;
    title?: string;
    direction?: string;
    nodes?: Array<{ id: string; label: string; kind?: string }>;
    groups?: Array<{ id: string; label: string }>;
    edges?: Array<{ from: string; to: string; label?: string }>;
    participants?: Array<{ id: string; label: string }>;
    messages?: Array<{ from: string; to: string; label?: string }>;
    [key: string]: unknown;
  };
  source_path: string;
  svg_path: string | null;
  png_path: string | null;
  sha256: string;
  validation_status: string;
  created_at: string;
  source_url: string;
  svg_url: string;
  png_url: string | null;
};
