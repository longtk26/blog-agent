import { z } from "zod";

import type { TArticleMetadata } from "../types";

// Mirrors the API's ArticleMetadataDto. Softer site rules (description ≤ 160, 1–4 tags) are reported by the
// validators as issues instead, so the owner can still save and see them.
export const metadataSchema = z.object({
  title: z.string().trim().min(3, "At least 3 characters").max(200),
  slug: z
    .string()
    .trim()
    .min(3, "At least 3 characters")
    .max(80)
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Lowercase words joined by dashes"),
  description: z.string().trim().min(1, "Required").max(400),
  tags: z
    .string()
    .trim()
    .refine((value) => value.split(",").every((tag) => !tag.trim() || /^[a-z0-9]{1,30}$/.test(tag.trim())), "Lowercase letters/digits, comma-separated"),
});

export type TMetadataFormValues = z.infer<typeof metadataSchema>;

export function toMetadataFormValues(metadata: TArticleMetadata): TMetadataFormValues {
  return { title: metadata.title, slug: metadata.slug, description: metadata.description, tags: metadata.tags.join(", ") };
}

export function toArticleMetadata(values: TMetadataFormValues): TArticleMetadata {
  return {
    title: values.title.trim(),
    slug: values.slug.trim(),
    description: values.description.trim(),
    tags: values.tags.split(",").map((tag) => tag.trim()).filter(Boolean),
  };
}
