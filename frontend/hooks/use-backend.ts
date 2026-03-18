"use client";

import * as React from "react";
import useSWR, { useSWRConfig } from "swr";

import {
  getConversion,
  getAssetEpisode,
  getAssetDetail,
  getEpisodeSamples,
  getEpisodeTimeline,
  getEpisodeViewerSource,
  getHealth,
  getJob,
  listAssetEpisodes,
  listConversions,
  listAssets,
  listJobs,
  listTags,
  prepareEpisodeVisualization,
  serializeAssetListQuery,
  type EpisodeSamplesQuery,
  type PrepareVisualizationResponse,
  type AssetListQuery,
} from "@/lib/api";

function serializeEpisodeSamplesQuery(query: EpisodeSamplesQuery) {
  const streamIds = (query.stream_ids ?? []).map((value) => value.trim()).filter(Boolean).sort().join(",");

  return [
    `ts:${query.timestamp_ns}`,
    `before:${query.window_before_ns ?? ""}`,
    `after:${query.window_after_ns ?? ""}`,
    `streams:${streamIds}`,
  ].join("|");
}

export const backendKeys = {
  asset: (assetId: string) => ["asset", assetId] as const,
  assets: (query?: AssetListQuery | null) => ["assets", serializeAssetListQuery(query)] as const,
  conversion: (conversionId: string) => ["conversion", conversionId] as const,
  conversions: ["conversions"] as const,
  episode: (assetId: string, episodeId: string) => ["episode", assetId, episodeId] as const,
  episodes: (assetId: string) => ["episodes", assetId] as const,
  health: ["health"] as const,
  job: (jobId: string) => ["job", jobId] as const,
  jobs: ["jobs"] as const,
  samples: (assetId: string, episodeId: string, query: EpisodeSamplesQuery) =>
    ["samples", assetId, episodeId, serializeEpisodeSamplesQuery(query)] as const,
  tags: ["tags"] as const,
  timeline: (assetId: string, episodeId: string) => ["timeline", assetId, episodeId] as const,
  viewerSource: (assetId: string, episodeId: string) => ["viewer-source", assetId, episodeId] as const,
};

export function useHealth() {
  return useSWR(backendKeys.health, () => getHealth(), {
    dedupingInterval: 10_000,
    errorRetryCount: 1,
    refreshInterval: 30_000,
  });
}

export function useAssets(query?: AssetListQuery | null) {
  return useSWR(query === null ? null : backendKeys.assets(query), () => listAssets(query));
}

export function useAsset(assetId: string) {
  return useSWR(assetId ? backendKeys.asset(assetId) : null, () => getAssetDetail(assetId));
}

export function useConversions() {
  return useSWR(backendKeys.conversions, () => listConversions());
}

export function useConversion(conversionId: string) {
  return useSWR(conversionId ? backendKeys.conversion(conversionId) : null, () => getConversion(conversionId));
}

export function useJobs() {
  return useSWR(backendKeys.jobs, () => listJobs());
}

export function useJob(jobId: string) {
  return useSWR(jobId ? backendKeys.job(jobId) : null, () => getJob(jobId));
}

export function useTags() {
  return useSWR(backendKeys.tags, () => listTags());
}

export function useAssetEpisodes(assetId: string) {
  return useSWR(assetId ? backendKeys.episodes(assetId) : null, () => listAssetEpisodes(assetId));
}

export function useAssetEpisode(assetId: string, episodeId: string) {
  return useSWR(
    assetId && episodeId ? backendKeys.episode(assetId, episodeId) : null,
    () => getAssetEpisode(assetId, episodeId),
  );
}

export function useEpisodeViewerSource(assetId: string, episodeId: string) {
  return useSWR(
    assetId && episodeId ? backendKeys.viewerSource(assetId, episodeId) : null,
    () => getEpisodeViewerSource(assetId, episodeId),
  );
}

export function useEpisodeTimeline(assetId: string, episodeId: string) {
  return useSWR(
    assetId && episodeId ? backendKeys.timeline(assetId, episodeId) : null,
    () => getEpisodeTimeline(assetId, episodeId),
  );
}

export function useEpisodeSamples(assetId: string, episodeId: string, query: EpisodeSamplesQuery | null) {
  return useSWR(
    assetId && episodeId && query ? backendKeys.samples(assetId, episodeId, query) : null,
    () => getEpisodeSamples(assetId, episodeId, query as EpisodeSamplesQuery),
    {
      keepPreviousData: false,
    },
  );
}

export function usePrepareVisualization() {
  const { mutate } = useSWRConfig();
  const [isPreparing, setIsPreparing] = React.useState(false);
  const [error, setError] = React.useState<unknown>(null);

  const trigger = React.useCallback(
    async (assetId: string, episodeId: string) => {
      if (!assetId || !episodeId) {
        throw new Error("assetId and episodeId are required");
      }

      setIsPreparing(true);
      setError(null);

      try {
        const response = await prepareEpisodeVisualization(assetId, episodeId);

        await Promise.all([
          mutate(backendKeys.viewerSource(assetId, episodeId), undefined, { revalidate: true }),
          mutate((key) => Array.isArray(key) && key[0] === "jobs", undefined, { revalidate: true }),
        ]);

        if (response.job?.id) {
          await mutate(backendKeys.job(response.job.id), response.job, { revalidate: true });
        }

        return response;
      } catch (nextError) {
        setError(nextError);
        throw nextError;
      } finally {
        setIsPreparing(false);
      }
    },
    [mutate],
  );

  const reset = React.useCallback(() => {
    setError(null);
  }, []);

  return {
    error,
    isPreparing,
    reset,
    trigger,
  } as {
    error: unknown;
    isPreparing: boolean;
    reset: () => void;
    trigger: (assetId: string, episodeId: string) => Promise<PrepareVisualizationResponse>;
  };
}

export function useBackendCache() {
  const { mutate } = useSWRConfig();

  const revalidateAssetLists = React.useCallback(async () => {
    await mutate((key) => Array.isArray(key) && key[0] === "assets", undefined, {
      revalidate: true,
    });
  }, [mutate]);

  const revalidateAssetDetail = React.useCallback(
    async (assetId: string) => {
      if (!assetId) {
        return;
      }

      await mutate(backendKeys.asset(assetId));
    },
    [mutate],
  );

  const revalidateAssetEverywhere = React.useCallback(
    async (assetId: string) => {
      await Promise.all([revalidateAssetLists(), revalidateAssetDetail(assetId)]);
    },
    [revalidateAssetDetail, revalidateAssetLists],
  );

  const revalidateTags = React.useCallback(async () => {
    await mutate(backendKeys.tags);
  }, [mutate]);

  const revalidateConversions = React.useCallback(async () => {
    await mutate(backendKeys.conversions);
  }, [mutate]);

  const revalidateJobs = React.useCallback(async () => {
    await mutate(backendKeys.jobs);
  }, [mutate]);

  const revalidateJobDetail = React.useCallback(
    async (jobId: string) => {
      if (!jobId) {
        return;
      }

      await mutate(backendKeys.job(jobId));
    },
    [mutate],
  );

  const revalidateConversionDetail = React.useCallback(
    async (conversionId: string) => {
      if (!conversionId) {
        return;
      }

      await mutate(backendKeys.conversion(conversionId));
    },
    [mutate],
  );

  const revalidateAssetEpisodes = React.useCallback(
    async (assetId: string) => {
      if (!assetId) {
        return;
      }

      await mutate(backendKeys.episodes(assetId));
    },
    [mutate],
  );

  const revalidateAssetEpisodeDetail = React.useCallback(
    async (assetId: string, episodeId: string) => {
      if (!assetId || !episodeId) {
        return;
      }

      await mutate(backendKeys.episode(assetId, episodeId));
    },
    [mutate],
  );

  const revalidateEpisodeViewerSource = React.useCallback(
    async (assetId: string, episodeId: string) => {
      if (!assetId || !episodeId) {
        return;
      }

      await mutate(backendKeys.viewerSource(assetId, episodeId));
    },
    [mutate],
  );

  const revalidateEpisodeTimeline = React.useCallback(
    async (assetId: string, episodeId: string) => {
      if (!assetId || !episodeId) {
        return;
      }

      await mutate(backendKeys.timeline(assetId, episodeId));
    },
    [mutate],
  );

  const revalidateEpisodeSamples = React.useCallback(
    async (assetId: string, episodeId: string) => {
      if (!assetId || !episodeId) {
        return;
      }

      await mutate(
        (key) =>
          Array.isArray(key) &&
          key[0] === "samples" &&
          key[1] === assetId &&
          key[2] === episodeId,
        undefined,
        {
          revalidate: true,
        },
      );
    },
    [mutate],
  );

  return {
    revalidateAssetDetail,
    revalidateAssetEverywhere,
    revalidateAssetEpisodeDetail,
    revalidateAssetEpisodes,
    revalidateAssetLists,
    revalidateConversionDetail,
    revalidateConversions,
    revalidateEpisodeSamples,
    revalidateEpisodeTimeline,
    revalidateEpisodeViewerSource,
    revalidateJobDetail,
    revalidateJobs,
    revalidateTags,
  };
}
