"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, RefreshCw, TriangleAlert } from "lucide-react";

import {
  useAssets,
  useBackendCache,
  useConversion,
  useConversions,
  useJob,
} from "@/hooks/use-backend";
import type { AssetSummary } from "@/lib/api";
import { BackendApiError, getErrorMessage } from "@/lib/api";
import {
  formatDateTime,
  formatJobType,
  isWorkflowActiveStatus,
} from "@/lib/format";
import { buildAssetDetailHref, resolveReturnHref } from "@/lib/navigation";
import { buildOutputsHref } from "@/lib/outputs";
import { getImagePayloadContract, isLegacyImagePayloadPolicy } from "@/lib/conversion-representation";

import { MetadataField } from "@/components/metadata-field";
import { WorkflowStatusBadge } from "@/components/workflow-status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function JobDetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-32" />
      <Skeleton className="h-28 rounded-xl" />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.9fr)]">
        <Skeleton className="h-80 rounded-xl" />
        <Skeleton className="h-80 rounded-xl" />
      </div>
      <Skeleton className="h-60 rounded-xl" />
    </div>
  );
}

export function JobDetailPageFallback() {
  return <JobDetailSkeleton />;
}

function TargetAssetLinks({
  assetIds,
  assetsById,
  currentHref,
}: {
  assetIds: string[];
  assetsById: Map<string, AssetSummary>;
  currentHref: string;
}) {
  if (assetIds.length === 0) {
    return <p className="text-sm text-muted-foreground">This job is not tied to a specific registered asset.</p>;
  }

  return (
    <div className="space-y-2">
      {assetIds.map((assetId) => {
        const asset = assetsById.get(assetId);
        return (
          <div
            key={assetId}
            className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/20 px-3 py-3"
          >
            <div className="space-y-1">
              <p className="text-sm font-medium text-foreground">{asset?.file_name ?? assetId}</p>
              <p className="break-all text-xs text-muted-foreground">{asset?.file_path ?? assetId}</p>
            </div>
            <Button asChild size="sm" variant="outline">
              <Link href={buildAssetDetailHref(assetId, currentHref)}>
                Open asset
                <ArrowRight className="size-3.5" />
              </Link>
            </Button>
          </div>
        );
      })}
    </div>
  );
}

export function JobDetailPage({ jobId }: { jobId: string }) {
  const searchParams = useSearchParams();
  const { revalidateConversionDetail, revalidateConversions, revalidateJobDetail, revalidateJobs } =
    useBackendCache();
  const jobResponse = useJob(jobId);
  const assetsResponse = useAssets();
  const conversionsResponse = useConversions();

  const matchedConversionSummary = React.useMemo(
    () => conversionsResponse.data?.find((conversion) => conversion.job_id === jobId) ?? null,
    [conversionsResponse.data, jobId],
  );
  const conversionDetailResponse = useConversion(matchedConversionSummary?.id ?? "");

  const returnHref = resolveReturnHref(searchParams.get("from"), "/jobs");
  const currentHref = React.useMemo(() => {
    const currentQuery = searchParams.toString();
    return currentQuery ? `/jobs/${jobId}?${currentQuery}` : `/jobs/${jobId}`;
  }, [jobId, searchParams]);

  const assetsById = React.useMemo(
    () => new Map((assetsResponse.data ?? []).map((asset) => [asset.id, asset])),
    [assetsResponse.data],
  );

  React.useEffect(() => {
    const job = jobResponse.data;
    if (!job) {
      return;
    }

    const conversionStatus =
      conversionDetailResponse.data?.status ?? matchedConversionSummary?.status ?? null;
    const shouldPoll =
      isWorkflowActiveStatus(job.status) ||
      (conversionStatus ? isWorkflowActiveStatus(conversionStatus) : false);

    if (!shouldPoll) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void jobResponse.mutate();
      void revalidateJobDetail(job.id);
      void revalidateJobs();

      if (matchedConversionSummary?.id) {
        void conversionDetailResponse.mutate();
        void revalidateConversionDetail(matchedConversionSummary.id);
      }

      void revalidateConversions();
    }, 1500);

    return () => window.clearInterval(intervalId);
  }, [
    conversionDetailResponse,
    jobResponse,
    matchedConversionSummary,
    revalidateConversionDetail,
    revalidateConversions,
    revalidateJobDetail,
    revalidateJobs,
  ]);

  if (jobResponse.isLoading) {
    return <JobDetailSkeleton />;
  }

  if (jobResponse.error) {
    const isMissingJob = jobResponse.error instanceof BackendApiError && jobResponse.error.status === 404;

    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <Alert variant="destructive">
          <AlertTitle>{isMissingJob ? "Job not found" : "Could not load job"}</AlertTitle>
          <AlertDescription>{getErrorMessage(jobResponse.error)}</AlertDescription>
        </Alert>
        {!isMissingJob ? (
          <div>
            <Button onClick={() => void jobResponse.mutate()} type="button" variant="outline">
              Try again
            </Button>
          </div>
        ) : null}
      </div>
    );
  }

  const job = jobResponse.data;
  if (!job) {
    return null;
  }

  const conversionDetail = conversionDetailResponse.data ?? null;
  const conversionRepresentationPolicy =
    conversionDetail?.representation_policy ??
    matchedConversionSummary?.representation_policy ??
    job.representation_policy ??
    null;
  const imagePayloadContract = getImagePayloadContract(conversionRepresentationPolicy);
  const usesLegacyContract = isLegacyImagePayloadPolicy(conversionRepresentationPolicy);

  return (
    <div className="space-y-6">
      <Button asChild size="sm" variant="ghost">
        <Link href={returnHref}>
          <ArrowLeft className="size-4" />
          Back
        </Link>
      </Button>

      <Card>
        <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            <CardTitle className="text-xl">{formatJobType(job.type)}</CardTitle>
            <CardDescription className="break-all">{job.id}</CardDescription>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <WorkflowStatusBadge status={job.status} />
            <Button onClick={() => void jobResponse.mutate()} size="sm" type="button" variant="outline">
              <RefreshCw className="size-3.5" />
              Refresh
            </Button>
          </div>
        </CardHeader>
      </Card>

      {job.error_message ? (
        <Alert variant="destructive">
          <TriangleAlert className="size-4" />
          <AlertTitle>Job failed</AlertTitle>
          <AlertDescription>{job.error_message}</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.9fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Job details</CardTitle>
            <CardDescription>Current durable job state reported by the backend.</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-4 sm:grid-cols-2">
              <MetadataField label="Type" value={formatJobType(job.type)} />
              <MetadataField label="Status" value={<WorkflowStatusBadge status={job.status} />} />
              <MetadataField label="Created" value={formatDateTime(job.created_at)} />
              <MetadataField label="Updated" value={formatDateTime(job.updated_at)} />
              <MetadataField label="Started" value={formatDateTime(job.started_at)} />
              <MetadataField label="Finished" value={formatDateTime(job.finished_at)} />
              <div className="space-y-1 sm:col-span-2">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Output path</dt>
                <dd className="break-all text-sm font-medium text-foreground">
                  {job.output_path ?? "Not available"}
                </dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Target assets</CardTitle>
            <CardDescription>Jump back to the assets this job was launched against.</CardDescription>
          </CardHeader>
          <CardContent>
            <TargetAssetLinks assetIds={job.target_asset_ids_json} assetsById={assetsById} currentHref={currentHref} />
          </CardContent>
        </Card>
      </div>

      {Object.keys(job.config_json).length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Config</CardTitle>
            <CardDescription>Execution parameters stored with the durable job record.</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto rounded-lg border bg-muted/20 p-3 text-xs text-foreground">
              {JSON.stringify(job.config_json, null, 2)}
            </pre>
          </CardContent>
        </Card>
      ) : null}

      {matchedConversionSummary ? (
        <Card>
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle>Conversion output</CardTitle>
              <CardDescription>Completed conversion metadata linked to this job.</CardDescription>
            </div>
            <Button asChild size="sm" variant="outline">
              <Link
                href={buildOutputsHref({
                  conversionId: matchedConversionSummary.id,
                  imagePayloadContract,
                })}
              >
                View outputs
                <ArrowRight className="size-3.5" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            <dl className="grid gap-4 sm:grid-cols-2">
              <MetadataField
                label="Conversion status"
                value={
                  <WorkflowStatusBadge
                    status={conversionDetail?.status ?? matchedConversionSummary.status}
                  />
                }
              />
              <MetadataField
                label="Created"
                value={formatDateTime(conversionDetail?.created_at ?? matchedConversionSummary.created_at)}
              />
              <div className="space-y-1 sm:col-span-2">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Output path</dt>
                <dd className="break-all text-sm font-medium text-foreground">
                  {conversionDetail?.output_path ?? matchedConversionSummary.output_path ?? "Not available"}
                </dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Image payload contract</dt>
                <dd className="text-sm font-medium text-foreground">{imagePayloadContract}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Schema policy</dt>
                <dd className="text-sm font-medium text-foreground">
                  v{conversionRepresentationPolicy?.policy_version ?? 1}
                </dd>
              </div>
            </dl>

            <p className="text-sm text-muted-foreground">
              {usesLegacyContract
                ? "Legacy list image payload mode is active for this conversion."
                : "Training loaders should consume bytes-based image features from this conversion."}
            </p>

            {conversionDetail?.error_message || matchedConversionSummary.error_message ? (
              <Alert variant="destructive">
                <TriangleAlert className="size-4" />
                <AlertTitle>Conversion error</AlertTitle>
                <AlertDescription>
                  {conversionDetail?.error_message ?? matchedConversionSummary.error_message}
                </AlertDescription>
              </Alert>
            ) : null}

            {conversionDetail?.output_files.length ? (
              <div className="space-y-2">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Output files</p>
                <div className="space-y-2">
                  {conversionDetail.output_files.map((outputFile) => (
                    <div
                      key={outputFile}
                      className="rounded-lg border bg-muted/20 px-3 py-2 text-sm break-all text-foreground"
                    >
                      {outputFile}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Output files are not available yet. The job detail will keep polling while the linked conversion is
                active.
              </p>
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
