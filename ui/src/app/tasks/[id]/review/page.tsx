import { Suspense } from "react";

import { Container } from "@/components/layout/Container";
import { Skeleton } from "@/components/ui/skeleton";
import { ReviewPage } from "@/features/review/components/ReviewPage";

export default function TaskReviewPage() {
  // useParams() suspends for dynamic params under Cache Components; the fallback is the static shell.
  return (
    <Suspense
      fallback={
        <Container size="xl">
          <Skeleton className="h-[70vh]" />
        </Container>
      }
    >
      <ReviewPage />
    </Suspense>
  );
}
