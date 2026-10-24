const FENCE = /^\s*(```|~~~)/;
const LEADING_NUMBER = /^\s*(?:step\s+\d+\s*[:.-]|\d+(?:\.\d+)*[.)]?)\s*/i;
const SKIPPED = new Set(["Table of Contents", "References"]);

export const INTRO = "Introduction";

export function stripHeadingNumber(heading: string) {
  return heading.replace(LEADING_NUMBER, "").trim() || heading.trim();
}

function plainText(markdown: string) {
  return markdown.replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/<[^>]+>/g, "").replace(/(\*\*|__|\*|_|`|~~)/g, "").trim();
}

export type TArticleSection = { name: string; heading: string; body: string; line: number };

/** H2 sections of an assembled article (fence-aware), like the API's split_article: the intro is "Introduction". */
export function splitSections(markdown: string): TArticleSection[] {
  const sections: TArticleSection[] = [{ name: INTRO, heading: INTRO, body: "", line: 1 }];
  let current: TArticleSection | null = sections[0];
  let inFence = false;
  markdown.split("\n").forEach((line, index) => {
    if (FENCE.test(line)) inFence = !inFence;
    const h2 = !inFence ? /^##\s+(.*?)\s*#*\s*$/.exec(line) : null;
    if (h2) {
      const heading = plainText(h2[1]);
      current = SKIPPED.has(heading) ? null : { name: stripHeadingNumber(heading), heading, body: "", line: index + 1 };
      if (current) sections.push(current);
      return;
    }
    if (current && !/^#\s/.test(line)) current.body += `${line}\n`;
  });
  return sections;
}

/** Section names that link to any of these URLs. */
export function sectionsCiting(sections: TArticleSection[], urls: string[]) {
  return sections.filter((section) => urls.some((url) => url && section.body.includes(`](${url}`))).map((s) => s.name);
}

export function normaliseSentence(text: string) {
  return plainText(text).replace(/\s+/g, " ").toLowerCase();
}
