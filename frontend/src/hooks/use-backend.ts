"use client"

import * as React from "react"
import useSWR, { useSWRConfig } from "swr"

import {
  BackendApiError,
  listWorkspaces,
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
  type WorkspaceRegistryListResponse,
} from "@/lib/api"
import { useActiveWorkspaceId } from "@/lib/workspace-store"

const WORKSPACE_SCOPED_SWR_OPTIONS = {
  keepPreviousData: false,
} as const

const WORKSPACE_SCOPED_KEY_PREFIXES = new Set([
  "asset",
  "assets",
  "conversion",
  "conversion-authoring",
  "conversion-config",
  "conversion-configs",
  "conversions",
  "dashboard",
  "job",
  "jobs",
  "output",
  "outputs",
  "tags",
])

function isWorkspaceScopedKey(key: unknown) {
  return (
    Array.isArray(key) &&
    typeof key[0] === "string" &&
    WORKSPACE_SCOPED_KEY_PREFIXES.has(key[0])
  )
}

function matchesWorkspaceKey(
  key: unknown,
  prefix: string,
  workspaceId: string
) {
  return Array.isArray(key) && key[0] === prefix && key[1] === workspaceId
}

export const backendKeys = {
  asset: (workspaceId: string, assetId: string) =>
    ["asset", workspaceId, assetId] as const,
  assets: (workspaceId: string, query?: AssetListQuery | null) =>
    ["assets", workspaceId, serializeAssetListQuery(query)] as const,
  conversion: (workspaceId: string, conversionId: string) =>
    ["conversion", workspaceId, conversionId] as const,
  conversionAuthoringCapabilities: (workspaceId: string) =>
    ["conversion-authoring", workspaceId, "capabilities"] as const,
  conversions: (workspaceId: string) => ["conversions", workspaceId] as const,
  dashboardBlockers: (workspaceId: string) =>
    ["dashboard", workspaceId, "blockers"] as const,
  dashboardSummary: (workspaceId: string) =>
    ["dashboard", workspaceId, "summary"] as const,
  dashboardTrends: (workspaceId: string, days = 7) =>
    ["dashboard", workspaceId, "trends", days] as const,
  health: ["health"] as const,
  job: (workspaceId: string, jobId: string) =>
    ["job", workspaceId, jobId] as const,
  jobs: (workspaceId: string) => ["jobs", workspaceId] as const,
  output: (workspaceId: string, outputId: string) =>
    ["output", workspaceId, outputId] as const,
  outputs: (workspaceId: string, query?: OutputsQuery | null) =>
    ["outputs", workspaceId, serializeOutputsQuery(query)] as const,
  savedConfig: (workspaceId: string, configId: string) =>
    ["conversion-config", workspaceId, configId] as const,
  savedConfigs: (workspaceId: string) =>
    ["conversion-configs", workspaceId] as const,
  tags: (workspaceId: string) => ["tags", workspaceId] as const,
  workspaces: ["workspaces"] as const,
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

export function useWorkspaceRegistry(enabled = true) {
  return useSWR<WorkspaceRegistryListResponse>(
    enabled ? backendKeys.workspaces : null,
    () => listWorkspaces()
  )
}

export function useHealth() {
  return useSWR(backendKeys.health, () => getHealth(), {
    dedupingInterval: 10_000,
    errorRetryCount: 1,
    refreshInterval: 30_000,
  })
}

export function useAssets(query?: AssetListQuery | null) {
  const activeWorkspaceId = useActiveWorkspaceId()

  return useSWR(
    activeWorkspaceId && query !== null
      ? backendKeys.assets(activeWorkspaceId, query)
      : null,
    () => listAssets(query),
    WORKSPACE_SCOPED_SWR_OPTIONS
  )
}

export function useDashboardBlockers() {
  const activeWorkspaceId = useActiveWorkspaceId()

  return useSWR(
    activeWorkspaceId ? backendKeys.dashboardBlockers(activeWorkspaceId) : null,
    () => getDashboardBlockers(),
    WORKSPACE_SCOPED_SWR_OPTIONS
  )
}

export function useDashboardSummary() {
  const activeWorkspaceId = useActiveWorkspaceId()

  return useSWR(
    activeWorkspaceId ? backendKeys.dashboardSummary(activeWorkspaceId) : null,
    () => getDashboardSummary(),
    WORKSPACE_SCOPED_SWR_OPTIONS
  )
}

export function useDashboardTrends(days = 7) {
  const activeWorkspaceId = useActiveWorkspaceId()

  return useSWR(
    activeWorkspaceId
      ? backendKeys.dashboardTrends(activeWorkspaceId, days)
      : null,
    () => getDashboardTrends(days),
    WORKSPACE_SCOPED_SWR_OPTIONS
  )
}

export function useAsset(assetId: string) {
  const activeWorkspaceId = useActiveWorkspaceId()

  return useSWR(
    activeWorkspaceId && assetId
      ? backendKeys.asset(activeWorkspaceId, assetId)
      : null,
    () => getAssetDetail(assetId),
    WORKSPACE_SCOPED_SWR_OPTIONS
  )
}

export function useConversions() {
  const activeWorkspaceId = useActiveWorkspaceId()

  return useSWR(
    activeWorkspaceId ? backendKeys.conversions(activeWorkspaceId) : null,
    () => listConversions(),
    WORKSPACE_SCOPED_SWR_OPTIONS
  )
}

export function useConversion(conversionId: string) {
  const activeWorkspaceId = useActiveWorkspaceId()

  return useSWR(
    activeWorkspaceId && conversionId
      ? backendKeys.conversion(activeWorkspaceId, conversionId)
      : null,
    () => getConversion(conversionId),
    WORKSPACE_SCOPED_SWR_OPTIONS
  )
}

export function useConversionAuthoringCapabilities() {
  const activeWorkspaceId = useActiveWorkspaceId()

  return useSWR(
    activeWorkspaceId
      ? backendKeys.conversionAuthoringCapabilities(activeWorkspaceId)
      : null,
    () => getConversionAuthoringCapabilities(),
    {
      dedupingInterval: 60_000,
      keepPreviousData: false,
    }
  )
}

export function useSavedConversionConfigs() {
  const activeWorkspaceId = useActiveWorkspaceId()

  return useSWR(
    activeWorkspaceId ? backendKeys.savedConfigs(activeWorkspaceId) : null,
    () => listConversionConfigs(),
    WORKSPACE_SCOPED_SWR_OPTIONS
  )
}

export function useSavedConversionConfig(configId: string) {
  const activeWorkspaceId = useActiveWorkspaceId()

  return useSWR(
    activeWorkspaceId && configId
      ? backendKeys.savedConfig(activeWorkspaceId, configId)
      : null,
    () => getConversionConfig(configId),
    WORKSPACE_SCOPED_SWR_OPTIONS
  )
}

export function useOutputs(query?: OutputsQuery | null) {
  const activeWorkspaceId = useActiveWorkspaceId()

  return useSWR(
    activeWorkspaceId && query !== null
      ? backendKeys.outputs(activeWorkspaceId, query)
      : null,
    () => listOutputs(query),
    WORKSPACE_SCOPED_SWR_OPTIONS
  )
}

export function useOutput(outputId: string) {
  const activeWorkspaceId = useActiveWorkspaceId()

  return useSWR(
    activeWorkspaceId && outputId
      ? backendKeys.output(activeWorkspaceId, outputId)
      : null,
    () => getOutput(outputId),
    WORKSPACE_SCOPED_SWR_OPTIONS
  )
}

export function useJobs(options?: JobsHookOptions) {
  const activeWorkspaceId = useActiveWorkspaceId()

  return useSWR(activeWorkspaceId ? backendKeys.jobs(activeWorkspaceId) : null, () => listJobs(), {
    errorRetryCount: JOBS_ERROR_RETRY_COUNT,
    errorRetryInterval: JOBS_ERROR_RETRY_INTERVAL_MS,
    keepPreviousData: false,
    refreshInterval: options?.refreshInterval,
    shouldRetryOnError: shouldRetryBackendReadError,
  })
}

export function useJob(jobId: string) {
  const activeWorkspaceId = useActiveWorkspaceId()

  return useSWR(
    activeWorkspaceId && jobId
      ? backendKeys.job(activeWorkspaceId, jobId)
      : null,
    () => getJob(jobId),
    WORKSPACE_SCOPED_SWR_OPTIONS
  )
}

export function useTags() {
  const activeWorkspaceId = useActiveWorkspaceId()

  return useSWR(
    activeWorkspaceId ? backendKeys.tags(activeWorkspaceId) : null,
    () => listTags(),
    WORKSPACE_SCOPED_SWR_OPTIONS
  )
}

export function useBackendCache() {
  const { mutate } = useSWRConfig()
  const activeWorkspaceId = useActiveWorkspaceId()

  const clearWorkspaceScopedCaches = React.useCallback(async () => {
    await mutate(
      (key) => isWorkspaceScopedKey(key),
      undefined,
      {
        populateCache: false,
        revalidate: false,
      }
    )
  }, [mutate])

  const revalidateWorkspaces = React.useCallback(async () => {
    await mutate(backendKeys.workspaces)
  }, [mutate])

  const revalidateAssetLists = React.useCallback(async () => {
    if (!activeWorkspaceId) {
      return
    }

    await mutate(
      (key) => matchesWorkspaceKey(key, "assets", activeWorkspaceId),
      undefined,
      {
        revalidate: true,
        populateCache: false,
      }
    )
  }, [activeWorkspaceId, mutate])

  const revalidateAssetDetail = React.useCallback(
    async (assetId: string) => {
      if (!activeWorkspaceId || !assetId) {
        return
      }

      await mutate(backendKeys.asset(activeWorkspaceId, assetId))
    },
    [activeWorkspaceId, mutate]
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
    if (!activeWorkspaceId) {
      return
    }

    await mutate(backendKeys.tags(activeWorkspaceId))
  }, [activeWorkspaceId, mutate])

  const revalidateConversions = React.useCallback(async () => {
    if (!activeWorkspaceId) {
      return
    }

    await mutate(backendKeys.conversions(activeWorkspaceId))
  }, [activeWorkspaceId, mutate])

  const revalidateSavedConfigs = React.useCallback(async () => {
    if (!activeWorkspaceId) {
      return
    }

    await mutate(backendKeys.savedConfigs(activeWorkspaceId))
  }, [activeWorkspaceId, mutate])

  const revalidateSavedConfigDetail = React.useCallback(
    async (configId: string) => {
      if (!activeWorkspaceId || !configId) {
        return
      }

      await mutate(backendKeys.savedConfig(activeWorkspaceId, configId))
    },
    [activeWorkspaceId, mutate]
  )

  const revalidateOutputs = React.useCallback(async () => {
    if (!activeWorkspaceId) {
      return
    }

    await mutate(
      (key) => matchesWorkspaceKey(key, "outputs", activeWorkspaceId),
      undefined,
      {
        revalidate: true,
      }
    )
  }, [activeWorkspaceId, mutate])

  const revalidateJobs = React.useCallback(async () => {
    if (!activeWorkspaceId) {
      return
    }

    await mutate(backendKeys.jobs(activeWorkspaceId))
  }, [activeWorkspaceId, mutate])

  const revalidateJobDetail = React.useCallback(
    async (jobId: string) => {
      if (!activeWorkspaceId || !jobId) {
        return
      }

      await mutate(backendKeys.job(activeWorkspaceId, jobId))
    },
    [activeWorkspaceId, mutate]
  )

  const revalidateConversionDetail = React.useCallback(
    async (conversionId: string) => {
      if (!activeWorkspaceId || !conversionId) {
        return
      }

      await mutate(backendKeys.conversion(activeWorkspaceId, conversionId))
    },
    [activeWorkspaceId, mutate]
  )

  const revalidateOutputDetail = React.useCallback(
    async (outputId: string) => {
      if (!activeWorkspaceId || !outputId) {
        return
      }

      await Promise.all([
        mutate(backendKeys.output(activeWorkspaceId, outputId), undefined, {
          revalidate: true,
        }),
        mutate(
          (key) => matchesWorkspaceKey(key, "outputs", activeWorkspaceId),
          undefined,
          {
            revalidate: true,
          }
        ),
      ])
    },
    [activeWorkspaceId, mutate]
  )

  return {
    clearWorkspaceScopedCaches,
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
    revalidateWorkspaces,
  }
}
