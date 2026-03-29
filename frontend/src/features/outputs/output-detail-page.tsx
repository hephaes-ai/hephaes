"use client";

import * as React from "react";
import { ArrowLeft } from "lucide-react";

import { OutputDetailContent } from "@/components/output-detail-content";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/sonner";
import { useAssets, useOutput } from "@/hooks/use-backend";
import type { OutputDetail } from "@/lib/api";
import { BackendApiError, getErrorMessage } from "@/lib/api";
import {
  AppLink as Link,
  useAppSearchParams as useSearchParams,
} from "@/lib/app-routing";
import { resolveReturnHref } from "@/lib/navigation";

function OutputDetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-32" />
      <Skeleton className="h-28 rounded-xl" />
      <Skeleton className="h-40 rounded-xl" />
      <Skeleton className="h-64 rounded-xl" />
    </div>
  );
}

export function OutputDetailPageFallback() {
  return <OutputDetailSkeleton />;
}

export function OutputDetailPage({ outputId }: { outputId: string }) {
  const searchParams = useSearchParams();
  const outputResponse = useOutput(outputId);
  const assetsResponse = useAssets();

  const returnHref = resolveReturnHref(searchParams.get("from"), "/outputs");
  const currentHref = React.useMemo(() => {
    const currentQuery = searchParams.toString();
    return currentQuery ? `/outputs/${outputId}?${currentQuery}` : `/outputs/${outputId}`;
  }, [outputId, searchParams]);

  const assetsById = React.useMemo(
    () => new Map((assetsResponse.data ?? []).map((asset) => [asset.id, asset])),
    [assetsResponse.data],
  );

  async function onCopyReference(output: OutputDetail) {
    try {
      const reference = `${output.file_name} (${output.id})`;
      await navigator.clipboard.writeText(reference);
      toast.success("Output reference copied to clipboard.");
    } catch (error) {
      toast.error("Could not copy reference", {
        description: getErrorMessage(error),
      });
    }
  }

  if (outputResponse.isLoading) {
    return <OutputDetailSkeleton />;
  }

  if (outputResponse.error) {
    const isMissing = outputResponse.error instanceof BackendApiError && outputResponse.error.status === 404;

    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <Alert variant="destructive">
          <AlertTitle>{isMissing ? "Output not found" : "Could not load output"}</AlertTitle>
          <AlertDescription>{getErrorMessage(outputResponse.error)}</AlertDescription>
        </Alert>
        {!isMissing ? (
          <div>
            <Button onClick={() => void outputResponse.mutate()} type="button" variant="outline">
              Try again
            </Button>
          </div>
        ) : null}
      </div>
    );
  }

  const output = outputResponse.data;
  if (!output) {
    return null;
  }

  return (
    <div className="space-y-6">
      <Button asChild size="sm" variant="ghost">
        <Link href={returnHref}>
          <ArrowLeft className="size-4" />
          Back
        </Link>
      </Button>

      <OutputDetailContent
        assetsById={assetsById}
        currentHref={currentHref}
        onCopyReference={onCopyReference}
        output={output}
      />
    </div>
  );
}
