import { useCallback, useEffect, useRef } from "react";
import { toast } from "sonner";

import type { TRevision } from "@/features/tasks/types";
import { useReviewStore } from "@/store/review-store";
import type { TEditorDraft } from "@/store/review-store";

const storageKey = (taskId: string, baseRevisionId: string) => `blog-agent:draft:${taskId}:${baseRevisionId}`;

// Only article content is stored (no secrets); the key includes the base revision, so a stale draft never
// silently lands on a newer revision.
function readStoredDraft(taskId: string, baseRevisionId: string): TEditorDraft | null {
  try {
    const raw = window.localStorage.getItem(storageKey(taskId, baseRevisionId));
    return raw ? (JSON.parse(raw) as TEditorDraft) : null;
  } catch {
    return null;
  }
}

export function clearStoredDraft(taskId: string, baseRevisionId: string) {
  try {
    window.localStorage.removeItem(storageKey(taskId, baseRevisionId));
  } catch {
    // storage unavailable (private mode): nothing to clear
  }
}

function fromRevision(revision: TRevision): TEditorDraft {
  return {
    baseRevisionId: revision.id,
    markdown: revision.markdown,
    metadata: { title: revision.title, slug: revision.slug, description: revision.description, tags: revision.tags },
  };
}

export function isDraftDirty(draft: TEditorDraft | null, revision: TRevision | undefined) {
  if (!draft || !revision || draft.baseRevisionId !== revision.id) return Boolean(draft);
  const base = fromRevision(revision);
  return draft.markdown !== base.markdown || JSON.stringify(draft.metadata) !== JSON.stringify(base.metadata);
}

/** Owner editing (E4-S3): the draft lives in the review store, survives reloads via localStorage, and the
 *  browser warns before leaving with unsaved changes. */
export function useRevisionEditor(taskId: string, revision: TRevision | undefined, canEdit: boolean) {
  const draft = useReviewStore((state) => state.draft);
  const startDraft = useReviewStore((state) => state.startDraft);
  const discardDraft = useReviewStore((state) => state.discardDraft);
  const setMode = useReviewStore((state) => state.setMode);
  const dirty = isDraftDirty(draft, revision);
  const restoredFor = useRef<string | null>(null);

  // Restore unsaved edits once per base revision.
  useEffect(() => {
    if (!revision || !canEdit || draft || restoredFor.current === revision.id) return;
    restoredFor.current = revision.id;
    const stored = readStoredDraft(taskId, revision.id);
    if (stored && isDraftDirty(stored, revision)) {
      startDraft(stored);
      setMode("split");
      toast.info("Restored your unsaved edits");
    }
  }, [taskId, revision, canEdit, draft, startDraft, setMode]);

  useEffect(() => {
    if (!draft) return;
    const timer = setTimeout(() => {
      try {
        if (dirty) window.localStorage.setItem(storageKey(taskId, draft.baseRevisionId), JSON.stringify(draft));
        else window.localStorage.removeItem(storageKey(taskId, draft.baseRevisionId));
      } catch {
        // storage full or unavailable: the in-memory draft still works
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [taskId, draft, dirty]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const startEditing = useCallback(() => {
    if (!revision) return;
    if (!draft || draft.baseRevisionId !== revision.id) startDraft(readStoredDraft(taskId, revision.id) ?? fromRevision(revision));
  }, [taskId, revision, draft, startDraft]);

  const discard = useCallback(() => {
    if (draft) clearStoredDraft(taskId, draft.baseRevisionId);
    discardDraft();
  }, [taskId, draft, discardDraft]);

  return { draft, dirty, startEditing, discard };
}
