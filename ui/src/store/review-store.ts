import { create } from "zustand";
import { devtools } from "zustand/middleware";

import type { TArticleMetadata, TReviewMode, TSidebarTab } from "@/features/review/types";

export type TEditorDraft = { baseRevisionId: string; markdown: string; metadata: TArticleMetadata };

type TReviewState = {
  taskId: string | null;
  mode: TReviewMode;
  sidebarTab: TSidebarTab;
  selectedRevisionId: string | null; // null = follow the latest revision
  diffFromId: string | null;
  highlightedSentence: string | null;
  highlightScroll: boolean; // scroll the preview to the highlight (on click, not on hover)
  jumpTarget: { section: string | null; line: number | null; nonce: number } | null;
  draft: TEditorDraft | null;
  metadataValid: boolean;
  openTask: (taskId: string) => void;
  setMode: (mode: TReviewMode) => void;
  setSidebarTab: (tab: TSidebarTab) => void;
  selectRevision: (revisionId: string | null) => void;
  setDiffFrom: (revisionId: string | null) => void;
  highlight: (sentence: string | null, scroll?: boolean) => void;
  jumpTo: (target: { section: string | null; line: number | null }) => void;
  startDraft: (draft: TEditorDraft) => void;
  updateMarkdown: (markdown: string) => void;
  updateMetadata: (metadata: TArticleMetadata) => void;
  discardDraft: () => void;
  setMetadataValid: (valid: boolean) => void;
};

/** Keeps the H1 in step with the metadata title (the validators block a mismatch). */
function syncTitleHeading(markdown: string, previousTitle: string, title: string) {
  if (previousTitle === title) return markdown;
  return markdown.replace(/^#\s+(.+)$/m, (line, current: string) => (current.trim() === previousTitle.trim() ? `# ${title}` : line));
}

const initialView = {
  mode: "preview" as TReviewMode,
  sidebarTab: "issues" as TSidebarTab,
  selectedRevisionId: null,
  diffFromId: null,
  highlightedSentence: null,
  highlightScroll: false,
  jumpTarget: null,
  draft: null,
  metadataValid: true,
};

export const useReviewStore = create<TReviewState>()(
  devtools(
    (set) => ({
      taskId: null,
      ...initialView,
      openTask: (taskId) =>
        set((state) => (state.taskId === taskId ? state : { taskId, ...initialView }), false, "review/openTask"),
      setMode: (mode) => set({ mode }, false, "review/setMode"),
      setSidebarTab: (sidebarTab) => set({ sidebarTab }, false, "review/setSidebarTab"),
      selectRevision: (selectedRevisionId) => set({ selectedRevisionId, diffFromId: null }, false, "review/selectRevision"),
      setDiffFrom: (diffFromId) => set({ diffFromId }, false, "review/setDiffFrom"),
      highlight: (highlightedSentence, highlightScroll = false) =>
        set({ highlightedSentence, highlightScroll }, false, "review/highlight"),
      jumpTo: (target) =>
        set((state) => ({ jumpTarget: { ...target, nonce: (state.jumpTarget?.nonce ?? 0) + 1 } }), false, "review/jumpTo"),
      startDraft: (draft) => set({ draft }, false, "review/startDraft"),
      updateMarkdown: (markdown) =>
        set((state) => (state.draft ? { draft: { ...state.draft, markdown } } : state), false, "review/updateMarkdown"),
      updateMetadata: (metadata) =>
        set(
          (state) =>
            state.draft
              ? {
                  draft: {
                    ...state.draft,
                    metadata,
                    markdown: syncTitleHeading(state.draft.markdown, state.draft.metadata.title, metadata.title),
                  },
                }
              : state,
          false,
          "review/updateMetadata",
        ),
      discardDraft: () => set({ draft: null, metadataValid: true }, false, "review/discardDraft"),
      setMetadataValid: (metadataValid) => set({ metadataValid }, false, "review/setMetadataValid"),
    }),
    { name: "review-store" },
  ),
);
