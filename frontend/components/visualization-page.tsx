"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Gauge, Play, SkipBack, SkipForward, Pause } from "lucide-react";

import {
  useAsset,
  useAssetEpisode,
  useAssetEpisodes,
  useEpisodeViewerSource,
} from "@/hooks/use-backend";
import { BackendApiError, getErrorMessage } from "@/lib/api";
import { formatDateTime, formatDuration } from "@/lib/format";
import { resolveReturnHref } from "@/lib/navigation";
import { buildVisualizeHref } from "@/lib/visualization";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";

function VisualizationShellSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-28" />
      <Skeleton className="h-28 rounded-xl" />
      <Skeleton className="h-16 rounded-xl" />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Skeleton className="h-[360px] rounded-xl" />
        <Skeleton className="h-[360px] rounded-xl" />
      </div>
    </div>
  );
}

export function VisualizationPageFallback() {
  return <VisualizationShellSkeleton />;
}

export function VisualizationPage() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();

  const assetId = searchParams.get("asset_id")?.trim() ?? "";
  const selectedEpisodeId = searchParams.get("episode_id")?.trim() ?? "";
  const returnHref = resolveReturnHref(searchParams.get("from"), "/");

  const assetResponse = useAsset(assetId);
  const episodesResponse = useAssetEpisodes(assetId);

  const episodes = episodesResponse.data ?? [];
  const resolvedEpisodeId = selectedEpisodeId || (episodes.length === 1 ? episodes[0].episode_id : "");

  const episodeResponse = useAssetEpisode(assetId, resolvedEpisodeId);
  const viewerSourceResponse = useEpisodeViewerSource(assetId, resolvedEpisodeId);

  const currentHref = React.useMemo(() => {
    const query = searchParams.toString();
    return query ? `${pathname}?${query}` : pathname;
  }, [pathname, searchParams]);

  function onSelectEpisode(nextEpisodeId: string) {
    if (!assetId || !nextEpisodeId) {
      return;
    }

    const nextHref = buildVisualizeHref({
      assetId,
      episodeId: nextEpisodeId,
      from: returnHref,
    });

    React.startTransition(() => {
      router.replace(nextHref, { scroll: false });
    });
  }

  if (!assetId) {
    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <Alert variant="destructive">
          <AlertTitle>Missing asset</AlertTitle>
          <AlertDescription>Open visualization from inventory or asset detail so an asset ID is provided.</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (assetResponse.isLoading || episodesResponse.isLoading) {
    return <VisualizationShellSkeleton />;
  }

  if (assetResponse.error || episodesResponse.error) {
    const error = assetResponse.error ?? episodesResponse.error;
    const isNotFound = error instanceof BackendApiError && error.status === 404;

    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <Alert variant="destructive">
          <AlertTitle>{isNotFound ? "Visualization data not found" : "Could not load visualization"}</AlertTitle>
          <AlertDescription>{getErrorMessage(error)}</AlertDescription>
        </Alert>
      </div>
    );
  }

  const assetDetail = assetResponse.data;
  if (!assetDetail) {
    return null;
  }

  if (episodes.length === 0) {
    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <Alert>
          <AlertTitle>No episodes available</AlertTitle>
          <AlertDescription>
            This asset does not expose episode data yet. Run indexing or visualization preparation jobs and try again.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const selectedEpisode = episodes.find((episode) => episode.episode_id === resolvedEpisodeId) ?? null;
  const hasVisualizableData =
    (episodeResponse.data?.has_visualizable_streams ?? selectedEpisode?.has_visualizable_streams) !== false;

  return (
    <div className="space-y-6">
      <Button asChild size="sm" variant="ghost">
        <Link href={returnHref}>
          <ArrowLeft className="size-4" />
          Back
        </Link>
      </Button>

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <CardTitle className="text-xl">Visualization</CardTitle>
            <CardDescription>{assetDetail.asset.file_name}</CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">Asset {assetId}</Badge>
            {selectedEpisode ? <Badge variant="secondary">Episode {selectedEpisode.label}</Badge> : null}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Duration</dt>
              <dd className="text-sm font-medium">{formatDuration(selectedEpisode?.duration)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Start</dt>
              <dd className="text-sm font-medium">{formatDateTime(selectedEpisode?.start_time)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">End</dt>
              <dd className="text-sm font-medium">{formatDateTime(selectedEpisode?.end_time)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Lane count</dt>
              <dd className="text-sm font-medium">{selectedEpisode?.default_lane_count ?? "Not available"}</dd>
            </div>
          </dl>

          {episodes.length > 1 && !selectedEpisode ? (
            <Alert>
              <AlertTitle>Select an episode</AlertTitle>
              <AlertDescription>
                This asset has multiple episodes. Choose one to load the visualization shell.
              </AlertDescription>
            </Alert>
          ) : null}

          {episodes.length > 1 ? (
            <div className="max-w-sm space-y-2">
              <label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="episode-picker">
                Episode
              </label>
              <NativeSelect
                id="episode-picker"
                onChange={(event) => onSelectEpisode(event.target.value)}
                value={resolvedEpisodeId}
              >
                <option value="">Select episode</option>
                {episodes.map((episode) => (
                  <option key={episode.episode_id} value={episode.episode_id}>
                    {episode.label}
                  </option>
                ))}
              </NativeSelect>
            </div>
          ) : null}

          {!hasVisualizableData ? (
            <Alert>
              <AlertTitle>Episode has no supported visualizable data</AlertTitle>
              <AlertDescription>
                This episode is available but does not currently expose streams supported by the visualization viewer.
              </AlertDescription>
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Gauge className="size-4" />
            Transport controls
          </CardTitle>
          <CardDescription>Phase 8A shell with controls scaffolded for phase 8B behavior.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2">
          <Button disabled size="sm" type="button" variant="outline">
            <SkipBack className="size-3.5" />
            Start
          </Button>
          <Button disabled size="sm" type="button" variant="outline">
            <Play className="size-3.5" />
            Play
          </Button>
          <Button disabled size="sm" type="button" variant="outline">
            <Pause className="size-3.5" />
            Pause
          </Button>
          <Button disabled size="sm" type="button" variant="outline">
            <SkipForward className="size-3.5" />
            End
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Viewer panel</CardTitle>
            <CardDescription>Official Rerun embedding arrives in phase 8C.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {!resolvedEpisodeId ? (
              <Alert>
                <AlertTitle>Viewer is waiting for an episode</AlertTitle>
                <AlertDescription>Select an episode to load viewer-source status.</AlertDescription>
              </Alert>
            ) : viewerSourceResponse.isLoading ? (
              <Skeleton className="h-24 rounded-lg" />
            ) : viewerSourceResponse.error ? (
              <Alert variant="destructive">
                <AlertTitle>Could not load viewer source</AlertTitle>
                <AlertDescription>{getErrorMessage(viewerSourceResponse.error)}</AlertDescription>
              </Alert>
            ) : (
              <Alert>
                <AlertTitle>Viewer source status: {viewerSourceResponse.data?.status ?? "missing"}</AlertTitle>
                <AlertDescription>
                  {viewerSourceResponse.data?.source_url
                    ? `Source URL ready: ${viewerSourceResponse.data.source_url}`
                    : viewerSourceResponse.data?.detail ?? "Viewer source is not ready yet."}
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Inspector panel</CardTitle>
            <CardDescription>Topic and sample inspector scaffolding for phase 8B.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>Current route: {currentHref}</p>
            <p>
              Episode detail status:{" "}
              {resolvedEpisodeId
                ? episodeResponse.isLoading
                  ? "Loading"
                  : episodeResponse.error
                    ? "Error"
                    : "Ready"
                : "No episode selected"}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
