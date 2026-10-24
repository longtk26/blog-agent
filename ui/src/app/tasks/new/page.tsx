import { Suspense } from "react";

import { Container } from "@/components/layout/Container";
import { PageHeader } from "@/components/layout/PageHeader";
import { Stack } from "@/components/layout/Stack";
import { Skeleton } from "@/components/ui/skeleton";
import { TaskForm } from "@/features/tasks/components/TaskForm";

export default function NewTaskPage() {
  return (
    <Container size="md">
      <Stack gap="lg">
        <PageHeader title="New task" description="Ask the agent to research a topic or write a blog post." />
        {/* useSearchParams (?from= for cloning) needs a Suspense boundary under Cache Components. */}
        <Suspense fallback={<Skeleton className="h-96" />}>
          <TaskForm />
        </Suspense>
      </Stack>
    </Container>
  );
}
