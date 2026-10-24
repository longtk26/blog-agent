"use client";

import { useState } from "react";
import {
  BookOpenIcon,
  GlobeIcon,
  Link2OffIcon,
  Loader2Icon,
  PencilIcon,
  PlusIcon,
  SparklesIcon,
  Trash2Icon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  useCreateOwnerNote,
  useDeleteOwnerNote,
  useOwnerNotes,
  useUpdateOwnerNote,
} from "../hooks/use-style";
import type { TOwnerNote } from "../types";

export function OwnerNotesManager() {
  const { data: notes, isLoading } = useOwnerNotes();
  const createMutation = useCreateOwnerNote();
  const updateMutation = useUpdateOwnerNote();
  const deleteMutation = useDeleteOwnerNote();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingNote, setEditingNote] = useState<TOwnerNote | null>(null);

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [citableUrl, setCitableUrl] = useState("");
  const [qualityScore, setQualityScore] = useState("1.0");

  const openCreateDialog = () => {
    setEditingNote(null);
    setTitle("");
    setContent("");
    setCitableUrl("");
    setQualityScore("1.0");
    setDialogOpen(true);
  };

  const openEditDialog = (note: TOwnerNote) => {
    setEditingNote(note);
    setTitle(note.title);
    setContent(note.content);
    setCitableUrl(note.citable_url || "");
    setQualityScore(String(note.quality_score));
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!title.trim() || !content.trim()) return;

    const payload = {
      title: title.trim(),
      content: content.trim(),
      citable_url: citableUrl.trim() || null,
      quality_score: Math.min(1.0, Math.max(0.0, parseFloat(qualityScore) || 1.0)),
    };

    if (editingNote) {
      await updateMutation.mutateAsync({ noteId: editingNote.id, input: payload });
    } else {
      await createMutation.mutateAsync(payload);
    }
    setDialogOpen(false);
  };

  const isSaving = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Owner Knowledge Base</h2>
          <p className="text-sm text-muted-foreground">
            Personal notes, benchmarks, and internal guidelines. Automatically chunked and retrieved as primary evidence during research.
          </p>
        </div>
        <Button onClick={openCreateDialog} className="gap-2">
          <PlusIcon className="h-4 w-4" />
          Add Note
        </Button>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editingNote ? "Edit Note" : "Create Owner Note"}</DialogTitle>
            <DialogDescription>
              Owner notes are embedded into pgvector and queried by research agents. Notes without a citable URL are used as internal guidance and never cited publicly.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <label htmlFor="note-title" className="text-xs font-semibold text-muted-foreground uppercase">
                Title
              </label>
              <Input
                id="note-title"
                placeholder="e.g. In-house vLLM Throughput Benchmarks"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="mt-1"
              />
            </div>

            <div>
              <label htmlFor="note-content" className="text-xs font-semibold text-muted-foreground uppercase">
                Content (Markdown supported)
              </label>
              <Textarea
                id="note-content"
                rows={8}
                placeholder="## Findings\n\nWe measured 450 tokens/sec across 4x A100 GPUs with paged attention enabled..."
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="mt-1 font-mono text-xs"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="note-url" className="text-xs font-semibold text-muted-foreground uppercase">
                  Citable URL (Optional)
                </label>
                <Input
                  id="note-url"
                  placeholder="https://docs.mycompany.com/..."
                  value={citableUrl}
                  onChange={(e) => setCitableUrl(e.target.value)}
                  className="mt-1"
                />
                <span className="block text-xs text-muted-foreground mt-1">
                  Leave blank to keep note strictly internal.
                </span>
              </div>

              <div>
                <label htmlFor="note-quality" className="text-xs font-semibold text-muted-foreground uppercase">
                  Quality Score (0.0 to 1.0)
                </label>
                <Input
                  id="note-quality"
                  type="number"
                  step="0.1"
                  min="0.0"
                  max="1.0"
                  value={qualityScore}
                  onChange={(e) => setQualityScore(e.target.value)}
                  className="mt-1"
                />
                <span className="block text-xs text-muted-foreground mt-1">
                  Higher scores prioritize this evidence in research.
                </span>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!title.trim() || !content.trim() || isSaving}
              className="gap-2"
            >
              {isSaving && <Loader2Icon className="h-4 w-4 animate-spin" />}
              {editingNote ? "Save Changes" : "Create Note"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : !notes || notes.length === 0 ? (
        <Card className="text-center py-12">
          <CardContent className="flex flex-col items-center justify-center">
            <BookOpenIcon className="h-12 w-12 text-muted-foreground/40 mb-3" />
            <h3 className="text-base font-medium">No owner notes created yet</h3>
            <p className="text-sm text-muted-foreground max-w-md mt-1 mb-6">
              Add your own project notes, architecture decisions, or benchmark data. The research node automatically retrieves matching notes and adds them to research evidence.
            </p>
            <Button onClick={openCreateDialog} className="gap-2">
              <PlusIcon className="h-4 w-4" />
              Add First Note
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {notes.map((note) => (
            <Card key={note.id} className="flex flex-col justify-between">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base line-clamp-1">{note.title}</CardTitle>
                  <Badge variant="outline" className="text-xs shrink-0">
                    Quality {note.quality_score.toFixed(1)}
                  </Badge>
                </div>
                <div className="flex items-center gap-1.5 mt-1">
                  {note.citable_url ? (
                    <Badge variant="secondary" className="gap-1 text-xs font-normal">
                      <GlobeIcon className="h-3 w-3 text-emerald-500" /> Citable
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="gap-1 text-xs font-normal text-muted-foreground">
                      <Link2OffIcon className="h-3 w-3" /> Internal only
                    </Badge>
                  )}
                  {note.updated_at && (
                    <span className="text-xs text-muted-foreground ml-auto">
                      {new Date(note.updated_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </CardHeader>
              <CardContent className="pb-3">
                <p className="text-xs text-muted-foreground line-clamp-4 font-mono leading-relaxed bg-muted/40 p-2.5 rounded">
                  {note.content}
                </p>
              </CardContent>
              <CardFooter className="flex justify-end gap-1 border-t pt-2.5">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => openEditDialog(note)}
                  className="gap-1 h-8 text-xs"
                >
                  <PencilIcon className="h-3.5 w-3.5" /> Edit
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    if (confirm(`Delete note "${note.title}"?`)) {
                      deleteMutation.mutate(note.id);
                    }
                  }}
                  disabled={deleteMutation.isPending}
                  className="gap-1 h-8 text-xs text-muted-foreground hover:text-destructive"
                >
                  <Trash2Icon className="h-3.5 w-3.5" /> Delete
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
