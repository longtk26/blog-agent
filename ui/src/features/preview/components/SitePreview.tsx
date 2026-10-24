"use client";

import "katex/dist/katex.min.css";
import "prismjs/themes/prism-tomorrow.css";

import { ShieldAlertIcon } from "lucide-react";
import Prism from "prismjs";
import "prismjs/components/prism-bash";
import "prismjs/components/prism-java";
import "prismjs/components/prism-javascript";
import "prismjs/components/prism-json";
import "prismjs/components/prism-markdown";
import "prismjs/components/prism-python";
import "prismjs/components/prism-typescript";
import { useMemo } from "react";
import type { MouseEvent, RefObject } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import rehypeSlug from "rehype-slug";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import type { PluggableList } from "unified";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useHydrated } from "@/hooks/use-hydrated";
import { cn } from "@/lib/utils";
import { normalizeMarkdown } from "../normalize-markdown";
import { getSanitizeReport, previewSanitizeSchema } from "../sanitize";
import { MermaidDiagram } from "./MermaidDiagram";

// Component overrides ported from profile-ui/components/post/MarkdownComp.tsx (see PROVENANCE.md).
// Differences: links never navigate the dashboard away (in-page anchors scroll inside the preview), and
// the pipeline runs rehype-sanitize between rehype-raw and rehype-katex.
const components: Components = {
  h1: ({ children, id }) => (
    <h1 id={id} className="my-3 text-left text-3xl font-bold text-zinc-100">
      {children}
    </h1>
  ),
  h2: ({ children, id }) => (
    <h2 id={id} className="my-3 text-left text-2xl font-semibold text-zinc-100">
      {children}
    </h2>
  ),
  h3: ({ children, id }) => (
    <h3 id={id} className="my-2 text-left text-xl font-semibold text-zinc-200">
      {children}
    </h3>
  ),
  p: ({ children }) => <p className="my-4 text-left leading-relaxed text-zinc-300">{children}</p>,
  a: ({ children, href }) => {
    const isHashLink = href?.startsWith("#") ?? false;
    const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
      if (!href || !isHashLink) return;
      event.preventDefault();
      const root = event.currentTarget.closest("[data-site-preview]");
      root?.querySelector(`[id="${CSS.escape(decodeURIComponent(href.slice(1)))}"]`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    return (
      <a
        href={href ?? "#"}
        rel={isHashLink ? undefined : "noreferrer noopener"}
        className="text-blue-500 hover:underline"
        target={isHashLink ? "_self" : "_blank"}
        onClick={handleClick}
      >
        {children}
      </a>
    );
  },
  ul: ({ children }) => <ul className="my-2 list-disc pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 list-decimal pl-5">{children}</ol>,
  li: ({ children }) => <li className="mb-1">{children}</li>,
  code: ({ className, children }) => {
    const rawCode = String(children).replace(/\n$/, "");
    const language = /language-(\w+)/.exec(className ?? "")?.[1] ?? "";

    if (language === "mermaid") return <MermaidDiagram chart={rawCode} />;

    if (!className && !rawCode.includes("\n") && rawCode.length <= 60) {
      return <code className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-sm text-emerald-300">{rawCode}</code>;
    }

    const targetLang = language || "text";
    const grammar = Prism.languages[targetLang] ?? Prism.languages.markdown;
    // Prism escapes the code it highlights, so this HTML only contains its own token spans.
    const highlighted = Prism.highlight(rawCode, grammar, targetLang);
    return (
      <pre className="my-4 overflow-auto rounded-md bg-[#1e1e1e] p-4 text-white">
        <code className={className} dangerouslySetInnerHTML={{ __html: highlighted }} />
      </pre>
    );
  },
  pre: ({ children }) => <>{children}</>,
  // eslint-disable-next-line @next/next/no-img-element -- mirrors the site, which renders plain <img> for content images
  img: ({ src, alt }) => {
    let resolvedSrc = typeof src === "string" ? src : "";
    if (resolvedSrc.startsWith("asset://")) {
      const assetId = resolvedSrc.replace("asset://", "").trim();
      resolvedSrc = `/api/agent/assets/${assetId}?type=svg`;
    }
    return <img className="my-4 rounded-md max-w-full h-auto" src={resolvedSrc} alt={alt ?? ""} />;
  },
  blockquote: ({ children }) => (
    <blockquote className="my-4 border-l-4 border-black/20 pl-4 italic dark:border-white/25">{children}</blockquote>
  ),
};

function resolveAssetUrls(content: string): string {
  return content.replace(/asset:\/\/([0-9a-fA-F-]+)(?:\?type=(\w+))?/g, (_, id, type) => {
    return `/api/agent/assets/${id}?type=${type || "svg"}`;
  });
}

const remarkPlugins: PluggableList = [remarkGfm, remarkMath];
const rehypePlugins: PluggableList = [rehypeRaw, [rehypeSanitize, previewSanitizeSchema], rehypeKatex, rehypeSlug];

type SitePreviewProps = {
  markdown: string;
  title: string;
  coverUrl?: string | null;
  containerRef?: RefObject<HTMLDivElement | null>;
  className?: string;
};

/** Renders a draft the way leon-pham.vercel.app/posts/<slug> does: post header (title + cover) and the
 *  Markdown body inside `.prose-post`, on the site's dark surface regardless of the dashboard theme. */
export function SitePreview({ markdown, title, coverUrl, containerRef, className }: SitePreviewProps) {
  const resolvedMarkdown = useMemo(() => resolveAssetUrls(markdown), [markdown]);
  const normalized = useMemo(() => normalizeMarkdown(resolvedMarkdown), [resolvedMarkdown]);
  const report = useMemo(() => getSanitizeReport(normalized), [normalized]);
  const sanitized = report.removedElements.length > 0 || report.removedAttributes > 0;
  // Client-only body: like the site, long inline code renders as <pre> inside <p>, which the HTML parser
  // would restructure and break hydration. The DOM APIs used on the client keep the site's nesting.
  const hydrated = useHydrated();

  return (
    <div data-site-preview ref={containerRef} className={cn("site-preview relative rounded-lg", className)}>
      {sanitized ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge variant="destructive" className="absolute top-3 right-3 z-10">
              <ShieldAlertIcon /> Sanitised
            </Badge>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            Unsafe or non-contract HTML was removed from this preview
            {report.removedElements.length ? `: <${report.removedElements.join(">, <")}>` : ""}
            {report.removedAttributes ? ` (${report.removedAttributes} attribute(s))` : ""}. The live site would render it — fix
            the Markdown before approving.
          </TooltipContent>
        </Tooltip>
      ) : null}
      <div className="mx-auto max-w-3xl px-4 pt-8 pb-24 sm:px-6">
        <div className="antialiased">
          <header className="mb-8">
            <h1 className="mb-6 text-3xl leading-tight font-bold tracking-tight text-zinc-50 md:text-4xl">{title}</h1>
            {coverUrl ? (
              <div className="relative aspect-[16/9] w-full overflow-hidden rounded-xl border border-zinc-800">
                {/* eslint-disable-next-line @next/next/no-img-element -- remote cover from the draft, not optimisable here */}
                <img alt={title} src={coverUrl} className="absolute inset-0 h-full w-full object-cover" />
              </div>
            ) : null}
          </header>
          <div className="prose-post">
            {hydrated ? (
              <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins} components={components}>
                {normalized}
              </ReactMarkdown>
            ) : (
              <Skeleton className="h-96 bg-zinc-900" />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
