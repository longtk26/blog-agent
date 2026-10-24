"use client";

import { SaveIcon, Undo2Icon } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SitePreview } from "@/features/preview/components/SitePreview";
import type { TRevision, TRevisionSummary } from "@/features/tasks/types";
import { useReviewStore } from "@/store/review-store";
import { useRevisionEditor } from "../hooks/use-revision-editor";
import { useReviewActions } from "../hooks/use-review";
import { useTextHighlight } from "../hooks/use-text-highlight";
import { splitSections, stripHeadingNumber } from "../markdown-sections";
import type { TReviewMode } from "../types";
import { MarkdownEditor } from "./MarkdownEditor";
import { RevisionDiff } from "./RevisionDiff";
import { DevtoPreview } from "./DevtoPreview";

type ReviewMainProps = {
  taskId: string;
  revision: TRevision;
  revisions: TRevisionSummary[];
  canEdit: boolean;
  readOnlyReason: string | null;
};

function scrollToSection(root: HTMLElement | null, section: string) {
  const wanted = stripHeadingNumber(section).toLowerCase();
  const heading = [...(root?.querySelectorAll("h2, h3") ?? [])].find(
    (element) => stripHeadingNumber(element.textContent ?? "").toLowerCase() === wanted,
  );
  heading?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function ReviewMain({ taskId, revision, revisions, canEdit, readOnlyReason }: ReviewMainProps) {
  const mode = useReviewStore((state) => state.mode);
  const setMode = useReviewStore((state) => state.setMode);
  const updateMarkdown = useReviewStore((state) => state.updateMarkdown);
  const highlighted = useReviewStore((state) => state.highlightedSentence);
  const highlightScroll = useReviewStore((state) => state.highlightScroll);
  const jumpTarget = useReviewStore((state) => state.jumpTarget);
  const metadataValid = useReviewStore((state) => state.metadataValid);
  const { draft, dirty, startEditing, discard } = useRevisionEditor(taskId, revision, canEdit);
  const { save } = useReviewActions(taskId);
  const previewRef = useRef<HTMLDivElement>(null);

  const editing = Boolean(draft && canEdit && draft.baseRevisionId === revision.id);
  const markdown = editing && draft ? draft.markdown : revision.markdown;
  const title = editing && draft ? draft.metadata.title : revision.title;
  const sections = useMemo(() => splitSections(markdown), [markdown]);

  useTextHighlight(previewRef, highlighted, highlightScroll, `${mode}:${markdown.length}`);

  const editorJump = useMemo(() => {
    if (!jumpTarget) return null;
    const line = jumpTarget.line ?? sections.find((s) => s.name.toLowerCase() === stripHeadingNumber(jumpTarget.section ?? "").toLowerCase())?.line;
    return line ? { line, nonce: jumpTarget.nonce } : null;
  }, [jumpTarget, sections]);

  useEffect(() => {
    if (jumpTarget?.section && mode !== "edit") scrollToSection(previewRef.current, jumpTarget.section);
  }, [jumpTarget, mode]);

  const onModeChange = (value: string) => {
    const next = value as TReviewMode;
    if ((next === "edit" || next === "split") && canEdit) startEditing();
    setMode(next);
  };

  const onSave = () => {
    if (!draft) return;
    save.mutate({ base_revision_id: draft.baseRevisionId, markdown: draft.markdown, metadata: draft.metadata });
  };

  const preview = <SitePreview markdown={markdown} title={title} containerRef={previewRef} />;
  const editor = (
    <MarkdownEditor value={markdown} onChange={updateMarkdown} jumpToLine={editorJump} readOnly={!editing} />
  );

  return (
    <Tabs value={mode} onValueChange={onModeChange} className="min-w-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <TabsList>
          <TabsTrigger value="preview">Preview</TabsTrigger>
          <TabsTrigger value="devto">Dev.to Preview</TabsTrigger>
          <TabsTrigger value="edit">Edit</TabsTrigger>
          <TabsTrigger value="split">Split</TabsTrigger>
          <TabsTrigger value="diff">Changes</TabsTrigger>
        </TabsList>
        {editing ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{dirty ? "Unsaved changes" : "No changes yet"}</span>
            <Button variant="ghost" size="sm" onClick={discard} disabled={save.isPending}>
              <Undo2Icon /> Discard
            </Button>
            <Button size="sm" onClick={onSave} disabled={!dirty || !metadataValid || save.isPending}>
              <SaveIcon /> {save.isPending ? "Saving…" : `Save as r${revision.revision_number + 1}`}
            </Button>
          </div>
        ) : null}
      </div>

      {(mode === "edit" || mode === "split") && !canEdit && readOnlyReason ? (
        <Alert className="mt-3">
          <AlertDescription>{readOnlyReason}</AlertDescription>
        </Alert>
      ) : null}

      <TabsContent value="preview" className="mt-3">
        {preview}
      </TabsContent>
      <TabsContent value="devto" className="mt-3">
        <DevtoPreview revision={revision} />
      </TabsContent>
      <TabsContent value="edit" className="mt-3">
        {editor}
      </TabsContent>
      <TabsContent value="split" className="mt-3">
        <div className="grid gap-3 xl:grid-cols-2">
          {editor}
          <div className="max-h-[80vh] overflow-y-auto rounded-lg">{preview}</div>
        </div>
      </TabsContent>
      <TabsContent value="diff" className="mt-3">
        <RevisionDiff revision={revision} revisions={revisions} />
      </TabsContent>
    </Tabs>
  );
}
