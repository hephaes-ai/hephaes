"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ChevronDown, ListFilter, RefreshCw } from "lucide-react";

import { useAssets, useJobs } from "@/hooks/use-backend";
import type { AssetSummary, JobStatus, JobType } from "@/lib/api";
import { BackendApiError, getErrorMessage } from "@/lib/api";
import {
  formatDateTime,
  formatJobType,
  isWorkflowActiveStatus,
} from "@/lib/format";
import { cn } from "@/lib/utils";

import { EmptyState } from "@/components/empty-state";
import { WorkflowStatusBadge } from "@/components/workflow-status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const JOB_TYPE_OPTIONS: JobType[] = ["index", "convert", "prepare_visualization"];
const JOB_STATUS_OPTIONS: JobStatus[] = ["queued", "running", "succeeded", "failed"];

function buildAssetDetailHref(assetId: string, returnHref: string) {
  return `/assets/${assetId}?from=${encodeURIComponent(returnHref)}`;
}

function buildJobDetailHref(jobId: string, returnHref: string) {
  return `/jobs/${jobId}?from=${encodeURIComponent(returnHref)}`;
}

function JobsPageSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-9 w-32" />
      <Skeleton className="h-28 rounded-xl" />
      <Skeleton className="h-[460px] rounded-xl" />
    </div>
  );
}

export function JobsPageFallback() {
  return <JobsPageSkeleton />;
}


function formatTargetAssetLabel(asset: AssetSummary | undefined, assetId: string) {
  if (!asset) {
    return assetId;
  }

  return asset.file_name;
}

function AssetTargetLinks({
  assetIds,
  assetsById,
  currentHref,
}: {
  assetIds: string[];
  assetsById: Map<string, AssetSummary>;
  currentHref: string;
}) {
  if (assetIds.length === 0) {
    return <span className="text-sm text-muted-foreground">No assets</span>;
  }

  const visibleAssetIds = assetIds.slice(0, 2);
  const hiddenAssetCount = Math.max(assetIds.length - visibleAssetIds.length, 0);

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {visibleAssetIds.map((assetId) => (
        <Button asChild key={assetId} size="xs" variant="outline">
          <Link href={buildAssetDetailHref(assetId, currentHref)}>
            {formatTargetAssetLabel(assetsById.get(assetId), assetId)}
          </Link>
        </Button>
      ))}
      {hiddenAssetCount > 0 ? (
        <span className="text-xs text-muted-foreground">+{hiddenAssetCount} more</span>
      ) : null}
    </div>
  );
}

export function JobsPage() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeType = searchParams.get("type")?.trim() ?? "";
  const activeStatus = searchParams.get("status")?.trim() ?? "";
  const currentHref = searchParams.toString() ? `${pathname}?${searchParams.toString()}` : pathname;

  const jobsResponse = useJobs();
  const assetsResponse = useAssets();
  const jobs = jobsResponse.data ?? [];
  const assets = assetsResponse.data;
  const assetsById = React.useMemo(
    () => new Map((assets ?? []).map((asset) => [asset.id, asset])),
    [assets],
  );

  const filteredJobs = jobs.filter((job) => {
    if (activeType && job.type !== activeType) {
      return false;
    }

    if (activeStatus && job.status !== activeStatus) {
      return false;
    }

    return true;
  });

  const activeJobCount = jobs.filter((job) => isWorkflowActiveStatus(job.status)).length;
  const shouldPollJobs = jobs.some((job) => isWorkflowActiveStatus(job.status));
  const hasAppliedFilters = !!(activeType || activeStatus);
  const activeFilterCount = (activeType ? 1 : 0) + (activeStatus ? 1 : 0);
  const [isFiltersOpen, setIsFiltersOpen] = React.useState(hasAppliedFilters);

  React.useEffect(() => {
    if (!shouldPollJobs) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void jobsResponse.mutate();
    }, 1500);

    return () => window.clearInterval(intervalId);
  }, [jobsResponse, shouldPollJobs]);

  function updateFilters(updates: Record<string, string | null>) {
    const nextParams = new URLSearchParams(searchParams.toString());

    for (const [key, value] of Object.entries(updates)) {
      const normalizedValue = value?.trim() ?? "";
      if (!normalizedValue) {
        nextParams.delete(key);
      } else {
        nextParams.set(key, normalizedValue);
      }
    }

    const nextQuery = nextParams.toString();
    const nextHref = nextQuery ? `${pathname}?${nextQuery}` : pathname;

    React.startTransition(() => {
      router.replace(nextHref, { scroll: false });
    });
  }

  if (jobsResponse.isLoading) {
    return <JobsPageSkeleton />;
  }

  if (jobsResponse.error) {
    const isMissingRoute =
      jobsResponse.error instanceof BackendApiError && jobsResponse.error.status === 404;

    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <AlertTitle>{isMissingRoute ? "Jobs route not found" : "Could not load jobs"}</AlertTitle>
          <AlertDescription>{getErrorMessage(jobsResponse.error)}</AlertDescription>
        </Alert>
        <div>
          <Button onClick={() => void jobsResponse.mutate()} type="button" variant="outline">
            Try again
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight">Jobs</h1>
              <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                {jobs.length} total
              </span>
              <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                {activeJobCount} active
              </span>
            </div>
            <p className="max-w-3xl text-sm text-muted-foreground">
              Monitor indexing, conversion, visualization jobs.
            </p>
          </div>
          <Button
            disabled={jobsResponse.isLoading}
            onClick={() => void jobsResponse.mutate()}
            size="sm"
            type="button"
            variant="outline"
          >
            <RefreshCw className="size-4" />
            Refresh
          </Button>
        </div>
      </section>

      {jobs.length === 0 ? (
        <EmptyState
          description="Indexing, conversion, and visualization-preparation runs will appear here once the backend starts creating durable jobs."
          title="No jobs yet"
        />
      ) : (
        <Card>
          <CardHeader className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <CardTitle>Job history</CardTitle>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge className="h-6" variant="secondary">
                  {filteredJobs.length} result{filteredJobs.length === 1 ? "" : "s"}
                </Badge>
                <Button
                  aria-expanded={isFiltersOpen}
                  onClick={() => setIsFiltersOpen((current) => !current)}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  <ListFilter className="size-4" />
                  Filters{hasAppliedFilters ? ` (${activeFilterCount})` : ""}
                  <ChevronDown className={cn("size-4 transition-transform", isFiltersOpen && "rotate-180")} />
                </Button>
              </div>
            </div>

            <div
              className={cn(
                "grid transition-all duration-200 ease-out",
                isFiltersOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
              )}
            >
              <div className="overflow-hidden">
                <div className="space-y-4 rounded-xl border bg-muted/20 p-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="job-type-filter">
                        Job type
                      </label>
                      <NativeSelect
                        id="job-type-filter"
                        onChange={(event) => updateFilters({ type: event.target.value || null })}
                        value={activeType}
                      >
                        <option value="">All job types</option>
                        {JOB_TYPE_OPTIONS.map((jobType) => (
                          <option key={jobType} value={jobType}>
                            {formatJobType(jobType)}
                          </option>
                        ))}
                      </NativeSelect>
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="job-status-filter">
                        Status
                      </label>
                      <NativeSelect
                        id="job-status-filter"
                        onChange={(event) => updateFilters({ status: event.target.value || null })}
                        value={activeStatus}
                      >
                        <option value="">All statuses</option>
                        {JOB_STATUS_OPTIONS.map((jobStatus) => (
                          <option key={jobStatus} value={jobStatus}>
                            {jobStatus}
                          </option>
                        ))}
                      </NativeSelect>
                    </div>
                  </div>
                  {hasAppliedFilters ? (
                    <div className="flex justify-end">
                      <Button
                        onClick={() => updateFilters({ status: null, type: null })}
                        size="sm"
                        type="button"
                        variant="ghost"
                      >
                        Clear filters
                      </Button>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          </CardHeader>

          {filteredJobs.length === 0 ? (
            <CardContent>
              <div className="rounded-xl border border-dashed px-6 py-16 text-center">
                <h2 className="text-sm font-medium text-foreground">No matching jobs</h2>
                <p className="mx-auto mt-2 max-w-2xl text-sm text-muted-foreground">
                  Try clearing one of the active filters to see the rest of the backend job history.
                </p>
              </div>
            </CardContent>
          ) : (
            <CardContent>
              <div className="overflow-x-auto">
                <Table className="min-w-[820px]">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Target assets</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead>Updated</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredJobs.map((job) => (
                      <TableRow
                        className="cursor-pointer"
                        key={job.id}
                        onClick={() => router.push(buildJobDetailHref(job.id, currentHref))}
                      >
                        <TableCell className="font-medium">{formatJobType(job.type)}</TableCell>
                        <TableCell>
                          <WorkflowStatusBadge status={job.status} />
                        </TableCell>
                        <TableCell>
                          <div className="space-y-2">
                            <AssetTargetLinks
                              assetIds={job.target_asset_ids_json}
                              assetsById={assetsById}
                              currentHref={currentHref}
                            />
                            {job.target_asset_ids_json.length > 0 ? (
                              <p className="text-xs text-muted-foreground">
                                {job.target_asset_ids_json.length} asset
                                {job.target_asset_ids_json.length === 1 ? "" : "s"}
                              </p>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{formatDateTime(job.created_at)}</TableCell>
                        <TableCell className="text-muted-foreground">{formatDateTime(job.updated_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          )}
        </Card>
      )}
    </div>
  );
}
