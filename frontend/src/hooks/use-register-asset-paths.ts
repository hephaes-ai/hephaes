"use client";

import * as React from "react";

import { useBackendCache } from "@/hooks/use-backend";
import type { AssetRegistrationSkip, AssetSummary } from "@/lib/api";
import { BackendApiError, getErrorMessage, registerAsset } from "@/lib/api";
import { formatCount } from "@/lib/format";
import type { NoticeMessage } from "@/lib/types";

export interface RegisterAssetPathProgressState {
  completed: number;
  total: number;
}

const REGISTER_CONCURRENCY = 4;

function summarizeSkipped(skipped: AssetRegistrationSkip[]) {
  if (skipped.length === 0) {
    return "";
  }

  const duplicateCount = skipped.filter((item) => item.reason === "duplicate").length;
  const invalidCount = skipped.filter((item) => item.reason === "invalid_path").length;
  const parts: string[] = [];

  if (duplicateCount > 0) {
    parts.push(`${formatCount(duplicateCount, "duplicate")} skipped`);
  }

  if (invalidCount > 0) {
    parts.push(`${formatCount(invalidCount, "invalid file")} skipped`);
  }

  const firstDetail = skipped[0]?.detail;
  if (firstDetail) {
    parts.push(firstDetail);
  }

  return parts.join(". ");
}

function classifyPathRegistrationSkip(
  filePath: string,
  error: unknown,
): AssetRegistrationSkip | null {
  if (!(error instanceof BackendApiError)) {
    return null;
  }

  if (error.status === 409) {
    return {
      detail: error.message,
      file_path: filePath,
      reason: "duplicate",
    };
  }

  if (error.status === 400) {
    return {
      detail: error.message,
      file_path: filePath,
      reason: "invalid_path",
    };
  }

  return null;
}

export interface RegisterAssetPathsResult {
  notice: NoticeMessage | null;
  registeredCount: number;
  toastAction: { type: "success"; title: string; description: string } | null;
}

export function useRegisterAssetPaths() {
  const { revalidateAssetLists } = useBackendCache();
  const [isRegistering, setIsRegistering] = React.useState(false);
  const [progress, setProgress] = React.useState<RegisterAssetPathProgressState | null>(null);

  const registerPaths = React.useCallback(
    async (filePaths: string[]): Promise<RegisterAssetPathsResult> => {
      if (filePaths.length === 0) {
        return { notice: null, registeredCount: 0, toastAction: null };
      }

      setIsRegistering(true);
      setProgress({ completed: 0, total: filePaths.length });

      const registeredAssets: AssetSummary[] = [];
      const skipped: AssetRegistrationSkip[] = [];
      const unexpectedErrors: string[] = [];
      let completed = 0;

      try {
        let nextIndex = 0;
        const workerCount = Math.min(REGISTER_CONCURRENCY, filePaths.length);

        async function runWorker() {
          while (nextIndex < filePaths.length) {
            const filePath = filePaths[nextIndex];
            nextIndex += 1;

            try {
              const asset = await registerAsset({ file_path: filePath });
              registeredAssets.push(asset);
            } catch (registrationError) {
              const classifiedSkip = classifyPathRegistrationSkip(filePath, registrationError);
              if (classifiedSkip) {
                skipped.push(classifiedSkip);
              } else {
                unexpectedErrors.push(`${filePath}: ${getErrorMessage(registrationError)}`);
              }
            } finally {
              completed += 1;
              setProgress({ completed, total: filePaths.length });
            }
          }
        }

        await Promise.all(Array.from({ length: workerCount }, () => runWorker()));

        if (registeredAssets.length > 0) {
          await revalidateAssetLists();
        }

        const descriptionParts: string[] = [];

        if (registeredAssets.length > 0) {
          descriptionParts.push(`${formatCount(registeredAssets.length, "file")} added to inventory`);
        }

        if (skipped.length > 0) {
          descriptionParts.push(summarizeSkipped(skipped));
        }

        if (unexpectedErrors.length > 0) {
          descriptionParts.push(
            `${unexpectedErrors[0]}${unexpectedErrors.length > 1 ? ` ${unexpectedErrors.length - 1} more registration${unexpectedErrors.length - 1 === 1 ? "" : "s"} failed.` : ""}`,
          );
        }

        const description = descriptionParts.join(". ") || "No selected files changed the inventory.";
        const tone: NoticeMessage["tone"] =
          unexpectedErrors.length > 0 && registeredAssets.length === 0 && skipped.length === 0
            ? "error"
            : registeredAssets.length > 0 && skipped.length === 0 && unexpectedErrors.length === 0
              ? "success"
              : "info";
        const title =
          registeredAssets.length > 0 && skipped.length === 0 && unexpectedErrors.length === 0
            ? "Files added"
            : registeredAssets.length > 0
              ? "Files added with warnings"
              : unexpectedErrors.length > 0 && skipped.length === 0
                ? "File registration failed"
                : "No selected files were added";

        if (tone === "success") {
          return {
            notice: null,
            registeredCount: registeredAssets.length,
            toastAction: {
              type: "success",
              title: registeredAssets.length === 1 ? "File added" : "Files added",
              description,
            },
          };
        }

        return {
          notice: { description, title, tone },
          registeredCount: registeredAssets.length,
          toastAction: null,
        };
      } finally {
        setIsRegistering(false);
        setProgress(null);
      }
    },
    [revalidateAssetLists],
  );

  return {
    isRegistering,
    progress,
    registerPaths,
  };
}
