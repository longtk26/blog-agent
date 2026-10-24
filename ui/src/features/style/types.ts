export type TWritingSample = {
  id: string;
  origin: "sanity" | "local" | string;
  remote_id: string;
  title: string;
  tags: string[];
  published_at: string | null;
  approved_as_style_example: boolean;
  content_hash: string;
  chunk_count: number;
  created_at: string | null;
  updated_at: string | null;
};

export type TImportSamplesResult = {
  imported: number;
  updated: number;
  skipped: number;
  total_chunks: number;
};

export type TStyleProfileData = {
  tone?: string;
  voice?: string;
  structure_patterns?: Record<string, string>;
  heading_conventions?: string;
  intro_pattern?: string;
  explanation_devices?: string[];
  code_example_style?: string;
  diagram_usage?: string;
  typical_length?: Record<string, string>;
  do?: string[];
  dont?: string[];
  signature_phrases?: string[];
  [key: string]: unknown;
};

export type TStyleProfile = {
  id: string | null;
  version: number;
  is_active: boolean;
  name: string;
  source: "learned_profile" | "seed" | "owner";
  profile_data: TStyleProfileData;
  markdown_content: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type TOwnerNote = {
  id: string;
  title: string;
  content: string;
  citable_url: string | null;
  quality_score: number;
  created_at: string | null;
  updated_at: string | null;
};

export type TOwnerNoteInput = {
  title: string;
  content: string;
  citable_url?: string | null;
  quality_score?: number;
};
