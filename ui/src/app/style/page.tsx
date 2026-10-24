"use client";

import { BookOpenIcon, FileTextIcon, SparklesIcon } from "lucide-react";

import { Container } from "@/components/layout/Container";
import { PageHeader } from "@/components/layout/PageHeader";
import { Stack } from "@/components/layout/Stack";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { OwnerNotesManager } from "@/features/style/components/OwnerNotesManager";
import { StyleProfileCard } from "@/features/style/components/StyleProfileCard";
import { WritingSamplesTable } from "@/features/style/components/WritingSamplesTable";

export default function StylePage() {
  return (
    <Container size="lg">
      <Stack gap="lg" className="py-6">
        <PageHeader
          title="Style & Knowledge Base"
          description="Manage personal writing style profiles, approved few-shot samples, and owner knowledge base for research."
        />

        <Tabs defaultValue="profile" className="space-y-6">
          <TabsList className="grid w-full grid-cols-3 max-w-[480px]">
            <TabsTrigger value="profile" className="gap-2">
              <SparklesIcon className="h-4 w-4" />
              Style Profile
            </TabsTrigger>
            <TabsTrigger value="samples" className="gap-2">
              <FileTextIcon className="h-4 w-4" />
              Writing Samples
            </TabsTrigger>
            <TabsTrigger value="notes" className="gap-2">
              <BookOpenIcon className="h-4 w-4" />
              Owner Notes
            </TabsTrigger>
          </TabsList>

          <TabsContent value="profile" className="outline-none">
            <StyleProfileCard />
          </TabsContent>

          <TabsContent value="samples" className="outline-none">
            <WritingSamplesTable />
          </TabsContent>

          <TabsContent value="notes" className="outline-none">
            <OwnerNotesManager />
          </TabsContent>
        </Tabs>
      </Stack>
    </Container>
  );
}
