"use client";

import * as React from "react";
import useSWR, { useSWRConfig } from "swr";

import {
  createOutputAction,
  getConversion,
  getAssetEpisode,
  getAssetDetail,
  getEpisodeSamples,
  getEpisodeTimeline,
  getEpisodeViewerSource,
  getHealth,
  getJob,
  getOutputAction,
  getOutput,
  listAssetEpisodes,
  listConversions,
  listAssets,
  listJobs,
  listOutputActions,
  listOutputs,
  listTags,
  prepareEpisodeVisualization,
  serializeAssetListQuery,
  type CreateOutputActionRequest,
  type OutputActionDetail,
  type OutputDetail,
  type OutputsQuery,
  type EpisodeSamplesQuery,
  type PrepareVisualizationResponse,
  type AssetListQuery,
} from "@/lib/api";
import { filterOutputs } from "@/lib/outputs";

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
  outputAction: (actionId: string) => ["output-action", actionId] as const,
  outputActions: (outputId?: string | null) => ["output-actions", outputId ?? "all"] as const,
  output: (outputId: string) => ["output", outputId] as const,
  outputs: ["outputs"] as const,
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

export function useOutputs(query?: OutputsQuery | null) {
  const response = useSWR(backendKeys.outputs, () => listOutputs());
  const data = React.useMemo(
    () => filterOutputs(response.data, query),
    [query, response.data],
  );

  return {
    ...response,
    data,
  } as typeof response & {
    data: OutputDetail[] | undefined;
  };
}

export function useOutput(outputId: string) {
  const outputsResponse = useOutputs();
  const data = React.useMemo(
    () => outputsResponse.data?.find((output) => output.id === outputId),
    [outputId, outputsResponse.data],
  );

  return {
    ...outputsResponse,
    data: outputId ? data : undefined,
  } as typeof outputsResponse & {
    data: OutputDetail | undefined;
  };
}

export function useOutputActions(outputId?: string | null) {
  return useSWR(outputId === null ? null : backendKeys.outputActions(outputId), () =>
    listOutputActions(outputId || undefined),
  );
}

export function useOutputAction(actionId: string) {
  return useSWR(actionId ? backendKeys.outputAction(actionId) : null, () => getOutputAction(actionId));
}

export function useCreateOutputAction() {
  const { mutate } = useSWRConfig();
  const [isCreating, setIsCreating] = React.useState(false);
  const [error, setError] = React.useState<unknown>(null);

  const trigger = React.useCallback(
    async (outputId: string, payload: CreateOutputActionRequest) => {
      if (!outputId) {
        throw new Error("outputId is required");
      }

      setIsCreating(true);
      setError(null);

      try {
        const response = await createOutputAction(outputId, payload);

        await Promise.all([
          mutate(backendKeys.outputActions(outputId), undefined, { revalidate: true }),
          mutate(backendKeys.outputActions(), undefined, { revalidate: true }),
          mutate(backendKeys.outputs, undefined, { revalidate: true }),
        ]);
        await mutate(backendKeys.outputAction(response.id), response, { revalidate: false });

        return response;
      } catch (nextError) {
        setError(nextError);
        throw nextError;
      } finally {
        setIsCreating(false);
      }
    },
    [mutate],
  );

  const reset = React.useCallback(() => {
    setError(null);
  }, []);

  return {
    error,
    isCreating,
    reset,
    trigger,
  } as {
    error: unknown;
    isCreating: boolean;
    reset: () => void;
    trigger: (outputId: string, payload: CreateOutputActionRequest) => Promise<OutputActionDetail>;
  };
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

  const revalidateOutputs = React.useCallback(async () => {
    await mutate(backendKeys.outputs);
  }, [mutate]);

  const revalidateOutputActions = React.useCallback(
    async (outputId?: string) => {
      await mutate(
        (key) =>
          Array.isArray(key) &&
          key[0] === "output-actions" &&
          (outputId ? key[1] === outputId || key[1] === "all" : true),
        undefined,
        {
          revalidate: true,
        },
      );
    },
    [mutate],
  );

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

  const revalidateOutputDetail = React.useCallback(
    async (outputId: string) => {
      if (!outputId) {
        return;
      }

      try {
        const nextOutput = await getOutput(outputId);
        await mutate(backendKeys.outputs, (currentOutputs?: OutputDetail[]) => {
          if (!currentOutputs) {
            return [nextOutput];
          }

          const nextOutputs = currentOutputs.filter((output) => output.id !== outputId);
          nextOutputs.push(nextOutput);
          return nextOutputs;
        }, {
          revalidate: false,
        });
      } catch {
        await mutate(backendKeys.outputs);
      }
    },
    [mutate],
  );

  const revalidateOutputActionDetail = React.useCallback(
    async (actionId: string) => {
      if (!actionId) {
        return;
      }

      await mutate(backendKeys.outputAction(actionId));
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
    revalidateOutputDetail,
    revalidateOutputActionDetail,
    revalidateOutputActions,
    revalidateOutputs,
    revalidateTags,
  };
}
