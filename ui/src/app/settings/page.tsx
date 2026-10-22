import { Container } from "@/components/layout/Container";
import { PageHeader } from "@/components/layout/PageHeader";
import { Stack } from "@/components/layout/Stack";
import { HealthDetails } from "@/features/health/components/HealthDetails";

export default function SettingsPage() {
  return (
    <Container size="md">
      <Stack gap="lg">
        <PageHeader title="Settings" description="Backend status and model configuration." />
        <HealthDetails />
      </Stack>
    </Container>
  );
}
