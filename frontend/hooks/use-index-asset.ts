"use client";

import * as React from "react";

import { useBackendCache } from "@/hooks/use-backend";
import type { AssetSummary } from "@/lib/api";
import { getErrorMessage, indexAsset, reindexAllAssets } from "@/lib/api";
import type { NoticeMessage } from "@/lib/types";

export function useIndexAsset() {
  const { revalidateAssetLists, revalidateJobs } = useBackendCache();
  const [pendingAssetIds, setPendingAssetIds] = React.useState<Set<string>>(new Set());

  const addPending = React.useCallback((assetId: string) => {
    setPendingAssetIds((current) => new Set(current).add(assetId));
  }, []);

  const removePending = React.useCallback((assetId: string) => {
    setPendingAssetIds((current) => {
      const next = new Set(current);
      next.delete(assetId);
      return next;
    });
  }, []);

  const refreshAssetLists = React.useCallback(async () => {
    await Promise.all([revalidateAssetLists(), revalidateJobs()]);
  }, [revalidateAssetLists, revalidateJobs]);

  const runIndexAsset = React.useCallback(
    async (asset: AssetSummary): Promise<NoticeMessage | null> => {
      if (asset.indexing_status === "indexing" || pendingAssetIds.has(asset.id)) {
        return null;
      }

      addPending(asset.id);

      try {
        await indexAsset(asset.id);
        await refreshAssetLists();
        return null;
      } catch (indexError) {
        const message = getErrorMessage(indexError);
        await refreshAssetLists();
        return {
          description: `${asset.file_name}: ${message}`,
          title: "Indexing failed",
          tone: "error",
        };
      } finally {
        removePending(asset.id);
      }
    },
    [addPending, pendingAssetIds, refreshAssetLists, removePending],
  );

  const runBulkIndex = React.useCallback(
    async (assets: AssetSummary[]): Promise<NoticeMessage | null> => {
      const actionable = assets.filter(
        (asset) => asset.indexing_status !== "indexing" && !pendingAssetIds.has(asset.id),
      );

      if (actionable.length === 0) {
        return null;
      }

      setPendingAssetIds((current) => {
        const next = new Set(current);
        for (const asset of actionable) {
          next.add(asset.id);
        }
        return next;
      });

      try {
        let indexedCount = 0;
        const failureMessages: string[] = [];

        for (const asset of actionable) {
          try {
            await indexAsset(asset.id);
            indexedCount += 1;
          } catch (indexError) {
            failureMessages.push(`${asset.file_name}: ${getErrorMessage(indexError)}`);
          } finally {
            removePending(asset.id);
            await refreshAssetLists();
          }
        }

        if (indexedCount > 0 && failureMessages.length === 0) {
          return null;
        }

        if (indexedCount > 0 && failureMessages.length > 0) {
          return {
            description: `${indexedCount} asset${indexedCount === 1 ? "" : "s"} indexed. ${failureMessages[0]}${failureMessages.length > 1 ? ` ${failureMessages.length - 1} more failed.` : ""}`,
            title: "Selection indexed with warnings",
            tone: "info",
          };
        }

        return {
          description: failureMessages[0] ?? "No selected assets could be indexed.",
          title: "Selected assets failed to index",
          tone: "error",
        };
      } finally {
        // Ensure all are removed even if loop exits early
        setPendingAssetIds((current) => {
          const next = new Set(current);
          for (const asset of actionable) {
            next.delete(asset.id);
          }
          return next;
        });
      }
    },
    [pendingAssetIds, refreshAssetLists, removePending],
  );

  const runIndexPending = React.useCallback(async (): Promise<NoticeMessage | null> => {
    try {
      const result = await reindexAllAssets();
      await refreshAssetLists();

      if (result.total_requested === 0) {
        return {
          description: "There were no pending or failed assets to index.",
          title: "Nothing to index",
          tone: "info",
        };
      }

      if (result.failed_assets.length > 0) {
        return {
          description: `${result.indexed_assets.length} asset${result.indexed_assets.length === 1 ? "" : "s"} indexed. ${result.failed_assets.length} asset${result.failed_assets.length === 1 ? "" : "s"} failed.`,
          title: "Pending indexing completed with warnings",
          tone: "info",
        };
      }

      return null;
    } catch (indexError) {
      const message = getErrorMessage(indexError);
      await refreshAssetLists();
      return {
        description: message,
        title: "Could not index pending assets",
        tone: "error",
      };
    }
  }, [refreshAssetLists]);

  return {
    pendingAssetIds,
    runBulkIndex,
    runIndexAsset,
    runIndexPending,
  };
}
