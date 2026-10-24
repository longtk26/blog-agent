"use client";

import { useEffect, useId, useState } from "react";

// Port of profile-ui/components/post/MermaidRenderer.tsx (see PROVENANCE.md). One deliberate difference:
// securityLevel "strict" instead of "loose" — labels still allow <b>/<br/>, but click handlers and scripts
// in model-written diagrams never run in the dashboard.
const MERMAID_CONFIG = {
  startOnLoad: false,
  theme: "dark",
  securityLevel: "strict",
  fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  fontSize: 12,
  flowchart: { htmlLabels: true, useMaxWidth: false, padding: 18, nodeSpacing: 36, rankSpacing: 40, curve: "basis" },
  themeVariables: {
    darkMode: true,
    background: "#09090b",
    primaryColor: "#0f172a",
    primaryTextColor: "#f8fafc",
    primaryBorderColor: "#38bdf8",
    lineColor: "#64748b",
    secondaryColor: "#1e293b",
    tertiaryColor: "#1e1e2f",
    fontSize: "12px",
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  },
} as const;

let mermaidPromise: Promise<typeof import("mermaid").default> | null = null;

function loadMermaid() {
  // Loaded on demand: mermaid is large and only needed when a draft contains a diagram.
  mermaidPromise ??= import("mermaid").then(({ default: mermaid }) => {
    mermaid.initialize(MERMAID_CONFIG);
    return mermaid;
  });
  return mermaidPromise;
}

type MermaidDiagramProps = {
  chart: string;
};

type TRenderState = { chart: string; svg: string | null; error: string | null };

export function MermaidDiagram({ chart }: MermaidDiagramProps) {
  const [state, setState] = useState<TRenderState>({ chart: "", svg: null, error: null });
  const uniqueId = `mermaid_${useId().replace(/:/g, "_")}`;

  useEffect(() => {
    let mounted = true;
    const clean = chart.trim();
    if (!clean) return;
    (async () => {
      try {
        if (document.fonts) await document.fonts.ready;
        const mermaid = await loadMermaid();
        const { svg } = await mermaid.render(uniqueId, clean);
        if (mounted) setState({ chart, svg, error: null });
      } catch (err: unknown) {
        if (mounted) setState({ chart, svg: null, error: err instanceof Error ? err.message : String(err) });
      }
    })();
    return () => {
      mounted = false;
      document.getElementById(uniqueId)?.remove();
      document.getElementById(`d${uniqueId}`)?.remove();
    };
  }, [chart, uniqueId]);

  const current = state.chart === chart ? state : { svg: null, error: null };

  if (current.error) {
    return (
      <div className="my-6 rounded-lg border border-red-500/30 bg-red-950/20 p-4 font-mono text-xs text-zinc-300">
        <p className="mb-2 font-semibold text-red-400">Diagram rendering fallback:</p>
        <pre className="overflow-x-auto text-[11.5px] text-zinc-400">{chart}</pre>
      </div>
    );
  }

  if (!current.svg) {
    return (
      <div className="my-6 flex animate-pulse items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/40 p-8 font-mono text-xs text-zinc-500">
        Rendering diagram...
      </div>
    );
  }

  return (
    <div className="mermaid-container my-8 flex flex-col items-center justify-center overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 shadow-inner sm:p-6">
      <style>{`
        #${uniqueId} { max-width: 100% !important; height: auto !important; overflow: visible !important; }
        #${uniqueId} foreignObject { overflow: visible !important; }
        #${uniqueId} foreignObject div {
          display: flex !important; align-items: center !important; justify-content: center !important;
          text-align: center !important; line-height: 1.25 !important; font-size: 12px !important;
          padding: 0 !important; margin: 0 !important; overflow: visible !important;
        }
        #${uniqueId} .nodeLabel {
          line-height: 1.25 !important; font-size: 12px !important; display: inline-block !important;
          padding: 0 !important; margin: 0 !important;
        }
        #${uniqueId} .label { overflow: visible !important; }
      `}</style>
      {/* SVG produced by mermaid in strict mode (it sanitises labels with DOMPurify). */}
      <div className="flex w-full justify-center overflow-x-auto" dangerouslySetInnerHTML={{ __html: current.svg }} />
    </div>
  );
}
