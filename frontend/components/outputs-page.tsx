"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, Copy, Database, ListFilter, RefreshCw } from "lucide-react";

import { useFeedback } from "@/components/feedback-provider";
import { WorkflowStatusBadge } from "@/components/workflow-status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
import { useAssets, useOutput, useOutputs } from "@/hooks/use-backend";
import type { AssetSummary, OutputAvailability, OutputDetail, OutputFormat, OutputsQuery } from "@/lib/api";
import { getErrorMessage } from "@/lib/api";
import {
  formatDateTime,
  formatOutputAvailability,
  formatOutputFormat,
} from "@/lib/format";

const OUTPUT_FORMAT_OPTIONS: OutputFormat[] = ["parquet", "tfrecord", "json", "unknown"];
const OUTPUT_AVAILABILITY_OPTIONS: OutputAvailability[] = ["ready"];

function buildAssetDetailHref(assetId: string, returnHref: string) {
  return `/assets/${assetId}?from=${encodeURIComponent(returnHref)}`;
}

function buildJobDetailHref(jobId: string, returnHref: string) {
  return `/jobs/${jobId}?from=${encodeURIComponent(returnHref)}`;
}

function formatCount(count: number, noun: string) {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function buildOutputsQuery(searchParams: URLSearchParams): OutputsQuery {
  const search = searchParams.get("search")?.trim() ?? "";
  const format = searchParams.get("format")?.trim() ?? "";
  const assetId = searchParams.get("asset_id")?.trim() ?? "";
  const availability = searchParams.get("availability")?.trim() ?? "";
  const conversionId = searchParams.get("conversion_id")?.trim() ?? "";

  return {
    asset_id: assetId || undefined,
    availability: availability === "ready" ? "ready" : undefined,
    conversion_id: conversionId || undefined,
    format: OUTPUT_FORMAT_OPTIONS.includes(format as OutputFormat)
      ? (format as OutputFormat)
      : undefined,
    search: search || undefined,
  };
}

function OutputsPageSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-9 w-44" />
      <Skeleton className="h-28 rounded-xl" />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
        <Skeleton className="h-[560px] rounded-xl" />
        <Skeleton className="h-[560px] rounded-xl" />
      </div>
    </div>
  );
}

export function OutputsPageFallback() {
  return <OutputsPageSkeleton />;
}

function OutputsEmptyState({
  action,
  description,
  title,
}: {
  action?: React.ReactNode;
  description: string;
  title: string;
}) {
  return (
    <div className="rounded-xl border border-dashed px-6 py-16 text-center">
      <h2 className="text-sm font-medium text-foreground">{title}</h2>
      <p className="mx-auto mt-2 max-w-2xl text-sm text-muted-foreground">{description}</p>
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  );
}

function MetadataField({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium text-foreground">{value}</dd>
    </div>
  );
}

function OutputAvailabilityBadge({ availability }: { availability: OutputAvailability }) {
  return (
    <Badge className="border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200" variant="outline">
      {formatOutputAvailability(availability)}
    </Badge>
  );
}

function OutputSourceLinks({
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

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {assetIds.map((assetId) => (
        <Button asChild key={assetId} size="xs" variant="outline">
          <Link href={buildAssetDetailHref(assetId, currentHref)}>
            {assetsById.get(assetId)?.file_name ?? assetId}
          </Link>
        </Button>
      ))}
    </div>
  );
}

function OutputDetailPanel({
  assetsById,
  currentHref,
  onClearSelection,
  onCopyPath,
  output,
  selectionMissing,
}: {
  assetsById: Map<string, AssetSummary>;
  currentHref: string;
  onClearSelection: () => void;
  onCopyPath: (output: OutputDetail) => Promise<void>;
  output: OutputDetail | null;
  selectionMissing: boolean;
}) {
  if (selectionMissing) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Selected output not found</CardTitle>
          <CardDescription>
            The output in the URL is not available in the current conversion history anymore.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={onClearSelection} type="button" variant="outline">
            Clear selection
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!output) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Output detail</CardTitle>
          <CardDescription>
            Select an output to inspect its path, source assets, and conversion settings.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const siblingOutputs = output.sibling_output_files.filter(
    (siblingOutput) => siblingOutput !== output.output_file,
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            <CardTitle className="break-all text-xl">{output.file_name}</CardTitle>
            <CardDescription className="break-all">{output.relative_path}</CardDescription>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <OutputAvailabilityBadge availability={output.availability} />
            <Button onClick={() => void onCopyPath(output)} size="sm" type="button" variant="outline">
              <Copy className="size-3.5" />
              Copy path
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <dl className="grid gap-4 sm:grid-cols-2">
            <MetadataField label="Format" value={formatOutputFormat(output.format)} />
            <MetadataField label="Created" value={formatDateTime(output.created_at)} />
            <MetadataField
              label="Conversion status"
              value={<WorkflowStatusBadge status={output.conversion_status} />}
            />
            <MetadataField label="Job status" value={<WorkflowStatusBadge status={output.job_status} />} />
            <MetadataField label="Conversion ID" value={<span className="break-all font-mono text-xs">{output.conversion_id}</span>} />
            <MetadataField label="Job ID" value={<span className="break-all font-mono text-xs">{output.job_id}</span>} />
            <div className="space-y-1 sm:col-span-2">
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Output path</dt>
              <dd className="break-all text-sm font-medium text-foreground">{output.output_file}</dd>
            </div>
          </dl>

          <div className="space-y-2">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Source assets</p>
            <OutputSourceLinks assetIds={output.asset_ids} assetsById={assetsById} currentHref={currentHref} />
          </div>

          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline">
              <Link href={buildJobDetailHref(output.job_id, currentHref)}>
                Open job
                <ArrowRight className="size-3.5" />
              </Link>
            </Button>
            {output.asset_ids.length === 1 ? (
              <Button asChild size="sm" variant="outline">
                <Link href={buildAssetDetailHref(output.asset_ids[0], currentHref)}>
                  Open asset
                  <ArrowRight className="size-3.5" />
                </Link>
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {Object.keys(output.config).length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Conversion config</CardTitle>
            <CardDescription>
              Stored conversion settings for the run that produced this output.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto rounded-lg border bg-muted/20 p-3 text-xs text-foreground">
              {JSON.stringify(output.config, null, 2)}
            </pre>
          </CardContent>
        </Card>
      ) : null}

      {siblingOutputs.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Other files from this conversion</CardTitle>
            <CardDescription>
              Additional files reported by the same conversion run.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {siblingOutputs.map((siblingOutput) => (
              <div
                key={siblingOutput}
                className="rounded-lg border bg-muted/20 px-3 py-2 text-sm text-foreground break-all"
              >
                {siblingOutput}
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function OutputsTable({
  assetsById,
  currentHref,
  onCopyPath,
  onSelectOutput,
  outputs,
  selectedOutputId,
}: {
  assetsById: Map<string, AssetSummary>;
  currentHref: string;
  onCopyPath: (output: OutputDetail) => Promise<void>;
  onSelectOutput: (outputId: string) => void;
  outputs: OutputDetail[];
  selectedOutputId: string;
}) {
  return (
    <div className="hidden overflow-x-auto md:block">
      <Table className="min-w-[860px]">
        <TableHeader>
          <TableRow>
            <TableHead>Output file</TableHead>
            <TableHead>Format</TableHead>
            <TableHead>Source assets</TableHead>
            <TableHead>Created</TableHead>
            <TableHead>Availability</TableHead>
            <TableHead className="w-44 text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {outputs.map((output) => {
            const isSelected = output.id === selectedOutputId;

            return (
              <TableRow
                key={output.id}
                className={isSelected ? "bg-muted/35" : undefined}
                onClick={() => onSelectOutput(output.id)}
              >
                <TableCell className="max-w-0">
                  <div className="space-y-1">
                    <p className="font-medium text-foreground">{output.file_name}</p>
                    <p className="truncate text-xs text-muted-foreground">{output.relative_path}</p>
                  </div>
                </TableCell>
                <TableCell>{formatOutputFormat(output.format)}</TableCell>
                <TableCell>
                  <OutputSourceLinks assetIds={output.asset_ids} assetsById={assetsById} currentHref={currentHref} />
                </TableCell>
                <TableCell>{formatDateTime(output.created_at)}</TableCell>
                <TableCell>
                  <OutputAvailabilityBadge availability={output.availability} />
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-2">
                    <Button
                      onClick={(event) => {
                        event.stopPropagation();
                        onSelectOutput(output.id);
                      }}
                      size="sm"
                      type="button"
                      variant={isSelected ? "secondary" : "outline"}
                    >
                      Inspect
                    </Button>
                    <Button
                      onClick={(event) => {
                        event.stopPropagation();
                        void onCopyPath(output);
                      }}
                      size="sm"
                      type="button"
                      variant="outline"
                    >
                      Copy path
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function OutputsCards({
  assetsById,
  currentHref,
  onCopyPath,
  onSelectOutput,
  outputs,
}: {
  assetsById: Map<string, AssetSummary>;
  currentHref: string;
  onCopyPath: (output: OutputDetail) => Promise<void>;
  onSelectOutput: (outputId: string) => void;
  outputs: OutputDetail[];
}) {
  return (
    <div className="space-y-3 md:hidden">
      {outputs.map((output) => (
        <div key={output.id} className="space-y-3 rounded-xl border bg-muted/15 px-4 py-4">
          <div className="space-y-1">
            <p className="font-medium text-foreground">{output.file_name}</p>
            <p className="break-all text-xs text-muted-foreground">{output.relative_path}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{formatOutputFormat(output.format)}</Badge>
            <OutputAvailabilityBadge availability={output.availability} />
          </div>
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Source assets</p>
            <OutputSourceLinks assetIds={output.asset_ids} assetsById={assetsById} currentHref={currentHref} />
          </div>
          <p className="text-sm text-muted-foreground">Created {formatDateTime(output.created_at)}</p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => onSelectOutput(output.id)} size="sm" type="button" variant="secondary">
              Inspect
            </Button>
            <Button onClick={() => void onCopyPath(output)} size="sm" type="button" variant="outline">
              Copy path
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}

export function OutputsPage() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { notify } = useFeedback();
  const query = React.useMemo(() => buildOutputsQuery(searchParams), [searchParams]);
  const outputsResponse = useOutputs(query);
  const selectedOutputId = searchParams.get("output")?.trim() ?? "";
  const selectedOutputResponse = useOutput(selectedOutputId);
  const assetsResponse = useAssets();
  const outputs = outputsResponse.data ?? [];
  const currentHref = React.useMemo(() => {
    const queryString = searchParams.toString();
    return queryString ? `${pathname}?${queryString}` : pathname;
  }, [pathname, searchParams]);
  const selectedOutput =
    outputs.find((output) => output.id === selectedOutputId) ?? selectedOutputResponse.data ?? null;
  const assetsById = React.useMemo(
    () => new Map((assetsResponse.data ?? []).map((asset) => [asset.id, asset])),
    [assetsResponse.data],
  );
  const hasAppliedFilters = Boolean(
    query.asset_id ||
      query.availability ||
      query.conversion_id ||
      query.format ||
      query.search,
  );

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

  async function onCopyPath(output: OutputDetail) {
    try {
      await navigator.clipboard.writeText(output.output_file);
      notify({
        description: output.output_file,
        title: "Output path copied",
        tone: "success",
      });
    } catch (error) {
      notify({
        description: getErrorMessage(error),
        title: "Could not copy path",
        tone: "error",
      });
    }
  }

  if (outputsResponse.isLoading && !outputsResponse.data) {
    return <OutputsPageSkeleton />;
  }

  if (outputsResponse.error) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <AlertTitle>Could not load outputs</AlertTitle>
          <AlertDescription>{getErrorMessage(outputsResponse.error)}</AlertDescription>
        </Alert>
        <div>
          <Button onClick={() => void outputsResponse.mutate()} type="button" variant="outline">
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
              <h1 className="text-2xl font-semibold tracking-tight">Outputs</h1>
              <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                {formatCount(outputs.length, "output")}
              </span>
            </div>
            <p className="max-w-3xl text-sm text-muted-foreground">
              Browse the files produced by conversion runs without retracing the original job history.
            </p>
          </div>
          <Button
            disabled={outputsResponse.isLoading}
            onClick={() => void outputsResponse.mutate()}
            size="sm"
            type="button"
            variant="outline"
          >
            <RefreshCw className="size-4" />
            Refresh
          </Button>
        </div>
      </section>

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ListFilter className="size-4" />
              Filters
            </CardTitle>
            <CardDescription>
              Keep the outputs workspace focused while preserving shareable URL state.
            </CardDescription>
          </div>
          {hasAppliedFilters || selectedOutputId ? (
            <Button
              onClick={() =>
                updateFilters({
                  asset_id: null,
                  availability: null,
                  conversion_id: null,
                  format: null,
                  output: null,
                  search: null,
                })
              }
              size="sm"
              type="button"
              variant="ghost"
            >
              Clear filters
            </Button>
          ) : null}
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_180px]">
            <div className="space-y-2">
              <label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="outputs-search">
                Search
              </label>
              <Input
                id="outputs-search"
                onChange={(event) => updateFilters({ search: event.target.value, output: null })}
                placeholder="Search file name, path, job, or asset ID"
                value={query.search ?? ""}
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="outputs-format">
                Format
              </label>
              <NativeSelect
                id="outputs-format"
                onChange={(event) => updateFilters({ format: event.target.value || null, output: null })}
                value={query.format ?? ""}
              >
                <option value="">All formats</option>
                {OUTPUT_FORMAT_OPTIONS.map((format) => (
                  <option key={format} value={format}>
                    {formatOutputFormat(format)}
                  </option>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-2">
              <label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="outputs-availability">
                Availability
              </label>
              <NativeSelect
                id="outputs-availability"
                onChange={(event) =>
                  updateFilters({ availability: event.target.value || null, output: null })
                }
                value={query.availability ?? ""}
              >
                <option value="">All</option>
                {OUTPUT_AVAILABILITY_OPTIONS.map((availability) => (
                  <option key={availability} value={availability}>
                    {formatOutputAvailability(availability)}
                  </option>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-2">
              <label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="outputs-asset">
                Asset ID
              </label>
              <Input
                id="outputs-asset"
                onChange={(event) => updateFilters({ asset_id: event.target.value, output: null })}
                placeholder="Filter to one asset"
                value={query.asset_id ?? ""}
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="outputs-conversion">
                Conversion ID
              </label>
              <Input
                id="outputs-conversion"
                onChange={(event) => updateFilters({ conversion_id: event.target.value, output: null })}
                placeholder="Filter to one conversion"
                value={query.conversion_id ?? ""}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {outputs.length === 0 ? (
        <OutputsEmptyState
          action={
            hasAppliedFilters ? (
              <Button
                onClick={() =>
                  updateFilters({
                    asset_id: null,
                    availability: null,
                    conversion_id: null,
                    format: null,
                    output: null,
                    search: null,
                  })
                }
                type="button"
                variant="outline"
              >
                Clear filters
              </Button>
            ) : undefined
          }
          description={
            hasAppliedFilters
              ? "Try clearing one or more filters to see outputs from other conversion runs."
              : "Run a conversion and its reported output files will appear here for later inspection."
          }
          title={hasAppliedFilters ? "No outputs match these filters" : "No outputs yet"}
        />
      ) : (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="size-4" />
                  Output catalog
                </CardTitle>
                <CardDescription>
                  Select an output to inspect its source assets, path, and conversion settings.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <OutputsTable
                  assetsById={assetsById}
                  currentHref={currentHref}
                  onCopyPath={onCopyPath}
                  onSelectOutput={(outputId) => updateFilters({ output: outputId })}
                  outputs={outputs}
                  selectedOutputId={selectedOutputId}
                />
                <OutputsCards
                  assetsById={assetsById}
                  currentHref={currentHref}
                  onCopyPath={onCopyPath}
                  onSelectOutput={(outputId) => updateFilters({ output: outputId })}
                  outputs={outputs}
                />
              </CardContent>
            </Card>
          </div>

          <OutputDetailPanel
            assetsById={assetsById}
            currentHref={currentHref}
            onClearSelection={() => updateFilters({ output: null })}
            onCopyPath={onCopyPath}
            output={selectedOutput}
            selectionMissing={Boolean(
              selectedOutputId &&
                !selectedOutput &&
                !selectedOutputResponse.isLoading &&
                outputsResponse.data,
            )}
          />
        </div>
      )}
    </div>
  );
}
