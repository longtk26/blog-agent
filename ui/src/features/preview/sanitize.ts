import type { Element, Root } from "hast";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import type { Options as TSanitizeSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import remarkParse from "remark-parse";
import remarkRehype from "remark-rehype";
import { unified } from "unified";
import { visit } from "unist-util-visit";

/** The site renders raw HTML unsanitised; the dashboard must not, because drafts are model output derived from
 *  web pages. This allowlist is GitHub's schema (everything Markdown itself produces) plus the classes math
 *  rendering needs. Anything else in raw HTML — scripts, iframes, styles, event handlers — is removed. */
export const previewSanitizeSchema: TSanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [["className", /^language-./, "math-inline", "math-display"]],
  },
  protocols: {
    ...defaultSchema.protocols,
    src: [...(defaultSchema.protocols?.src ?? ["http", "https"]), "asset"],
  },
};

export type TSanitizeReport = { removedElements: string[]; removedAttributes: number };

type TCounts = { tags: Map<string, number>; attributes: number };

function count(tree: Root): TCounts {
  const tags = new Map<string, number>();
  let attributes = 0;
  visit(tree, "element", (node: Element) => {
    tags.set(node.tagName, (tags.get(node.tagName) ?? 0) + 1);
    attributes += Object.keys(node.properties ?? {}).length;
  });
  return { tags, attributes };
}

const toHast = unified().use(remarkParse).use(remarkGfm).use(remarkMath).use(remarkRehype, { allowDangerousHtml: true }).use(rehypeRaw);
const sanitizer = unified().use(rehypeSanitize, previewSanitizeSchema);

/** What sanitisation removes from this (already normalised) Markdown, for the preview's warning badge. */
export function getSanitizeReport(markdown: string): TSanitizeReport {
  const raw = toHast.runSync(toHast.parse(markdown)) as Root;
  const before = count(raw);
  const after = count(sanitizer.runSync(structuredClone(raw)) as Root);
  const removedElements = [...before.tags].flatMap(([tag, n]) => (n > (after.tags.get(tag) ?? 0) ? [tag] : []));
  return { removedElements, removedAttributes: Math.max(0, before.attributes - after.attributes) };
}
