import Link from "next/link";

import { ComingSoon } from "@/components/layout/ComingSoon";
import { Container } from "@/components/layout/Container";
import { PageHeader } from "@/components/layout/PageHeader";
import { Stack } from "@/components/layout/Stack";
import { Button } from "@/components/ui/button";

export default function TasksPage() {
  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title="Tasks"
          description="Research and writing tasks you have asked the agent to run."
          actions={
            <Button asChild>
              <Link href="/tasks/new">New task</Link>
            </Button>
          }
        />
        <ComingSoon title="No tasks yet">The task list arrives with Epic 2 (research workflow).</ComingSoon>
      </Stack>
    </Container>
  );
}
