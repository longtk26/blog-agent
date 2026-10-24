import { useEffect } from "react";
import type { RefObject } from "react";

import { normaliseSentence } from "../markdown-sections";

const HIGHLIGHT = "review-claim";

/** Finds `text` in the rendered preview and paints it with the CSS Custom Highlight API (no DOM changes,
 *  so React and the Markdown renderer are unaffected). Browsers without the API simply skip highlighting. */
function findRange(root: HTMLElement, text: string): Range | null {
  // KaTeX renders each formula twice (hidden MathML + visible HTML); search only the visible copy.
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => (node.parentElement?.closest(".katex-mathml") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  const positions: { node: Text; offset: number }[] = [];
  let haystack = "";
  for (let node = walker.nextNode() as Text | null; node; node = walker.nextNode() as Text | null) {
    const value = node.data;
    for (let i = 0; i < value.length; i += 1) {
      const isSpace = /\s/.test(value[i]);
      if (isSpace && haystack.endsWith(" ")) continue;
      haystack += isSpace ? " " : value[i].toLowerCase();
      positions.push({ node, offset: i });
    }
  }
  const needle = normaliseSentence(text);
  for (const length of [needle.length, 80, 40]) {
    const probe = needle.slice(0, length).trim();
    if (probe.length < 12) continue;
    const index = haystack.indexOf(probe);
    if (index < 0) continue;
    const start = positions[index];
    const end = positions[index + probe.length - 1];
    const range = document.createRange();
    range.setStart(start.node, start.offset);
    range.setEnd(end.node, end.offset + 1);
    return range;
  }
  return null;
}

export function useTextHighlight(
  containerRef: RefObject<HTMLElement | null>,
  text: string | null,
  scroll: boolean,
  deps: unknown,
) {
  useEffect(() => {
    const root = containerRef.current;
    if (!root || !text || typeof CSS === "undefined" || !("highlights" in CSS)) return;
    const range = findRange(root, text);
    if (!range) return;
    CSS.highlights.set(HIGHLIGHT, new Highlight(range));
    if (scroll) range.startContainer.parentElement?.scrollIntoView({ block: "center", behavior: "smooth" });
    return () => {
      CSS.highlights.delete(HIGHLIGHT);
    };
  }, [containerRef, text, scroll, deps]);
}
