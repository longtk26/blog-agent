"use client";

import { markdown } from "@codemirror/lang-markdown";
import { EditorView } from "@codemirror/view";
import CodeMirror from "@uiw/react-codemirror";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { useTheme } from "next-themes";
import { useEffect, useRef } from "react";

const extensions = [markdown(), EditorView.lineWrapping];

type MarkdownEditorProps = {
  value: string;
  onChange: (value: string) => void;
  jumpToLine: { line: number; nonce: number } | null;
  readOnly?: boolean;
};

export function MarkdownEditor({ value, onChange, jumpToLine, readOnly }: MarkdownEditorProps) {
  const { resolvedTheme } = useTheme();
  const ref = useRef<ReactCodeMirrorRef>(null);

  useEffect(() => {
    const view = ref.current?.view;
    if (!view || !jumpToLine) return;
    const line = view.state.doc.line(Math.min(Math.max(jumpToLine.line, 1), view.state.doc.lines));
    view.dispatch({ selection: { anchor: line.from, head: line.to }, effects: EditorView.scrollIntoView(line.from, { y: "center" }) });
    view.focus();
  }, [jumpToLine]);

  return (
    <CodeMirror
      ref={ref}
      value={value}
      onChange={onChange}
      readOnly={readOnly}
      extensions={extensions}
      theme={resolvedTheme === "dark" ? "dark" : "light"}
      basicSetup={{ foldGutter: false, highlightActiveLineGutter: true }}
      className="overflow-hidden rounded-lg border text-sm [&_.cm-editor]:min-h-[60vh] [&_.cm-scroller]:font-mono"
      aria-label="Article Markdown"
    />
  );
}
