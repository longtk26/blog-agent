import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// Basic, safe Markdown (no raw HTML). Epic 4 replaces this with the site-accurate renderer.
const components: Components = {
  h1: ({ children }) => <h1 className="mb-4 text-2xl font-semibold tracking-tight">{children}</h1>,
  h2: ({ children }) => <h2 className="mt-8 mb-3 text-lg font-semibold">{children}</h2>,
  h3: ({ children }) => <h3 className="mt-6 mb-2 font-semibold">{children}</h3>,
  p: ({ children }) => <p className="my-3 leading-7">{children}</p>,
  ul: ({ children }) => <ul className="my-3 ml-6 list-disc space-y-1.5">{children}</ul>,
  ol: ({ children }) => <ol className="my-3 ml-6 list-decimal space-y-1.5">{children}</ol>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer noopener" className="text-primary underline underline-offset-4">
      {children}
    </a>
  ),
  code: ({ children }) => <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-sm">{children}</code>,
  em: ({ children }) => <em className="text-muted-foreground">{children}</em>,
};

type MarkdownViewProps = {
  markdown: string;
};

export function MarkdownView({ markdown }: MarkdownViewProps) {
  return (
    <div className="text-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
