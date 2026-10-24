"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SitePreview } from "./SitePreview";

type TPreviewFixture = { key: string; label: string; title: string; markdown: string };

type PreviewFixturesProps = {
  fixtures: TPreviewFixture[];
};

export function PreviewFixtures({ fixtures }: PreviewFixturesProps) {
  return (
    <Tabs defaultValue={fixtures[0]?.key}>
      <TabsList>
        {fixtures.map((fixture) => (
          <TabsTrigger key={fixture.key} value={fixture.key}>
            {fixture.label}
          </TabsTrigger>
        ))}
      </TabsList>
      {fixtures.map((fixture) => (
        <TabsContent key={fixture.key} value={fixture.key} className="mt-3">
          <SitePreview markdown={fixture.markdown} title={fixture.title} />
        </TabsContent>
      ))}
    </Tabs>
  );
}
