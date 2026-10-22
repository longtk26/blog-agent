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
      </Stack>
    </Container>
  );
}
