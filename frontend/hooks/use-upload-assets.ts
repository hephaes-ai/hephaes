"use client";

import * as React from "react";

import { useBackendCache } from "@/hooks/use-backend";
import type { AssetRegistrationSkip, AssetSummary } from "@/lib/api";
import { BackendApiError, getErrorMessage, uploadAssetFile } from "@/lib/api";
import { formatCount } from "@/lib/format";
import type { NoticeMessage } from "@/lib/types";

export interface UploadProgressState {
  completed: number;
  total: number;
}

const UPLOAD_CONCURRENCY = 4;

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

function classifyUploadedFileSkip(file: File, error: unknown): AssetRegistrationSkip | null {
  if (!(error instanceof BackendApiError)) {
    return null;
  }

  if (error.status === 409) {
    return {
      detail: error.message,
      file_path: file.name,
      reason: "duplicate",
    };
  }

  if (error.status === 400) {
    return {
      detail: error.message,
      file_path: file.name,
      reason: "invalid_path",
    };
  }

  return null;
}

export interface UploadResult {
  notice: NoticeMessage | null;
  registeredCount: number;
  toastAction: { type: "success"; title: string; description: string } | null;
}

export function useUploadAssets() {
  const { revalidateAssetLists } = useBackendCache();
  const [isUploading, setIsUploading] = React.useState(false);
  const [progress, setProgress] = React.useState<UploadProgressState | null>(null);

  const upload = React.useCallback(
    async (files: File[]): Promise<UploadResult> => {
      if (files.length === 0) {
        return { notice: null, registeredCount: 0, toastAction: null };
      }

      setIsUploading(true);
      setProgress({ completed: 0, total: files.length });

      const registeredAssets: AssetSummary[] = [];
      const skipped: AssetRegistrationSkip[] = [];
      const unexpectedErrors: string[] = [];
      let completed = 0;

      try {
        let nextIndex = 0;
        const workerCount = Math.min(UPLOAD_CONCURRENCY, files.length);

        async function runWorker() {
          while (nextIndex < files.length) {
            const file = files[nextIndex];
            nextIndex += 1;

            try {
              const asset = await uploadAssetFile(file);
              registeredAssets.push(asset);
            } catch (uploadError) {
              const classifiedSkip = classifyUploadedFileSkip(file, uploadError);
              if (classifiedSkip) {
                skipped.push(classifiedSkip);
              } else {
                unexpectedErrors.push(`${file.name}: ${getErrorMessage(uploadError)}`);
              }
            } finally {
              completed += 1;
              setProgress({ completed, total: files.length });
            }
          }
        }

        await Promise.all(Array.from({ length: workerCount }, () => runWorker()));

        if (registeredAssets.length > 0) {
          await revalidateAssetLists();
        }

        const descriptionParts: string[] = [];

        if (registeredAssets.length > 0) {
          descriptionParts.push(`${formatCount(registeredAssets.length, "file")} uploaded to inventory`);
        }

        if (skipped.length > 0) {
          descriptionParts.push(summarizeSkipped(skipped));
        }

        if (unexpectedErrors.length > 0) {
          descriptionParts.push(
            `${unexpectedErrors[0]}${unexpectedErrors.length > 1 ? ` ${unexpectedErrors.length - 1} more upload${unexpectedErrors.length - 1 === 1 ? "" : "s"} failed.` : ""}`,
          );
        }

        const description = descriptionParts.join(". ") || "No uploaded files changed the inventory.";
        const tone: NoticeMessage["tone"] =
          unexpectedErrors.length > 0 && registeredAssets.length === 0 && skipped.length === 0
            ? "error"
            : registeredAssets.length > 0 && skipped.length === 0 && unexpectedErrors.length === 0
              ? "success"
              : "info";
        const title =
          registeredAssets.length > 0 && skipped.length === 0 && unexpectedErrors.length === 0
            ? "Uploads finished"
            : registeredAssets.length > 0
              ? "Uploads finished with warnings"
              : unexpectedErrors.length > 0 && skipped.length === 0
                ? "Uploads failed"
                : "No uploaded files were added";

        if (tone === "success") {
          return {
            notice: null,
            registeredCount: registeredAssets.length,
            toastAction: {
              type: "success",
              title: registeredAssets.length === 1 ? "Upload completed" : "Uploads completed",
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
        setIsUploading(false);
        setProgress(null);
      }
    },
    [revalidateAssetLists],
  );

  return {
    isUploading,
    progress,
    upload,
  };
}
