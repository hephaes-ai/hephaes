"use client";

import * as React from "react";
import useSWR, { useSWRConfig } from "swr";

import {
  getConversion,
  getAssetDetail,
  getHealth,
  listConversions,
  listAssets,
  listTags,
  serializeAssetListQuery,
  type AssetListQuery,
} from "@/lib/api";

export const backendKeys = {
  asset: (assetId: string) => ["asset", assetId] as const,
  assets: (query?: AssetListQuery | null) => ["assets", serializeAssetListQuery(query)] as const,
  conversion: (conversionId: string) => ["conversion", conversionId] as const,
  conversions: ["conversions"] as const,
  health: ["health"] as const,
  tags: ["tags"] as const,
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

export function useTags() {
  return useSWR(backendKeys.tags, () => listTags());
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

  const revalidateConversionDetail = React.useCallback(
    async (conversionId: string) => {
      if (!conversionId) {
        return;
      }

      await mutate(backendKeys.conversion(conversionId));
    },
    [mutate],
  );

  return {
    revalidateAssetDetail,
    revalidateAssetEverywhere,
    revalidateAssetLists,
    revalidateConversionDetail,
    revalidateConversions,
    revalidateTags,
  };
}
