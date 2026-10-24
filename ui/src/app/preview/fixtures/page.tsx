import { readFile } from "node:fs/promises";
import path from "node:path";
import { cacheLife } from "next/cache";

import { Container } from "@/components/layout/Container";
import { PageHeader } from "@/components/layout/PageHeader";
import { PreviewFixtures } from "@/features/preview/components/PreviewFixtures";

const FIXTURES = [
  { key: "concept", label: "Concept · fine_tuning_concepts.md" },
  { key: "tutorial", label: "Tutorial · fine_tuning_implementation.md" },
  { key: "math", label: "Math-heavy sample" },
];

async function loadFixtures() {
  "use cache";
  // Read once at build time; the fixtures are part of the source tree (not shipped in the standalone image).
  cacheLife("max");
  const dir = path.join(process.cwd(), "src/features/preview/fixtures");
  return Promise.all(
    FIXTURES.map(async (fixture) => {
      const markdown = await readFile(path.join(dir, `${fixture.key}.md`), "utf-8");
      const title = markdown.match(/^#\s+(.+)/m)?.[1]?.trim() ?? fixture.key;
      return { ...fixture, title, markdown };
    }),
  );
}

export default async function PreviewFixturesPage() {
  const fixtures = await loadFixtures();
  return (
    <Container>
      <PageHeader
        title="Preview fixtures"
        description="Compare the site-accurate preview with the live site (E4-S1). Open a published post side by side."
      />
      <PreviewFixtures fixtures={fixtures} />
    </Container>
  );
}
