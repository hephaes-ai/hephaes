"use client";

import * as React from "react";
import { ArrowLeft, ArrowRight, ArrowRightLeft, CheckCircle2, LoaderCircle, TriangleAlert } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { WorkflowStatusBadge } from "@/components/workflow-status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { toast } from "@/components/ui/sonner";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useAssets, useBackendCache, useConversion } from "@/hooks/use-backend";
import {
  AppLink as Link,
  useAppPathname as usePathname,
  useAppRouter as useRouter,
  useAppSearchParams as useSearchParams,
} from "@/lib/app-routing";
import { useCreateConversion } from "@/hooks/use-create-conversion";
import {
  BackendApiError,
  getErrorMessage,
  type ConversionDetail,
  type ResampleMethod,
} from "@/lib/api";
import {
  formatDateTime,
  formatSentenceCase,
  getWorkflowStatusClasses,
  isWorkflowActiveStatus,
} from "@/lib/format";
import {
  buildConversionPayload,
  createDefaultFormState,
  formatMappingSummary,
  parseCustomMapping,
  PARQUET_COMPRESSION_OPTIONS,
  RESAMPLE_METHOD_OPTIONS,
  SummaryField,
  TFRECORD_COMPRESSION_OPTIONS,
  type ConversionFormState,
  type ParquetCompression,
  type TFRecordCompression,
} from "@/lib/conversion-workflow";
import { buildConversionHref, buildJobDetailHref, resolveReturnHref } from "@/lib/navigation";
import { buildOutputsHref } from "@/lib/outputs";

function parseAssetIds(rawAssetIds: string | null | undefined) {
  return Array.from(
    new Set(
      (rawAssetIds ?? "")
        .split(",")
        .map((assetId) => assetId.trim())
        .filter(Boolean),
    ),
  );
}

function ConversionPageSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <div className="h-8 w-40 rounded bg-muted" />
              <div className="h-5 w-28 rounded-full bg-muted" />
            </div>
            <div className="h-5 w-full max-w-3xl rounded bg-muted" />
          </div>
          <div className="h-9 w-24 rounded bg-muted" />
        </div>
      </div>
      <Card>
        <CardContent className="space-y-4 p-6">
          <div className="h-24 rounded-xl bg-muted" />
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(280px,0.95fr)]">
            <div className="h-[640px] rounded-xl bg-muted" />
            <div className="h-[640px] rounded-xl bg-muted" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function ConversionPageFallback() {
  return <ConversionPageSkeleton />;
}

function ConversionStatusCard({
  activeConversion,
  currentHref,
  isRefreshing,
  onNewConversion,
}: {
  activeConversion: ConversionDetail;
  currentHref: string;
  isRefreshing: boolean;
  onNewConversion: () => void;
}) {
  return (
    <div className="space-y-4">
      <Alert className={getWorkflowStatusClasses(activeConversion.status)} variant="default">
        <CheckCircle2 className="size-4" />
        <AlertTitle>Conversion created</AlertTitle>
        <AlertDescription>
          The backend created conversion <span className="font-mono text-xs">{activeConversion.id}</span> with status{" "}
          {activeConversion.status}.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle>Conversion status</CardTitle>
          <CardDescription>Initial handoff from the backend-managed conversion workflow.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <dl className="grid gap-4 sm:grid-cols-2">
            <SummaryField label="Conversion status" value={<WorkflowStatusBadge status={activeConversion.status} />} />
            <SummaryField label="Job status" value={<WorkflowStatusBadge status={activeConversion.job.status} />} />
            <SummaryField label="Created" value={formatDateTime(activeConversion.created_at)} />
            <SummaryField
              label="Job ID"
              value={<span className="break-all font-mono text-xs">{activeConversion.job_id}</span>}
            />
            <div className="space-y-1 sm:col-span-2">
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Output path</dt>
              <dd className="break-all text-sm font-medium text-foreground">
                {activeConversion.output_path ?? "Not available yet"}
              </dd>
            </div>
            <div className="space-y-1 sm:col-span-2">
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Selected assets</dt>
              <dd className="text-sm font-medium text-foreground">
                {activeConversion.asset_ids.length} asset{activeConversion.asset_ids.length === 1 ? "" : "s"}
              </dd>
            </div>
          </dl>

          {activeConversion.error_message ? (
            <Alert variant="destructive">
              <TriangleAlert className="size-4" />
              <AlertTitle>Execution error</AlertTitle>
              <AlertDescription>{activeConversion.error_message}</AlertDescription>
            </Alert>
          ) : null}

          <div className="space-y-2">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Output files</p>
            {activeConversion.output_files.length > 0 ? (
              <div className="space-y-2">
                {activeConversion.output_files.map((outputFile) => (
                  <div
                    key={outputFile}
                    className="break-all rounded-lg border bg-muted/20 px-3 py-2 text-sm text-foreground"
                  >
                    {outputFile}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Output files have not been reported yet. The linked job status above will update while this page stays
                open.
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button disabled={isRefreshing} onClick={onNewConversion} type="button" variant="outline">
              New conversion
            </Button>
            <Button asChild type="button" variant="outline">
              <Link href={buildJobDetailHref(activeConversion.job_id, currentHref)}>
                Open job
                <ArrowRight className="size-3.5" />
              </Link>
            </Button>
            <Button asChild type="button" variant="outline">
              <Link href={buildOutputsHref({ conversionId: activeConversion.id })}>View outputs</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function ConversionPage() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    revalidateAssetDetail,
    revalidateConversionDetail,
    revalidateConversions,
    revalidateJobs,
    revalidateOutputs,
  } = useBackendCache();
  const { isSubmitting, submit: submitConversion } = useCreateConversion();
  const assetsResponse = useAssets();
  const [formState, setFormState] = React.useState<ConversionFormState>(createDefaultFormState);
  const [createdConversion, setCreatedConversion] = React.useState<ConversionDetail | null>(null);
  const [requestMessage, setRequestMessage] = React.useState<{
    description?: string;
    title: string;
    tone: "error" | "info";
  } | null>(null);

  const assetIds = React.useMemo(() => parseAssetIds(searchParams.get("asset_ids")), [searchParams]);
  const assetIdSet = React.useMemo(() => new Set(assetIds), [assetIds]);
  const queryConversionId = searchParams.get("conversion_id")?.trim() ?? "";
  const returnHref = resolveReturnHref(searchParams.get("from"), "/inventory");
  const currentHref = React.useMemo(() => {
    const query = searchParams.toString();
    return query ? `${pathname}?${query}` : pathname;
  }, [pathname, searchParams]);
  const activeConversionId = createdConversion?.id ?? queryConversionId;
  const conversionResponse = useConversion(activeConversionId ?? "");

  const assets = React.useMemo(() => assetsResponse.data ?? [], [assetsResponse.data]);
  const selectedAssets = React.useMemo(
    () => assets.filter((asset) => assetIdSet.has(asset.id)),
    [assetIdSet, assets],
  );
  const unindexedAssets = selectedAssets.filter((asset) => asset.indexing_status !== "indexed");
  const missingAssetCount = Math.max(assetIds.length - selectedAssets.length, 0);
  const parsedCustomMapping = React.useMemo(() => {
    if (formState.mapping.mode !== "custom") {
      return {
        error: null,
        value: null,
      } as const;
    }

    return parseCustomMapping(formState.mapping.customJson);
  }, [formState.mapping.customJson, formState.mapping.mode]);
  const parsedResampleFrequency = Number(formState.resample.freqHz);
  const resampleError =
    formState.resample.enabled &&
    (!Number.isFinite(parsedResampleFrequency) || parsedResampleFrequency <= 0)
      ? "Resample frequency must be a number greater than zero."
      : null;
  const activeConversion = createdConversion ?? conversionResponse.data ?? null;
  const submitDisabled =
    selectedAssets.length === 0 ||
    isSubmitting ||
    unindexedAssets.length > 0 ||
    Boolean(parsedCustomMapping.error) ||
    Boolean(resampleError);
  const isPendingConversionRoute = Boolean(queryConversionId) && !createdConversion && conversionResponse.isLoading;

  React.useEffect(() => {
    if (!activeConversion) {
      return;
    }

    if (
      !isWorkflowActiveStatus(activeConversion.status) &&
      !isWorkflowActiveStatus(activeConversion.job.status)
    ) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void (async () => {
        try {
          if (activeConversion.id) {
            await conversionResponse.mutate();
            await Promise.all([
              ...selectedAssets.map((asset) => revalidateAssetDetail(asset.id)),
              revalidateConversionDetail(activeConversion.id),
              revalidateConversions(),
              revalidateJobs(),
              revalidateOutputs(),
            ]);
          }
        } catch {
          // Keep the last known status visible if polling fails briefly.
        }
      })();
    }, 1500);

    return () => window.clearInterval(intervalId);
  }, [
    activeConversion,
    conversionResponse,
    revalidateAssetDetail,
    revalidateConversionDetail,
    revalidateConversions,
    revalidateJobs,
    revalidateOutputs,
    selectedAssets,
  ]);

  function updateFormState(updater: (current: ConversionFormState) => ConversionFormState) {
    setFormState((current) => updater(current));
  }

  function resetForAnotherConversion() {
    setCreatedConversion(null);
    setRequestMessage(null);
    setFormState(createDefaultFormState());

    const nextHref = buildConversionHref({
      assetIds,
      from: searchParams.get("from"),
    });

    React.startTransition(() => {
      router.replace(nextHref, { scroll: false });
    });
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (submitDisabled) {
      return;
    }

    setRequestMessage(null);

    const payload = buildConversionPayload(selectedAssets, formState);
    const result = await submitConversion(payload, selectedAssets);

    if (result.conversion) {
      setCreatedConversion(result.conversion);
      const nextHref = buildConversionHref({
        assetIds,
        conversionId: result.conversion.id,
        from: searchParams.get("from"),
      });

      React.startTransition(() => {
        router.replace(nextHref, { scroll: false });
      });
    }

    if (result.notice) {
      setRequestMessage({
        description: result.notice.description,
        title: result.notice.title,
        tone: "error",
      });
      toast.error("Conversion failed", {
        description: result.notice.description,
      });
    }
  }

  const formatLabel = formState.output.format === "parquet" ? "Parquet" : "TFRecord";
  const compressionLabel =
    formState.output.format === "parquet"
      ? formState.output.parquetCompression
      : formState.output.tfrecordCompression;
  const hasSelectionContext = assetIds.length > 0;
  const isStatusMode = Boolean(activeConversion);

  if (assetsResponse.isLoading && !assetsResponse.data && !isStatusMode) {
    return <ConversionPageSkeleton />;
  }

  if (isPendingConversionRoute) {
    return <ConversionPageSkeleton />;
  }

  if (queryConversionId && conversionResponse.error) {
    const isMissingConversion =
      conversionResponse.error instanceof BackendApiError && conversionResponse.error.status === 404;

    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <Alert variant="destructive">
          <AlertTitle>{isMissingConversion ? "Conversion not found" : "Could not load conversion"}</AlertTitle>
          <AlertDescription>{getErrorMessage(conversionResponse.error)}</AlertDescription>
        </Alert>
        {!isMissingConversion ? (
          <div>
            <Button onClick={() => void conversionResponse.mutate()} type="button" variant="outline">
              Try again
            </Button>
          </div>
        ) : null}
      </div>
    );
  }

  if (assetsResponse.error && !isStatusMode) {
    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <Alert variant="destructive">
          <AlertTitle>Could not load assets</AlertTitle>
          <AlertDescription>{getErrorMessage(assetsResponse.error)}</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (!isStatusMode && !hasSelectionContext) {
    return (
      <div className="space-y-6">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <EmptyState
          action={
            <Button asChild variant="outline">
              <Link href="/inventory">Go to inventory</Link>
            </Button>
          }
          description="Open this page from inventory or asset detail so we know which assets to convert."
          title="No assets selected"
        />
      </div>
    );
  }

  if (!isStatusMode && hasSelectionContext && missingAssetCount > 0) {
    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <Alert variant="destructive">
          <TriangleAlert className="size-4" />
          <AlertTitle>Selected assets are no longer available</AlertTitle>
          <AlertDescription>
            {missingAssetCount} selected asset{missingAssetCount === 1 ? "" : "s"} could not be resolved from the
            current inventory. Go back and choose a fresh selection.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Button asChild size="sm" variant="ghost">
        <Link href={returnHref}>
          <ArrowLeft className="size-4" />
          Back
        </Link>
      </Button>

      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
                <ArrowRightLeft className="size-5" />
                Convert assets
              </h1>
              <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                {isStatusMode ? "Status" : `${selectedAssets.length} selected`}
              </span>
            </div>
            <p className="max-w-3xl text-sm text-muted-foreground">
              Configure the conversion, submit it to the backend, and keep the resulting workflow on this page.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {isStatusMode ? (
              <Button
                disabled={isSubmitting}
                onClick={resetForAnotherConversion}
                size="sm"
                type="button"
                variant="outline"
              >
                New conversion
              </Button>
            ) : null}
          </div>
        </div>
      </section>

      {requestMessage ? (
        <Alert variant={requestMessage.tone === "error" ? "destructive" : "default"}>
          <TriangleAlert className="size-4" />
          <AlertTitle>{requestMessage.title}</AlertTitle>
          {requestMessage.description ? <AlertDescription>{requestMessage.description}</AlertDescription> : null}
        </Alert>
      ) : null}

      {isStatusMode && activeConversion ? (
        <ConversionStatusCard
          activeConversion={activeConversion}
          currentHref={currentHref}
          isRefreshing={isSubmitting}
          onNewConversion={resetForAnotherConversion}
        />
      ) : (
        <form className="space-y-4" onSubmit={onSubmit}>
          {unindexedAssets.length > 0 ? (
            <Alert variant="destructive">
              <TriangleAlert className="size-4" />
              <AlertTitle>Index assets before converting</AlertTitle>
              <AlertDescription>
                {unindexedAssets
                  .slice(0, 3)
                  .map((asset) => asset.file_name)
                  .join(", ")}
                {unindexedAssets.length > 3 ? ` and ${unindexedAssets.length - 3} more` : ""} must finish indexing
                before this conversion can be submitted.
              </AlertDescription>
            </Alert>
          ) : null}

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(280px,0.95fr)]">
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Output format</CardTitle>
                  <CardDescription>Choose the backend output type and only the relevant options will appear.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex flex-wrap gap-2">
                    {(["parquet", "tfrecord"] as const).map((format) => (
                      <Button
                        key={format}
                        onClick={() =>
                          updateFormState((current) => ({
                            ...current,
                            output: {
                              ...current.output,
                              format,
                            },
                          }))
                        }
                        size="sm"
                        type="button"
                        variant={formState.output.format === format ? "secondary" : "outline"}
                      >
                        {format === "parquet" ? "Parquet" : "TFRecord"}
                      </Button>
                    ))}
                  </div>

                  {formState.output.format === "parquet" ? (
                    <div className="space-y-2">
                      <Label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="parquet-compression">
                        Compression
                      </Label>
                      <NativeSelect
                        id="parquet-compression"
                        onChange={(event) =>
                          updateFormState((current) => ({
                            ...current,
                            output: {
                              ...current.output,
                              parquetCompression: event.target.value as ParquetCompression,
                            },
                          }))
                        }
                        value={formState.output.parquetCompression}
                      >
                        {PARQUET_COMPRESSION_OPTIONS.map((compression) => (
                          <option key={compression} value={compression}>
                            {formatSentenceCase(compression)}
                          </option>
                        ))}
                      </NativeSelect>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="tfrecord-compression">
                          Compression
                        </Label>
                        <NativeSelect
                          id="tfrecord-compression"
                          onChange={(event) =>
                            updateFormState((current) => ({
                              ...current,
                              output: {
                                ...current.output,
                                tfrecordCompression: event.target.value as TFRecordCompression,
                              },
                            }))
                          }
                          value={formState.output.tfrecordCompression}
                        >
                          {TFRECORD_COMPRESSION_OPTIONS.map((compression) => (
                            <option key={compression} value={compression}>
                              {formatSentenceCase(compression)}
                            </option>
                          ))}
                        </NativeSelect>
                      </div>

                      <div className="rounded-lg border bg-muted/20 px-3 py-3 text-sm text-muted-foreground">
                        TFRecord uses the backend defaults for payload encoding (
                        <span className="font-medium text-foreground">typed features</span>) and null encoding (
                        <span className="font-medium text-foreground">presence flag</span>).
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Options</CardTitle>
                  <CardDescription>Keep the first cut minimal, but structured enough to grow later.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="flex items-start justify-between gap-4 rounded-lg border bg-muted/20 px-3 py-3">
                    <div className="space-y-1">
                      <Label className="text-sm font-medium text-foreground" htmlFor="write-manifest">
                        Write manifest
                      </Label>
                      <p className="text-sm text-muted-foreground">
                        Ask the backend to include a manifest alongside the conversion output.
                      </p>
                    </div>
                    <Switch
                      checked={formState.writeManifest}
                      id="write-manifest"
                      onCheckedChange={(checked) =>
                        updateFormState((current) => ({
                          ...current,
                          writeManifest: checked,
                        }))
                      }
                    />
                  </div>

                  <div className="space-y-3 rounded-lg border bg-muted/20 px-3 py-3">
                    <div className="flex items-start justify-between gap-4">
                      <div className="space-y-1">
                        <Label className="text-sm font-medium text-foreground" htmlFor="enable-resample">
                          Resample streams
                        </Label>
                        <p className="text-sm text-muted-foreground">
                          Optionally resample data before writing the converted output.
                        </p>
                      </div>
                      <Switch
                        checked={formState.resample.enabled}
                        id="enable-resample"
                        onCheckedChange={(checked) =>
                          updateFormState((current) => ({
                            ...current,
                            resample: {
                              ...current.resample,
                              enabled: checked,
                            },
                          }))
                        }
                      />
                    </div>

                    {formState.resample.enabled ? (
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="space-y-2">
                          <Label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="resample-method">
                            Method
                          </Label>
                          <NativeSelect
                            id="resample-method"
                            onChange={(event) =>
                              updateFormState((current) => ({
                                ...current,
                                resample: {
                                  ...current.resample,
                                  method: event.target.value as ResampleMethod,
                                },
                              }))
                            }
                            value={formState.resample.method}
                          >
                            {RESAMPLE_METHOD_OPTIONS.map((method) => (
                              <option key={method} value={method}>
                                {formatSentenceCase(method)}
                              </option>
                            ))}
                          </NativeSelect>
                        </div>
                        <div className="space-y-2">
                          <Label
                            className="text-xs uppercase tracking-wide text-muted-foreground"
                            htmlFor="resample-frequency"
                          >
                            Frequency (Hz)
                          </Label>
                          <Input
                            id="resample-frequency"
                            min="0.1"
                            onChange={(event) =>
                              updateFormState((current) => ({
                                ...current,
                                resample: {
                                  ...current.resample,
                                  freqHz: event.target.value,
                                },
                              }))
                            }
                            placeholder="10"
                            step="0.1"
                            type="number"
                            value={formState.resample.freqHz}
                          />
                        </div>
                      </div>
                    ) : null}

                    {resampleError ? <p className="text-sm text-destructive">{resampleError}</p> : null}
                  </div>

                  <div className="space-y-3 rounded-lg border bg-muted/20 px-3 py-3">
                    <div className="space-y-1">
                      <Label className="text-sm font-medium text-foreground">Mapping</Label>
                      <p className="text-sm text-muted-foreground">
                        Use automatic topic mapping now or provide a raw JSON mapping object.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {(["auto", "custom"] as const).map((mode) => (
                        <Button
                          key={mode}
                          onClick={() =>
                            updateFormState((current) => ({
                              ...current,
                              mapping: {
                                ...current.mapping,
                                mode,
                              },
                            }))
                          }
                          size="sm"
                          type="button"
                          variant={formState.mapping.mode === mode ? "secondary" : "outline"}
                        >
                          {mode === "auto" ? "Automatic" : "Custom JSON"}
                        </Button>
                      ))}
                    </div>

                    {formState.mapping.mode === "custom" ? (
                      <div className="space-y-2">
                        <Label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="custom-mapping">
                          Mapping JSON
                        </Label>
                        <Textarea
                          id="custom-mapping"
                          onChange={(event) =>
                            updateFormState((current) => ({
                              ...current,
                              mapping: {
                                ...current.mapping,
                                customJson: event.target.value,
                              },
                            }))
                          }
                          placeholder='{"camera_frame": ["/camera/image_raw"], "imu_reading": ["/imu/data"]}'
                          value={formState.mapping.customJson}
                        />
                        {parsedCustomMapping.error ? (
                          <p className="text-sm text-destructive">{parsedCustomMapping.error}</p>
                        ) : (
                          <p className="text-sm text-muted-foreground">
                            Provide a JSON object that maps output field names to one or more topic names.
                          </p>
                        )}
                      </div>
                    ) : null}
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Review</CardTitle>
                <CardDescription>Confirm the assets and settings that will be sent to the backend.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Selected assets</p>
                  <div className="space-y-2">
                    {selectedAssets.slice(0, 5).map((asset) => (
                      <div
                        key={asset.id}
                        className="flex items-center justify-between gap-3 rounded-lg border bg-muted/20 px-3 py-2"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-foreground">{asset.file_name}</p>
                          <p className="truncate text-xs text-muted-foreground">{asset.file_type.toUpperCase()}</p>
                        </div>
                        <Badge
                          className={
                            asset.indexing_status === "indexed"
                              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200"
                              : ""
                          }
                          variant={asset.indexing_status === "indexed" ? "outline" : "secondary"}
                        >
                          {formatSentenceCase(asset.indexing_status)}
                        </Badge>
                      </div>
                    ))}
                    {selectedAssets.length > 5 ? (
                      <p className="text-sm text-muted-foreground">
                        +{selectedAssets.length - 5} more asset{selectedAssets.length - 5 === 1 ? "" : "s"} selected
                      </p>
                    ) : null}
                  </div>
                </div>

                <dl className="grid gap-4">
                  <SummaryField label="Format" value={formatLabel} />
                  <SummaryField label="Compression" value={formatSentenceCase(compressionLabel)} />
                  <SummaryField label="Mapping" value={formatMappingSummary(formState.mapping.mode)} />
                  <SummaryField
                    label="Resampling"
                    value={
                      formState.resample.enabled
                        ? `${formState.resample.method} at ${formState.resample.freqHz || "?"} Hz`
                        : "Disabled"
                    }
                  />
                  <SummaryField label="Manifest" value={formState.writeManifest ? "Write manifest" : "Skip manifest"} />
                </dl>
              </CardContent>
            </Card>
          </div>

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button disabled={isSubmitting} onClick={() => router.push(returnHref)} type="button" variant="ghost">
              Cancel
            </Button>
            <Button disabled={submitDisabled} type="submit">
              {isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : null}
              {isSubmitting ? "Submitting..." : "Start conversion"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
