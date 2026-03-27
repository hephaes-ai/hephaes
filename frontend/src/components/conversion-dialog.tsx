"use client";

import * as React from "react";
import { ArrowRightLeft, CheckCircle2, LoaderCircle, TriangleAlert } from "lucide-react";

import { WorkflowStatusBadge } from "@/components/workflow-status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { toast } from "@/components/ui/sonner";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useBackendCache } from "@/hooks/use-backend";
import { useCreateConversion } from "@/hooks/use-create-conversion";
import {
  buildConversionPayload,
  createDefaultFormState,
  formatMappingSummary,
  PARQUET_COMPRESSION_OPTIONS,
  parseCustomMapping,
  RESAMPLE_METHOD_OPTIONS,
  SummaryField,
  TFRECORD_COMPRESSION_OPTIONS,
  type ConversionFormState,
  type ParquetCompression,
  type TFRecordCompression,
} from "@/lib/conversion-workflow";
import {
  getConversion,
  type AssetSummary,
  type ConversionDetail,
  type ResampleMethod,
} from "@/lib/api";
import { formatDateTime, formatSentenceCase, getWorkflowStatusClasses, isWorkflowActiveStatus } from "@/lib/format";
import { AppLink, useAppPathname, useAppSearchParams } from "@/lib/app-routing";
import { buildJobDetailHref } from "@/lib/navigation";
import { buildOutputsHref } from "@/lib/outputs";

export function ConversionDialog({
  assets,
  onOpenChange,
  open,
}: {
  assets: AssetSummary[];
  onOpenChange: (open: boolean) => void;
  open: boolean;
}) {
  const pathname = useAppPathname();
  const searchParams = useAppSearchParams();
  const {
    revalidateAssetDetail,
    revalidateConversionDetail,
    revalidateConversions,
    revalidateJobs,
    revalidateOutputs,
  } = useBackendCache();
  const { isSubmitting, submit: submitConversion } = useCreateConversion();
  const [formState, setFormState] = React.useState<ConversionFormState>(createDefaultFormState);
  const [createdConversion, setCreatedConversion] = React.useState<ConversionDetail | null>(null);
  const [requestMessage, setRequestMessage] = React.useState<{
    description?: string;
    title: string;
    tone: "error" | "info";
  } | null>(null);

  const unindexedAssets = assets.filter((asset) => asset.indexing_status !== "indexed");
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
  const submitDisabled =
    assets.length === 0 ||
    isSubmitting ||
    unindexedAssets.length > 0 ||
    Boolean(parsedCustomMapping.error) ||
    Boolean(resampleError);
  const currentHref = React.useMemo(() => {
    const query = searchParams.toString();
    return query ? `${pathname}?${query}` : pathname;
  }, [pathname, searchParams]);

  React.useEffect(() => {
    if (open) {
      return;
    }

    setFormState(createDefaultFormState());
    setCreatedConversion(null);
    setRequestMessage(null);
  }, [open]);

  React.useEffect(() => {
    if (!open || !createdConversion) {
      return;
    }

    if (
      !isWorkflowActiveStatus(createdConversion.status) &&
      !isWorkflowActiveStatus(createdConversion.job.status)
    ) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void (async () => {
        try {
          const refreshedConversion = await getConversion(createdConversion.id);
          setCreatedConversion(refreshedConversion);
          await Promise.all([
            ...assets.map((asset) => revalidateAssetDetail(asset.id)),
            revalidateConversionDetail(refreshedConversion.id),
            revalidateConversions(),
            revalidateJobs(),
            revalidateOutputs(),
          ]);
        } catch {
          // Keep the last known status visible if polling fails briefly.
        }
      })();
    }, 1500);

    return () => window.clearInterval(intervalId);
  }, [
    assets,
    createdConversion,
    open,
    revalidateAssetDetail,
    revalidateConversionDetail,
    revalidateConversions,
    revalidateJobs,
    revalidateOutputs,
  ]);

  function updateFormState(updater: (current: ConversionFormState) => ConversionFormState) {
    setFormState((current) => updater(current));
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen && isSubmitting) {
      return;
    }

    onOpenChange(nextOpen);
  }

  function resetForAnotherConversion() {
    setCreatedConversion(null);
    setRequestMessage(null);
    setFormState(createDefaultFormState());
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (submitDisabled) {
      return;
    }

    setRequestMessage(null);

    const payload = buildConversionPayload(assets, formState);
    const result = await submitConversion(payload, assets);

    if (result.conversion) {
      setCreatedConversion(result.conversion);
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

  const visibleAssetPreview = assets.slice(0, 5);
  const hiddenAssetCount = Math.max(assets.length - visibleAssetPreview.length, 0);
  const formatLabel = formState.output.format === "parquet" ? "Parquet" : "TFRecord";
  const compressionLabel =
    formState.output.format === "parquet"
      ? formState.output.parquetCompression
      : formState.output.tfrecordCompression;

  return (
    <Dialog onOpenChange={handleOpenChange} open={open}>
      <DialogContent className="max-h-[90vh] overflow-y-auto p-0" showCloseButton={!isSubmitting}>
        <DialogHeader className="border-b px-5 py-4 sm:px-6">
          <DialogTitle className="flex items-center gap-2">
            <ArrowRightLeft className="size-4" />
            Convert assets
          </DialogTitle>
          <DialogDescription>
            Choose an output format, review the selected assets, and submit a conversion request to the backend.
          </DialogDescription>
        </DialogHeader>

        {createdConversion ? (
          <div className="space-y-4 px-5 py-5 sm:px-6">
            <Alert className={getWorkflowStatusClasses(createdConversion.status)}>
              <CheckCircle2 className="size-4" />
              <AlertTitle>Conversion created</AlertTitle>
              <AlertDescription>
                The backend created conversion <span className="font-mono text-xs">{createdConversion.id}</span> with
                status {createdConversion.status}.
              </AlertDescription>
            </Alert>

            <Card>
              <CardHeader>
                <CardTitle>Conversion status</CardTitle>
                <CardDescription>Initial handoff from the backend-managed conversion workflow.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <dl className="grid gap-4 sm:grid-cols-2">
                  <SummaryField label="Conversion status" value={<WorkflowStatusBadge status={createdConversion.status} />} />
                  <SummaryField label="Job status" value={<WorkflowStatusBadge status={createdConversion.job.status} />} />
                  <SummaryField label="Created" value={formatDateTime(createdConversion.created_at)} />
                  <SummaryField
                    label="Job ID"
                    value={<span className="break-all font-mono text-xs">{createdConversion.job_id}</span>}
                  />
                  <div className="space-y-1 sm:col-span-2">
                    <dt className="text-xs uppercase tracking-wide text-muted-foreground">Output path</dt>
                    <dd className="break-all text-sm font-medium text-foreground">
                      {createdConversion.output_path ?? "Not available yet"}
                    </dd>
                  </div>
                  <div className="space-y-1 sm:col-span-2">
                    <dt className="text-xs uppercase tracking-wide text-muted-foreground">Selected assets</dt>
                    <dd className="text-sm font-medium text-foreground">
                      {createdConversion.asset_ids.length} asset{createdConversion.asset_ids.length === 1 ? "" : "s"}
                    </dd>
                  </div>
                </dl>

                {createdConversion.error_message ? (
                  <Alert variant="destructive">
                    <TriangleAlert className="size-4" />
                    <AlertTitle>Execution error</AlertTitle>
                    <AlertDescription>{createdConversion.error_message}</AlertDescription>
                  </Alert>
                ) : null}

                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Output files</p>
                  {createdConversion.output_files.length > 0 ? (
                    <div className="space-y-2">
                      {createdConversion.output_files.map((outputFile) => (
                        <div
                          key={outputFile}
                          className="rounded-lg border bg-muted/20 px-3 py-2 text-sm text-foreground break-all"
                        >
                          {outputFile}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Output files have not been reported yet. The linked job status above will update while this dialog
                      stays open.
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>

            <DialogFooter>
              <Button onClick={resetForAnotherConversion} type="button" variant="outline">
                New conversion
              </Button>
              <Button asChild type="button" variant="outline">
                <AppLink href={buildJobDetailHref(createdConversion.job_id, currentHref)}>
                  Open job
                </AppLink>
              </Button>
              <Button asChild type="button" variant="outline">
                <AppLink href={buildOutputsHref({ conversionId: createdConversion.id })}>View outputs</AppLink>
              </Button>
              <Button onClick={() => onOpenChange(false)} type="button">
                Done
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <form className="space-y-4 px-5 py-5 sm:px-6" onSubmit={onSubmit}>
            {requestMessage ? (
              <Alert className={requestMessage.tone === "info" ? "border-border bg-card" : ""} variant="destructive">
                <TriangleAlert className="size-4" />
                <AlertTitle>{requestMessage.title}</AlertTitle>
                {requestMessage.description ? (
                  <AlertDescription>{requestMessage.description}</AlertDescription>
                ) : null}
              </Alert>
            ) : null}

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
                            <Label
                              className="text-xs uppercase tracking-wide text-muted-foreground"
                              htmlFor="resample-method"
                            >
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
                          <Label
                            className="text-xs uppercase tracking-wide text-muted-foreground"
                            htmlFor="custom-mapping"
                          >
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
                      {visibleAssetPreview.map((asset) => (
                        <div
                          key={asset.id}
                          className="flex items-center justify-between gap-3 rounded-lg border bg-muted/20 px-3 py-2"
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-foreground">{asset.file_name}</p>
                            <p className="truncate text-xs text-muted-foreground">{asset.file_type.toUpperCase()}</p>
                          </div>
                          <Badge
                            className={asset.indexing_status === "indexed" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200" : ""}
                            variant={asset.indexing_status === "indexed" ? "outline" : "secondary"}
                          >
                            {formatSentenceCase(asset.indexing_status)}
                          </Badge>
                        </div>
                      ))}
                      {hiddenAssetCount > 0 ? (
                        <p className="text-sm text-muted-foreground">
                          +{hiddenAssetCount} more asset{hiddenAssetCount === 1 ? "" : "s"} selected
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

            <DialogFooter>
              <Button disabled={isSubmitting} onClick={() => onOpenChange(false)} type="button" variant="ghost">
                Cancel
              </Button>
              <Button disabled={submitDisabled} type="submit">
                {isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : null}
                {isSubmitting ? "Submitting..." : "Start conversion"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
