import Link from "next/link";

import { Container } from "@/components/layout/Container";
import { PageHeader } from "@/components/layout/PageHeader";
import { Stack } from "@/components/layout/Stack";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { HealthDetails } from "@/features/health/components/HealthDetails";
import { StyleGuideEditor } from "@/features/style-guide/components/StyleGuideEditor";

export default function SettingsPage() {
  return (
    <Container size="md">
      <Stack gap="lg">
        <PageHeader title="Settings" description="Backend status, models and your writing style guide." />
        <HealthDetails />
        <Card className="p-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold">Operations & Telemetry Dashboard</h3>
            <p className="text-xs text-muted-foreground">
              Review 30-day task durations, stage latencies, estimated LLM costs, tool error rates, and failure traces.
            </p>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link href="/settings/ops">Open Ops View</Link>
          </Button>
        </Card>
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
