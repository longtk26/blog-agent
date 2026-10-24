// Copied verbatim from profile-ui/components/post/MarkdownComp.tsx (see PROVENANCE.md).
// The site joins consecutive text lines into one paragraph; the preview must do exactly the same.
export const normalizeMarkdown = (value: string) => {
  let normalized = value.replace(/\r\n?/g, "\n");

  // Ensure all block math $$ ... $$ are isolated with blank lines before and after
  // so CommonMark never treats them as inline elements within a <p> tag
  normalized = normalized.replace(/([^\n])\n(\$\$[\s\S]*?\$\$)/g, "$1\n\n$2");
  normalized = normalized.replace(/(\$\$[\s\S]*?\$\$)\n([^\n])/g, "$1\n\n$2");

  const parts = normalized.split(/```/);

  const isBlockStart = (line: string) => {
    const trimmed = line.trimStart();
    return (
      trimmed.startsWith("- ") ||
      trimmed.startsWith("* ") ||
      trimmed.startsWith("+ ") ||
      /^\d+\.\s+/.test(trimmed) ||
      /^#{1,6}\s+/.test(trimmed) ||
      trimmed.startsWith("> ") ||
      trimmed.startsWith("|") ||
      trimmed.startsWith("$$") ||
      trimmed.startsWith("$")
    );
  };

  const isMathBlock = (line: string) => {
    const trimmed = line.trim();
    return trimmed.startsWith("$$") || trimmed.endsWith("$$");
  };

  return parts
    .map((part, index) => {
      if (index % 2 === 1) {
        return part;
      }

      const lines = part.split("\n");
      const merged: string[] = [];

      for (const line of lines) {
        const isBlank = line.trim().length === 0;

        if (isBlank) {
          merged.push("");
          continue;
        }

        const lastIndex = merged.length - 1;
        const lastLine = lastIndex >= 0 ? merged[lastIndex] : "";
        const canMerge =
          lastLine.length > 0 &&
          !isBlockStart(lastLine) &&
          !isBlockStart(line) &&
          !isMathBlock(lastLine) &&
          !isMathBlock(line);

        if (canMerge) {
          merged[lastIndex] = `${lastLine} ${line.trimStart()}`;
        } else {
          merged.push(line);
        }
      }

      return merged.join("\n");
    })
    .join("```");
};
