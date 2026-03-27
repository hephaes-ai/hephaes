"use client";

import * as React from "react";

import { useBackendCache } from "@/hooks/use-backend";
import { getErrorMessage, scanDirectoryForAssets } from "@/lib/api";
import { formatCount } from "@/lib/format";
import type { NoticeMessage } from "@/lib/types";

export interface ScanDirectoryResult {
  notice: NoticeMessage;
  dialogNotice?: undefined;
}

export interface ScanDirectoryError {
  notice?: undefined;
  dialogNotice: NoticeMessage;
}

export function useScanDirectory() {
  const { revalidateAssetLists } = useBackendCache();
  const [isScanning, setIsScanning] = React.useState(false);

  const scan = React.useCallback(
    async (directoryPath: string, recursive: boolean): Promise<ScanDirectoryResult | ScanDirectoryError> => {
      setIsScanning(true);

      try {
        const result = await scanDirectoryForAssets({
          directory_path: directoryPath,
          recursive,
        });

        if (result.registered_assets.length > 0) {
          await revalidateAssetLists();
        }

        const descriptionParts = [
          `Scanned ${result.scanned_directory} and found ${formatCount(result.discovered_file_count, "supported file")}`,
        ];

        if (result.registered_assets.length > 0) {
          descriptionParts.push(`${formatCount(result.registered_assets.length, "file")} added to inventory`);
        }

        if (result.skipped.length > 0) {
          const duplicateCount = result.skipped.filter((item) => item.reason === "duplicate").length;
          const invalidCount = result.skipped.filter((item) => item.reason === "invalid_path").length;
          const parts: string[] = [];
          if (duplicateCount > 0) parts.push(`${formatCount(duplicateCount, "duplicate")} skipped`);
          if (invalidCount > 0) parts.push(`${formatCount(invalidCount, "invalid file")} skipped`);
          const firstDetail = result.skipped[0]?.detail;
          if (firstDetail) parts.push(firstDetail);
          descriptionParts.push(parts.join(". "));
        }

        if (result.discovered_file_count === 0) {
          descriptionParts.push("No supported .bag or .mcap files were discovered");
        }

        const description = descriptionParts.join(". ");
        const tone: NoticeMessage["tone"] =
          result.registered_assets.length > 0 && result.skipped.length === 0
            ? "success"
            : result.registered_assets.length > 0 || result.skipped.length > 0 || result.discovered_file_count === 0
              ? "info"
              : "error";
        const title =
          result.registered_assets.length > 0 && result.skipped.length === 0
            ? "Directory scanned"
            : result.registered_assets.length > 0
              ? "Directory scanned with warnings"
              : result.discovered_file_count === 0
                ? "No supported files found"
                : "No new files were added";

        return {
          notice: { description, title, tone },
        };
      } catch (scanError) {
        const message = getErrorMessage(scanError);
        return {
          dialogNotice: {
            description: message,
            title: "Could not scan directory",
            tone: "error",
          },
        };
      } finally {
        setIsScanning(false);
      }
    },
    [revalidateAssetLists],
  );

  return {
    isScanning,
    scan,
  };
}
