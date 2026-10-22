import { ComingSoon } from "@/components/layout/ComingSoon";
import { Container } from "@/components/layout/Container";
import { PageHeader } from "@/components/layout/PageHeader";
import { Stack } from "@/components/layout/Stack";

export default function NewTaskPage() {
  return (
    <Container size="md">
      <Stack gap="lg">
        <PageHeader title="New task" description="Ask the agent to research a topic or write a blog post." />
        <ComingSoon title="Task form">The research / write request form arrives with Epic 2.</ComingSoon>
      </Stack>
    </Container>
  );
}
