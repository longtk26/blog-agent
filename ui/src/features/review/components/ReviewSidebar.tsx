"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { TRevision, TSource, TTask } from "@/features/tasks/types";
import { useReviewStore } from "@/store/review-store";
import type { TApproval, TPublication, TSidebarTab } from "../types";
import { ClaimsPanel } from "./ClaimsPanel";
import { DiagramsPanel } from "./DiagramsPanel";
import { IssuesPanel } from "./IssuesPanel";
import { MetadataPanel } from "./MetadataPanel";
import { PublicationPanel } from "./PublicationPanel";
import { ReviewSourcesPanel } from "./ReviewSourcesPanel";

type ReviewSidebarProps = {
  task: TTask;
  revision: TRevision;
  sources: TSource[];
  approvals: TApproval[];
  publications: TPublication[];
  canEdit: boolean;
};

export function ReviewSidebar({ task, revision, sources, approvals, publications, canEdit }: ReviewSidebarProps) {
  const tab = useReviewStore((state) => state.sidebarTab);
  const setTab = useReviewStore((state) => state.setSidebarTab);
  const draft = useReviewStore((state) => state.draft);
  const markdown = draft && draft.baseRevisionId === revision.id ? draft.markdown : revision.markdown;
  const blockers = revision.evaluations.flatMap((e) => e.issues).filter((issue) => issue.severity === "blocker").length;
  const isPublished = publications.some((p) => p.status === "published");

  return (
    <Tabs value={tab} onValueChange={(value) => setTab(value as TSidebarTab)} className="lg:sticky lg:top-16 lg:self-start">
      <TabsList className="grid w-full grid-cols-6 h-9 p-1">
        <TabsTrigger value="issues" className="px-1 text-xs">Issues{blockers ? ` (${blockers})` : ""}</TabsTrigger>
        <TabsTrigger value="claims" className="px-1 text-xs">Claims</TabsTrigger>
        <TabsTrigger value="sources" className="px-1 text-xs">Sources</TabsTrigger>
        <TabsTrigger value="metadata" className="px-1 text-xs">Metadata</TabsTrigger>
        <TabsTrigger value="diagrams" className="px-1 text-xs">Diagrams</TabsTrigger>
        <TabsTrigger value="publish" className="px-1 text-xs">Publish{isPublished ? " ✓" : ""}</TabsTrigger>
      </TabsList>
      <Card className="mt-3">
        <CardContent className="max-h-[75vh] overflow-y-auto">
          <TabsContent value="issues">
            <IssuesPanel revision={revision} />
          </TabsContent>
          <TabsContent value="claims">
            <ClaimsPanel revision={revision} sources={sources} />
          </TabsContent>
          <TabsContent value="sources">
            <ReviewSourcesPanel markdown={markdown} sources={sources} />
          </TabsContent>
          <TabsContent value="metadata">
            <MetadataPanel revision={revision} approvals={approvals} canEdit={canEdit} />
          </TabsContent>
          <TabsContent value="diagrams">
            <DiagramsPanel taskId={task.id} canEdit={canEdit} />
          </TabsContent>
          <TabsContent value="publish">
            <PublicationPanel task={task} revision={revision} publications={publications} />
          </TabsContent>
        </CardContent>
      </Card>
    </Tabs>
  );
}
