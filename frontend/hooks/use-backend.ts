"use client";

import useSWR from "swr";

import { getAssetDetail, getHealth, listAssets } from "@/lib/api";

export const backendKeys = {
  asset: (assetId: string) => ["asset", assetId] as const,
  assets: ["assets"] as const,
  health: ["health"] as const,
};

export function useHealth() {
  return useSWR(backendKeys.health, () => getHealth(), {
    dedupingInterval: 10_000,
    errorRetryCount: 1,
    refreshInterval: 30_000,
  });
}

export function useAssets() {
  return useSWR(backendKeys.assets, () => listAssets());
}

export function useAsset(assetId: string) {
  return useSWR(assetId ? backendKeys.asset(assetId) : null, () => getAssetDetail(assetId));
}
