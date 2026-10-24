import Link from "next/link";

import { Container } from "@/components/layout/Container";
import { PageHeader } from "@/components/layout/PageHeader";
import { Stack } from "@/components/layout/Stack";
import { HealthDetails } from "@/features/health/components/HealthDetails";
import { StyleGuideEditor } from "@/features/style-guide/components/StyleGuideEditor";

export default function SettingsPage() {
  return (
    <Container size="md">
      <Stack gap="lg">
        <PageHeader title="Settings" description="Backend status, models and your writing style guide." />
        <HealthDetails />
        <StyleGuideEditor />
        <p className="text-sm text-muted-foreground">
          Check the site-accurate draft preview against the live site on the{" "}
          <Link href="/preview/fixtures" className="underline underline-offset-4">
            preview fixtures
          </Link>
          .
        </p>
      </Stack>
    </Container>
  );
}
