"use client";

import { DownloadIcon, ExternalLinkIcon, RefreshCwIcon, ShuffleIcon, UploadIcon, ZoomInIcon } from "lucide-react";
import React, { useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { useDiagrams } from "../hooks/use-diagrams";
import type { TDiagramAsset } from "../types";

type DiagramsPanelProps = {
  taskId: string;
  canEdit: boolean;
};

export function DiagramsPanel({ taskId, canEdit }: DiagramsPanelProps) {
  const {
    diagrams,
    isLoading,
    switchFormat,
    isSwitching,
    upload,
    isUploading,
    regenerate,
    isRegenerating,
  } = useDiagrams(taskId);

  const [activeRegenSlot, setActiveRegenSlot] = useState<string | null>(null);
  const [feedbackText, setFeedbackText] = useState("");
  const [zoomAsset, setZoomAsset] = useState<TDiagramAsset | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadSlot, setUploadSlot] = useState<string | null>(null);

  const handleOpenUpload = (slotId: string) => {
    setUploadSlot(slotId);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
      fileInputRef.current.click();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && uploadSlot) {
      upload({ slotId: uploadSlot, file });
    }
  };

  const handleConfirmRegenerate = () => {
    if (!activeRegenSlot) return;
    regenerate({ slotId: activeRegenSlot, feedback: feedbackText });
    setActiveRegenSlot(null);
    setFeedbackText("");
  };

  if (isLoading) {
    return (
      <div className="space-y-4 py-4 text-center text-sm text-muted-foreground">
        <RefreshCwIcon className="mx-auto h-5 w-5 animate-spin text-muted-foreground/60" />
        <p>Loading diagrams...</p>
      </div>
    );
  }

  if (diagrams.length === 0) {
    return (
      <div className="space-y-3 py-6 text-center text-sm text-muted-foreground">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted">
          <ShuffleIcon className="h-6 w-6 text-muted-foreground/60" />
        </div>
        <p className="font-medium text-foreground">No diagrams generated</p>
        <p className="text-xs">
          Diagrams are created automatically when &quot;Include Diagram&quot; is enabled on task creation or requested in
          article outline sections.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <input
        ref={fileInputRef}
        type="file"
        accept=".drawio,.xml,.svg"
        className="hidden"
        onChange={handleFileChange}
      />

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{diagrams.length} diagram{diagrams.length > 1 ? "s" : ""}</span>
        <a
          href="https://app.diagrams.net"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-primary hover:underline"
        >
          <span>Open diagrams.net</span>
          <ExternalLinkIcon className="h-3 w-3" />
        </a>
      </div>

      <div className="space-y-4">
        {diagrams.map((d) => {
          const spec = d.spec || {};
          const nodeCount = spec.nodes?.length ?? (spec.participants?.length ?? 0);
          const edgeCount = spec.edges?.length ?? (spec.messages?.length ?? 0);
          const title = spec.title || d.slot_id;
          const svgUrl = `/api/agent/assets/${d.id}?type=svg`;
          const sourceUrl = `/api/agent/assets/${d.id}?type=source&download=1`;
          const svgDownloadUrl = `/api/agent/assets/${d.id}?type=svg&download=1`;
          const pngDownloadUrl = d.png_path ? `/api/agent/assets/${d.id}?type=png&download=1` : null;

          return (
            <Card key={d.id} className="overflow-hidden border border-border">
              <CardHeader className="p-3 pb-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <CardTitle className="truncate text-sm font-semibold">{title}</CardTitle>
                    <p className="text-xs text-muted-foreground font-mono truncate">{d.slot_id}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    <Badge variant={d.format === "drawio" ? "default" : "secondary"} className="text-[10px] uppercase">
                      {d.format}
                    </Badge>
                    <Badge
                      variant={d.validation_status === "valid" ? "outline" : "destructive"}
                      className="text-[10px]"
                    >
                      {d.validation_status}
                    </Badge>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="space-y-3 p-3 pt-0">
                {/* Thumbnail Preview */}
                <div
                  className="group relative flex h-36 w-full cursor-pointer items-center justify-center overflow-hidden rounded-md border border-border/60 bg-muted/30 p-2 transition-colors hover:border-primary/50"
                  onClick={() => setZoomAsset(d)}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={svgUrl}
                    alt={title}
                    className="max-h-full max-w-full object-contain pointer-events-none"
                    loading="lazy"
                  />
                  <div className="absolute inset-0 flex items-center justify-center bg-background/60 opacity-0 backdrop-blur-[1px] transition-opacity group-hover:opacity-100">
                    <span className="inline-flex items-center gap-1 rounded bg-background/90 px-2 py-1 text-xs font-medium shadow-sm">
                      <ZoomInIcon className="h-3.5 w-3.5" />
                      View Full
                    </span>
                  </div>
                </div>

                {/* Spec Summary */}
                <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>Type: <strong className="text-foreground capitalize">{spec.type || "diagram"}</strong></span>
                  <span>{nodeCount} nodes • {edgeCount} connections</span>
                </div>

                {/* Actions */}
                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs"
                    disabled={!canEdit || isRegenerating}
                    onClick={() => {
                      setActiveRegenSlot(d.slot_id);
                      setFeedbackText("");
                    }}
                  >
                    <RefreshCwIcon className={`mr-1 h-3 w-3 ${isRegenerating ? "animate-spin" : ""}`} />
                    Regenerate
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs"
                    disabled={!canEdit || isSwitching}
                    onClick={() =>
                      switchFormat({
                        slotId: d.slot_id,
                        targetFormat: d.format === "drawio" ? "mermaid" : "drawio",
                      })
                    }
                  >
                    <ShuffleIcon className="mr-1 h-3 w-3" />
                    To {d.format === "drawio" ? "Mermaid" : "Draw.io"}
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs"
                    disabled={!canEdit || isUploading}
                    onClick={() => handleOpenUpload(d.slot_id)}
                  >
                    <UploadIcon className="mr-1 h-3 w-3" />
                    Upload
                  </Button>

                  <div className="ml-auto flex items-center gap-1">
                    <a href={sourceUrl} download title={`Download .${d.format === "drawio" ? "drawio" : "mmd"}`}>
                      <Button variant="ghost" size="sm" className="h-7 px-2 text-xs">
                        <DownloadIcon className="h-3 w-3" />
                        <span className="ml-1 text-[10px]">{d.format === "drawio" ? ".drawio" : ".mmd"}</span>
                      </Button>
                    </a>
                    <a href={svgDownloadUrl} download title="Download .svg">
                      <Button variant="ghost" size="sm" className="h-7 px-2 text-xs">
                        <DownloadIcon className="h-3 w-3" />
                        <span className="ml-1 text-[10px]">.svg</span>
                      </Button>
                    </a>
                    {pngDownloadUrl && (
                      <a href={pngDownloadUrl} download title="Download .png">
                        <Button variant="ghost" size="sm" className="h-7 px-2 text-xs">
                          <DownloadIcon className="h-3 w-3" />
                          <span className="ml-1 text-[10px]">.png</span>
                        </Button>
                      </a>
                    )}
                  </div>
                </div>

                <p className="text-[10px] text-muted-foreground/80">
                  Tip: Download .drawio or .svg, edit locally at diagrams.net, and upload to replace.
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Regenerate Modal */}
      <Dialog open={Boolean(activeRegenSlot)} onOpenChange={(open) => !open && setActiveRegenSlot(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Regenerate Diagram</DialogTitle>
            <DialogDescription>
              Provide specific feedback to guide how this diagram should be updated. Only this diagram slot will be
              re-generated.
            </DialogDescription>
          </DialogHeader>
          <div className="py-2">
            <Textarea
              placeholder="e.g. Add an authentication service between client and database, or simplify the data pipeline steps..."
              value={feedbackText}
              onChange={(e) => setFeedbackText(e.target.value)}
              rows={4}
              className="resize-none text-xs"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setActiveRegenSlot(null)}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleConfirmRegenerate} disabled={isRegenerating}>
              {isRegenerating && <RefreshCwIcon className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              Submit Feedback
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Zoom Modal */}
      <Dialog open={Boolean(zoomAsset)} onOpenChange={(open) => !open && setZoomAsset(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>{zoomAsset?.spec?.title || zoomAsset?.slot_id}</DialogTitle>
            <DialogDescription>
              Format: {zoomAsset?.format} • Status: {zoomAsset?.validation_status}
            </DialogDescription>
          </DialogHeader>
          {zoomAsset && (
            <div className="flex max-h-[70vh] items-center justify-center overflow-auto rounded-lg border border-border bg-muted/20 p-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`/api/agent/assets/${zoomAsset.id}?type=svg`}
                alt={zoomAsset.spec?.title || zoomAsset.slot_id}
                className="max-h-[60vh] max-w-full object-contain"
              />
            </div>
          )}
          <DialogFooter className="flex items-center justify-between sm:justify-between">
            <a
              href="https://app.diagrams.net"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
            >
              <span>Edit online at diagrams.net</span>
              <ExternalLinkIcon className="h-3 w-3" />
            </a>
            <Button variant="outline" size="sm" onClick={() => setZoomAsset(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
