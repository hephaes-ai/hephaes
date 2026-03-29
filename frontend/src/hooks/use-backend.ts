"use client"

import * as React from "react"
import useSWR, { useSWRConfig } from "swr"

import {
  BackendApiError,
  getConversionAuthoringCapabilities,
  getDashboardBlockers,
  getDashboardSummary,
  getDashboardTrends,
  getConversion,
  getAssetDetail,
  getHealth,
  getJob,
  getConversionConfig,
  getOutput,
  listConversionConfigs,
  listConversions,
  listAssets,
  listJobs,
  listOutputs,
  listTags,
  serializeAssetListQuery,
  serializeOutputsQuery,
  type OutputsQuery,
  type AssetListQuery,
} from "@/lib/api"

export const backendKeys = {
  asset: (assetId: string) => ["asset", assetId] as const,
  assets: (query?: AssetListQuery | null) =>
    ["assets", serializeAssetListQuery(query)] as const,
  conversion: (conversionId: string) => ["conversion", conversionId] as const,
  conversionAuthoringCapabilities: ["conversion-authoring", "capabilities"] as const,
  conversions: ["conversions"] as const,
  dashboardBlockers: ["dashboard", "blockers"] as const,
  dashboardSummary: ["dashboard", "summary"] as const,
  dashboardTrends: (days = 7) => ["dashboard", "trends", days] as const,
  health: ["health"] as const,
  job: (jobId: string) => ["job", jobId] as const,
  jobs: ["jobs"] as const,
  output: (outputId: string) => ["output", outputId] as const,
  outputs: (query?: OutputsQuery | null) =>
    ["outputs", serializeOutputsQuery(query)] as const,
  savedConfig: (configId: string) => ["conversion-config", configId] as const,
  savedConfigs: ["conversion-configs"] as const,
  tags: ["tags"] as const,
}

type JobsHookOptions = {
  refreshInterval?: number
}

const JOBS_ERROR_RETRY_COUNT = 2
const JOBS_ERROR_RETRY_INTERVAL_MS = 500

function shouldRetryBackendReadError(error: unknown) {
  if (error instanceof Error && error.name === "AbortError") {
    return false
  }

  if (error instanceof BackendApiError) {
    return error.status >= 500
  }

  return true
}

export function useHealth() {
  return useSWR(backendKeys.health, () => getHealth(), {
    dedupingInterval: 10_000,
    errorRetryCount: 1,
    refreshInterval: 30_000,
  })
}

export function useAssets(query?: AssetListQuery | null) {
  return useSWR(query === null ? null : backendKeys.assets(query), () =>
    listAssets(query)
  )
}

export function useDashboardBlockers() {
  return useSWR(backendKeys.dashboardBlockers, () => getDashboardBlockers())
}

export function useDashboardSummary() {
  return useSWR(backendKeys.dashboardSummary, () => getDashboardSummary())
}

export function useDashboardTrends(days = 7) {
  return useSWR(backendKeys.dashboardTrends(days), () => getDashboardTrends(days))
}

export function useAsset(assetId: string) {
  return useSWR(assetId ? backendKeys.asset(assetId) : null, () =>
    getAssetDetail(assetId)
  )
}

export function useConversions() {
  return useSWR(backendKeys.conversions, () => listConversions())
}

export function useConversion(conversionId: string) {
  return useSWR(
    conversionId ? backendKeys.conversion(conversionId) : null,
    () => getConversion(conversionId)
  )
}

export function useConversionAuthoringCapabilities() {
  return useSWR(
    backendKeys.conversionAuthoringCapabilities,
    () => getConversionAuthoringCapabilities(),
    {
      dedupingInterval: 60_000,
    }
  )
}

export function useSavedConversionConfigs() {
  return useSWR(backendKeys.savedConfigs, () => listConversionConfigs())
}

export function useSavedConversionConfig(configId: string) {
  return useSWR(
    configId ? backendKeys.savedConfig(configId) : null,
    () => getConversionConfig(configId)
  )
}

export function useOutputs(query?: OutputsQuery | null) {
  return useSWR(query === null ? null : backendKeys.outputs(query), () =>
    listOutputs(query)
  )
}

export function useOutput(outputId: string) {
  return useSWR(outputId ? backendKeys.output(outputId) : null, () =>
    getOutput(outputId)
  )
}

export function useJobs(options?: JobsHookOptions) {
  return useSWR(backendKeys.jobs, () => listJobs(), {
    errorRetryCount: JOBS_ERROR_RETRY_COUNT,
    errorRetryInterval: JOBS_ERROR_RETRY_INTERVAL_MS,
    refreshInterval: options?.refreshInterval,
    shouldRetryOnError: shouldRetryBackendReadError,
  })
}

export function useJob(jobId: string) {
  return useSWR(jobId ? backendKeys.job(jobId) : null, () => getJob(jobId))
}

export function useTags() {
  return useSWR(backendKeys.tags, () => listTags())
}

export function useBackendCache() {
  const { mutate } = useSWRConfig()

  const revalidateAssetLists = React.useCallback(async () => {
    await mutate(
      (key) => Array.isArray(key) && key[0] === "assets",
      undefined,
      {
        revalidate: true,
      }
    )
  }, [mutate])

  const revalidateAssetDetail = React.useCallback(
    async (assetId: string) => {
      if (!assetId) {
        return
      }

      await mutate(backendKeys.asset(assetId))
    },
    [mutate]
  )

  const revalidateAssetEverywhere = React.useCallback(
    async (assetId: string) => {
      await Promise.all([
        revalidateAssetLists(),
        revalidateAssetDetail(assetId),
      ])
    },
    [revalidateAssetDetail, revalidateAssetLists]
  )

  const revalidateTags = React.useCallback(async () => {
    await mutate(backendKeys.tags)
  }, [mutate])

  const revalidateConversions = React.useCallback(async () => {
    await mutate(backendKeys.conversions)
  }, [mutate])

  const revalidateSavedConfigs = React.useCallback(async () => {
    await mutate(backendKeys.savedConfigs)
  }, [mutate])

  const revalidateSavedConfigDetail = React.useCallback(
    async (configId: string) => {
      if (!configId) {
        return
      }

      await mutate(backendKeys.savedConfig(configId))
    },
    [mutate]
  )

  const revalidateOutputs = React.useCallback(async () => {
    await mutate(
      (key) => Array.isArray(key) && key[0] === "outputs",
      undefined,
      {
        revalidate: true,
      }
    )
  }, [mutate])

  const revalidateJobs = React.useCallback(async () => {
    await mutate(backendKeys.jobs)
  }, [mutate])

  const revalidateJobDetail = React.useCallback(
    async (jobId: string) => {
      if (!jobId) {
        return
      }

      await mutate(backendKeys.job(jobId))
    },
    [mutate]
  )

  const revalidateConversionDetail = React.useCallback(
    async (conversionId: string) => {
      if (!conversionId) {
        return
      }

      await mutate(backendKeys.conversion(conversionId))
    },
    [mutate]
  )

  const revalidateOutputDetail = React.useCallback(
    async (outputId: string) => {
      if (!outputId) {
        return
      }

      await Promise.all([
        mutate(backendKeys.output(outputId), undefined, { revalidate: true }),
        mutate((key) => Array.isArray(key) && key[0] === "outputs", undefined, {
          revalidate: true,
        }),
      ])
    },
    [mutate]
  )

  return {
    revalidateAssetDetail,
    revalidateAssetEverywhere,
    revalidateAssetLists,
    revalidateConversionDetail,
    revalidateConversions,
    revalidateJobDetail,
    revalidateJobs,
    revalidateOutputDetail,
    revalidateOutputs,
    revalidateSavedConfigDetail,
    revalidateSavedConfigs,
    revalidateTags,
  }
}
