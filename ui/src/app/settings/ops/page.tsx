import Link from "next/link";
import { ArrowLeftIcon } from "lucide-react";

import { Container } from "@/components/layout/Container";
import { PageHeader } from "@/components/layout/PageHeader";
import { Stack } from "@/components/layout/Stack";
import { Button } from "@/components/ui/button";
import { OpsDashboard } from "@/features/stats/components/OpsDashboard";

export default function OpsPage() {
  return (
    <Container size="xl">
      <Stack gap="lg">
        <div>
          <Button variant="ghost" size="sm" asChild className="-ml-2 mb-2">
            <Link href="/settings">
              <ArrowLeftIcon className="h-4 w-4" /> Back to Settings
            </Link>
          </Button>
          <PageHeader
            title="Operations & Observability"
            description="30-day reliability metrics, stage durations, LLM cost analysis, and failure traces."
          />
        </div>
        <OpsDashboard />
      </Stack>
    </Container>
  );
}
