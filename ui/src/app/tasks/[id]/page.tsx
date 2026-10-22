import { Suspense } from "react";

import { Container } from "@/components/layout/Container";
import { Skeleton } from "@/components/ui/skeleton";
import { TaskDetail } from "@/features/tasks/components/TaskDetail";

export default function TaskDetailPage() {
  // useParams() suspends for dynamic params under Cache Components; the fallback is the static shell.
  return (
    <Suspense
      fallback={
        <Container>
          <Skeleton className="h-96" />
        </Container>
      }
    >
      <TaskDetail />
    </Suspense>
  );
}
