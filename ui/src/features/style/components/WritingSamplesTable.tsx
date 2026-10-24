"use client";

import { useState } from "react";
import {
  CheckCircle2Icon,
  DownloadIcon,
  FileTextIcon,
  Loader2Icon,
  SparklesIcon,
  Trash2Icon,
  XCircleIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useDeleteSample,
  useImportSamples,
  useToggleSampleApproval,
  useWritingSamples,
} from "../hooks/use-style";

export function WritingSamplesTable() {
  const { data: samples, isLoading } = useWritingSamples();
  const importMutation = useImportSamples();
  const toggleMutation = useToggleSampleApproval();
  const deleteMutation = useDeleteSample();

  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importSanity, setImportSanity] = useState(true);
  const [importLocal, setImportLocal] = useState(true);

  const handleImport = async () => {
    const sources: string[] = [];
    if (importSanity) sources.push("sanity");
    if (importLocal) sources.push("local");
    if (sources.length === 0) return;

    await importMutation.mutateAsync(sources);
    setImportDialogOpen(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Writing Samples</h2>
          <p className="text-sm text-muted-foreground">
            Published posts imported from Sanity or local Markdown. Approved samples serve as semantic few-shot references during drafting.
          </p>
        </div>
        <Dialog open={importDialogOpen} onOpenChange={setImportDialogOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2">
              <DownloadIcon className="h-4 w-4" />
              Import Samples
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Import Writing Samples</DialogTitle>
              <DialogDescription>
                Select which sources to scan for published articles. Chunks are automatically embedded with pgvector.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              <div className="flex items-center space-x-3 rounded-md border p-3">
                <Checkbox
                  id="import-sanity"
                  checked={importSanity}
                  onCheckedChange={(checked) => setImportSanity(checked === true)}
                />
                <div className="space-y-0.5">
                  <label htmlFor="import-sanity" className="text-sm font-medium leading-none cursor-pointer">
                    Sanity Studio CMS
                  </label>
                  <p className="text-xs text-muted-foreground">
                    Imports published post documents and tags via GROQ query.
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-3 rounded-md border p-3">
                <Checkbox
                  id="import-local"
                  checked={importLocal}
                  onCheckedChange={(checked) => setImportLocal(checked === true)}
                />
                <div className="space-y-0.5">
                  <label htmlFor="import-local" className="text-sm font-medium leading-none cursor-pointer">
                    Local Repository (blogs/)
                  </label>
                  <p className="text-xs text-muted-foreground">
                    Scans local markdown articles and matches against .publish-meta.json.
                  </p>
                </div>
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setImportDialogOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleImport}
                disabled={(!importSanity && !importLocal) || importMutation.isPending}
                className="gap-2"
              >
                {importMutation.isPending && <Loader2Icon className="h-4 w-4 animate-spin" />}
                {importMutation.isPending ? "Importing & Embedding…" : "Start Import"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-3 p-6">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : !samples || samples.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <FileTextIcon className="h-12 w-12 text-muted-foreground/40 mb-3" />
              <h3 className="text-base font-medium">No writing samples imported yet</h3>
              <p className="text-sm text-muted-foreground max-w-md mt-1 mb-6">
                Import articles from Sanity or your local repository to train your personal style profile and enable semantic reference retrieval.
              </p>
              <Button onClick={() => setImportDialogOpen(true)} className="gap-2">
                <DownloadIcon className="h-4 w-4" />
                Import Samples
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[40%]">Title</TableHead>
                  <TableHead>Origin</TableHead>
                  <TableHead>Tags</TableHead>
                  <TableHead className="text-center">Chunks</TableHead>
                  <TableHead className="text-center">Use as Style Reference</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {samples.map((sample) => (
                  <TableRow key={sample.id}>
                    <TableCell className="font-medium">
                      <div>
                        <span>{sample.title}</span>
                        {sample.published_at && (
                          <span className="block text-xs text-muted-foreground mt-0.5">
                            Published {new Date(sample.published_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={sample.origin === "sanity" ? "default" : "secondary"}>
                        {sample.origin}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1 max-w-[200px]">
                        {sample.tags.slice(0, 3).map((tag) => (
                          <Badge key={tag} variant="outline" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                        {sample.tags.length > 3 && (
                          <span className="text-xs text-muted-foreground">
                            +{sample.tags.length - 3}
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <span className="font-mono text-xs text-muted-foreground">
                        {sample.chunk_count}
                      </span>
                    </TableCell>
                    <TableCell className="text-center">
                      <Button
                        variant={sample.approved_as_style_example ? "default" : "outline"}
                        size="sm"
                        onClick={() =>
                          toggleMutation.mutate({
                            sampleId: sample.id,
                            approved: !sample.approved_as_style_example,
                          })
                        }
                        disabled={toggleMutation.isPending}
                        className="gap-1.5 text-xs h-7"
                      >
                        {sample.approved_as_style_example ? (
                          <>
                            <CheckCircle2Icon className="h-3.5 w-3.5" />
                            Approved
                          </>
                        ) : (
                          <>
                            <XCircleIcon className="h-3.5 w-3.5 text-muted-foreground" />
                            Ignored
                          </>
                        )}
                      </Button>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-muted-foreground hover:text-destructive h-8 w-8"
                        onClick={() => {
                          if (confirm(`Delete sample "${sample.title}" and its embedded chunks?`)) {
                            deleteMutation.mutate(sample.id);
                          }
                        }}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2Icon className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
