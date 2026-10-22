import { Container } from "@/components/layout/Container";
import { PageHeader } from "@/components/layout/PageHeader";
import { Stack } from "@/components/layout/Stack";
import { TaskForm } from "@/features/tasks/components/TaskForm";

export default function NewTaskPage() {
  return (
    <Container size="md">
      <Stack gap="lg">
        <PageHeader title="New task" description="Ask the agent to research a topic or write a blog post." />
        <TaskForm />
      </Stack>
    </Container>
  );
}
