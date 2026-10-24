"use client";

import { useEffect, useState } from "react";
import {
  CheckIcon,
  CopyIcon,
  FlameIcon,
  HistoryIcon,
  Loader2Icon,
  RefreshCwIcon,
  SaveIcon,
  SparklesIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  useActivateStyleProfile,
  useActiveStyleProfile,
  useGenerateStyleProfile,
  useStyleProfiles,
  useUpdateStyleProfile,
} from "../hooks/use-style";
import type { TStyleProfile } from "../types";

export function StyleProfileCard() {
  const { data: activeProfile, isLoading: isActLoading } = useActiveStyleProfile();
  const { data: profiles, isLoading: isListLoading } = useStyleProfiles();
  const generateMutation = useGenerateStyleProfile();
  const updateMutation = useUpdateStyleProfile();
  const activateMutation = useActivateStyleProfile();

  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [markdownEdit, setMarkdownEdit] = useState("");
  const [jsonEdit, setJsonEdit] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);

  // Sync state when active profile loads or changes
  const currentProfile: TStyleProfile | undefined =
    profiles?.find((p) => p.id === selectedProfileId) || activeProfile;

  useEffect(() => {
    if (activeProfile && !selectedProfileId) {
      if (activeProfile.id) {
        setSelectedProfileId(activeProfile.id);
      }
    }
  }, [activeProfile, selectedProfileId]);

  useEffect(() => {
    if (currentProfile) {
      setMarkdownEdit(currentProfile.markdown_content || "");
      try {
        setJsonEdit(JSON.stringify(currentProfile.profile_data || {}, null, 2));
        setJsonError(null);
      } catch {
        setJsonEdit("{}");
      }
    }
  }, [currentProfile]);

  const handleJsonChange = (val: string) => {
    setJsonEdit(val);
    try {
      JSON.parse(val);
      setJsonError(null);
    } catch (e: any) {
      setJsonError(e.message);
    }
  };

  const handleSave = async () => {
    if (!currentProfile || !currentProfile.id) return;

    let parsedData = currentProfile.profile_data;
    if (!jsonError) {
      try {
        parsedData = JSON.parse(jsonEdit);
      } catch {}
    }

    await updateMutation.mutateAsync({
      profileId: currentProfile.id,
      payload: {
        name: currentProfile.name,
        markdown_content: markdownEdit,
        profile_data: parsedData,
      },
    });
  };

  const handleActivate = async () => {
    if (!currentProfile || !currentProfile.id) return;
    await activateMutation.mutateAsync(currentProfile.id);
  };

  const handleGenerate = async () => {
    await generateMutation.mutateAsync();
  };

  if (isActLoading || isListLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const pData = currentProfile?.profile_data || {};

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold tracking-tight">Style Profile</h2>
            {currentProfile?.is_active && (
              <Badge variant="default" className="gap-1 bg-emerald-600 hover:bg-emerald-700">
                <CheckIcon className="h-3 w-3" /> Active Profile
              </Badge>
            )}
            <Badge variant="outline">
              {currentProfile?.source === "learned_profile"
                ? `Version ${currentProfile.version}`
                : currentProfile?.source === "seed"
                ? "Default Seed Guide"
                : "Manual Settings Guide"}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Defines the voice, tone, structural conventions, and guidelines injected into drafting prompts.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {profiles && profiles.length > 1 && (
            <Select
              value={currentProfile?.id || ""}
              onValueChange={(val) => setSelectedProfileId(val)}
            >
              <SelectTrigger className="w-[180px] h-9">
                <SelectValue placeholder="Switch version" />
              </SelectTrigger>
              <SelectContent>
                {profiles.map((p) => (
                  <SelectItem key={p.id || "default"} value={p.id || ""}>
                    v{p.version} - {p.name} {p.is_active ? "(Active)" : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {currentProfile && !currentProfile.is_active && currentProfile.id && (
            <Button
              variant="secondary"
              size="sm"
              onClick={handleActivate}
              disabled={activateMutation.isPending}
            >
              Set as Active
            </Button>
          )}

          <Button
            onClick={handleGenerate}
            disabled={generateMutation.isPending}
            className="gap-2"
          >
            {generateMutation.isPending ? (
              <Loader2Icon className="h-4 w-4 animate-spin" />
            ) : (
              <SparklesIcon className="h-4 w-4" />
            )}
            {generateMutation.isPending ? "Analyzing Samples…" : "Generate from Samples"}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-3 max-w-[420px]">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="markdown">Markdown Prompt</TabsTrigger>
          <TabsTrigger value="json">Structured Data</TabsTrigger>
        </TabsList>

        {/* Tab 1: Structured Overview */}
        <TabsContent value="overview" className="space-y-4 pt-2">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                  Voice & Tone
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <span className="text-xs font-semibold text-muted-foreground uppercase">Tone</span>
                  <p className="text-sm font-medium mt-0.5">{pData.tone || "Direct, authoritative, practical"}</p>
                </div>
                <div>
                  <span className="text-xs font-semibold text-muted-foreground uppercase">Voice</span>
                  <p className="text-sm font-medium mt-0.5">{pData.voice || "First-person plural ('we build', 'we contrast')"}</p>
                </div>
                <div>
                  <span className="text-xs font-semibold text-muted-foreground uppercase">Heading Conventions</span>
                  <p className="text-sm mt-0.5">{pData.heading_conventions || "Action-oriented headings without numbering"}</p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                  Key Guidelines (Do's & Don'ts)
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase">Recommended (Do)</span>
                  <ul className="text-xs space-y-1 mt-1 text-muted-foreground">
                    {(pData.do || [
                      "Anchor each claim in extracted research evidence",
                      "Provide complete, runnable code blocks with imports",
                      "Use comparison tables when contrasting alternatives",
                    ]).map((item: string, i: number) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <span className="text-emerald-500 font-bold">✓</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <span className="text-xs font-semibold text-rose-600 dark:text-rose-400 uppercase">Anti-Patterns (Don't)</span>
                  <ul className="text-xs space-y-1 mt-1 text-muted-foreground">
                    {(pData.dont || [
                      "Never invent benchmark numbers or library versions",
                      "Do not copy sentences verbatim from reference samples",
                      "Avoid vague filler transitions like 'In this modern fast-paced world'",
                    ]).map((item: string, i: number) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <span className="text-rose-500 font-bold">✕</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </CardContent>
            </Card>
          </div>

          {pData.structure_patterns && Object.keys(pData.structure_patterns).length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                  Structure Patterns
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 sm:grid-cols-2">
                  {Object.entries(pData.structure_patterns).map(([fmt, pattern]) => (
                    <div key={fmt} className="rounded-md border p-3">
                      <span className="text-xs font-semibold uppercase text-primary">{fmt}</span>
                      <p className="text-xs text-muted-foreground mt-1">{String(pattern)}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Tab 2: Markdown Guide */}
        <TabsContent value="markdown" className="space-y-4 pt-2">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Active Prompt Markdown</CardTitle>
              <CardDescription>
                This exact text is injected into the <code className="text-xs">&lt;style_guide&gt;</code> block of outlining and drafting prompts.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Textarea
                rows={16}
                value={markdownEdit}
                onChange={(e) => setMarkdownEdit(e.target.value)}
                className="font-mono text-xs leading-relaxed"
                placeholder="# Style Profile\n\n..."
              />
            </CardContent>
            {currentProfile?.id && (
              <CardFooter className="flex justify-end gap-2 border-t pt-3">
                <Button
                  onClick={handleSave}
                  disabled={updateMutation.isPending}
                  size="sm"
                  className="gap-2"
                >
                  {updateMutation.isPending ? (
                    <Loader2Icon className="h-4 w-4 animate-spin" />
                  ) : (
                    <SaveIcon className="h-4 w-4" />
                  )}
                  Save Changes
                </Button>
              </CardFooter>
            )}
          </Card>
        </TabsContent>

        {/* Tab 3: Structured JSON */}
        <TabsContent value="json" className="space-y-4 pt-2">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Structured JSON Representation</CardTitle>
              <CardDescription>
                Modify individual attributes such as tone, explanation devices, and signature phrases.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Textarea
                rows={16}
                value={jsonEdit}
                onChange={(e) => handleJsonChange(e.target.value)}
                className="font-mono text-xs leading-relaxed"
              />
              {jsonError && (
                <p className="text-xs text-destructive mt-2">Invalid JSON: {jsonError}</p>
              )}
            </CardContent>
            {currentProfile?.id && (
              <CardFooter className="flex justify-end gap-2 border-t pt-3">
                <Button
                  onClick={handleSave}
                  disabled={updateMutation.isPending || !!jsonError}
                  size="sm"
                  className="gap-2"
                >
                  {updateMutation.isPending ? (
                    <Loader2Icon className="h-4 w-4 animate-spin" />
                  ) : (
                    <SaveIcon className="h-4 w-4" />
                  )}
                  Save Changes
                </Button>
              </CardFooter>
            )}
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
