"use client";

import * as React from "react";
import useSWR, { useSWRConfig } from "swr";

import { getAssetDetail, getHealth, listAssets, serializeAssetListQuery, type AssetListQuery } from "@/lib/api";

export const backendKeys = {
  asset: (assetId: string) => ["asset", assetId] as const,
  assets: (query?: AssetListQuery | null) => ["assets", serializeAssetListQuery(query)] as const,
  health: ["health"] as const,
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

  return {
    revalidateAssetDetail,
    revalidateAssetEverywhere,
    revalidateAssetLists,
  };
}
