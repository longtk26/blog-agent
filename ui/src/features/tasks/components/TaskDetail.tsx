"use client";

import { Container } from "@/components/layout/Container";
import { PageHeader } from "@/components/layout/PageHeader";
import { Stack } from "@/components/layout/Stack";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useTaskDetail } from "../hooks/use-task-detail";
import { ResearchBriefView } from "./ResearchBriefView";
import { ResearchPlanCard } from "./ResearchPlanCard";
import { SourcesPanel } from "./SourcesPanel";
import { TaskActions } from "./TaskActions";
import { TaskSidebar } from "./TaskSidebar";
import { TaskStatusBadge } from "./TaskStatusBadge";
import { TaskTimeline } from "./TaskTimeline";

export function TaskDetail() {
  const { id, task, error, isPending, events, connected, hasBrief } = useTaskDetail();

  if (isPending) {
    return (
      <Container>
        <Skeleton className="h-96" />
      </Container>
    );
  }
  if (error || !task) {
    return (
      <Container>
        <PageHeader title="Task not found" description={error?.message} />
      </Container>
    );
  }

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={task.topic}
          description={`Task ${task.id.slice(0, 8)}`}
          actions={
            <div className="flex flex-wrap items-center gap-3">
              <TaskStatusBadge status={task.status} running={task.is_running} />
              <TaskActions task={task} />
            </div>
          }
        />
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Tabs defaultValue="activity">
            <TabsList>
              <TabsTrigger value="activity">Activity</TabsTrigger>
              <TabsTrigger value="plan">Plan</TabsTrigger>
              <TabsTrigger value="sources">Sources ({task.progress.sources_found})</TabsTrigger>
              <TabsTrigger value="brief" disabled={!hasBrief}>
                Brief
              </TabsTrigger>
            </TabsList>
            <Card className="mt-3">
              <CardContent>
                <TabsContent value="activity">
                  <TaskTimeline events={events} connected={connected} />
                </TabsContent>
                <TabsContent value="plan">
                  <ResearchPlanCard plan={task.research_plan} openQuestions={task.open_questions} />
                </TabsContent>
                <TabsContent value="sources">
                  <SourcesPanel taskId={id} />
                </TabsContent>
                <TabsContent value="brief">
                  <ResearchBriefView taskId={id} enabled={hasBrief} />
                </TabsContent>
              </CardContent>
            </Card>
          </Tabs>
          <TaskSidebar task={task} />
        </div>
      </Stack>
    </Container>
  );
}
