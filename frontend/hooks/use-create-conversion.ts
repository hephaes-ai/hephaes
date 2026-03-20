"use client";

import * as React from "react";

import { useBackendCache } from "@/hooks/use-backend";
import type { AssetSummary, ConversionCreateRequest, ConversionDetail } from "@/lib/api";
import { createConversion, getErrorMessage } from "@/lib/api";
import type { NoticeMessage } from "@/lib/types";

export interface CreateConversionResult {
  conversion: ConversionDetail | null;
  notice: NoticeMessage | null;
}

export function useCreateConversion() {
  const {
    revalidateAssetDetail,
    revalidateConversionDetail,
    revalidateConversions,
    revalidateJobs,
    revalidateOutputs,
  } = useBackendCache();
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const submit = React.useCallback(
    async (
      payload: ConversionCreateRequest,
      assets: AssetSummary[],
    ): Promise<CreateConversionResult> => {
      setIsSubmitting(true);

      try {
        const result = await createConversion(payload);

        await Promise.all([
          ...assets.map((asset) => revalidateAssetDetail(asset.id)),
          revalidateConversionDetail(result.id),
          revalidateConversions(),
          revalidateJobs(),
          revalidateOutputs(),
        ]);

        return { conversion: result, notice: null };
      } catch (conversionError) {
        const message = getErrorMessage(conversionError);
        return {
          conversion: null,
          notice: {
            description: message,
            title: "Could not create conversion",
            tone: "error",
          },
        };
      } finally {
        setIsSubmitting(false);
      }
    },
    [revalidateAssetDetail, revalidateConversionDetail, revalidateConversions, revalidateJobs, revalidateOutputs],
  );

  return {
    isSubmitting,
    submit,
  };
}
