"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, Copy, Database, ListFilter, RefreshCw, Sparkles } from "lucide-react";

import { useFeedback } from "@/components/feedback-provider";
import {
  getDefaultOutputActionPrefill,
  OutputActionDialog,
  type OutputActionDialogPrefill,
} from "@/components/output-action-dialog";
import { WorkflowStatusBadge } from "@/components/workflow-status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
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
import { useAssets, useOutput, useOutputActions, useOutputs } from "@/hooks/use-backend";
import type {
  AssetSummary,
  OutputActionDetail,
  OutputAvailability,
  OutputDetail,
  OutputFormat,
  OutputsQuery,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/api";
import {
  formatDateTime,
  formatOutputActionType,
  formatOutputAvailability,
  formatOutputFormat,
  formatSentenceCase,
  isWorkflowActiveStatus,
} from "@/lib/format";

const OUTPUT_FORMAT_OPTIONS: OutputFormat[] = ["parquet", "tfrecord", "json", "unknown"];
const OUTPUT_AVAILABILITY_OPTIONS: OutputAvailability[] = ["ready"];
const OUTPUT_PRESET_OPTIONS = [
  {
    description: "Surface finished Parquet and TFRecord datasets first.",
    label: "Ready datasets",
    value: "ready_datasets",
  },
  {
    description: "Show outputs with queued or running compute work.",
    label: "Active compute",
    value: "active_compute",
  },
  {
    description: "Focus on JSON sidecars such as manifests and summaries.",
    label: "JSON sidecars",
    value: "json_sidecars",
  },
] as const;
type OutputPreset = (typeof OUTPUT_PRESET_OPTIONS)[number]["value"];

interface OutputPreviewFact {
  label: string;
  value: string;
}

interface OutputPreviewMapping {
  sourceTopics: string[];
  targetField: string;
}

interface OutputPreviewModel {
  description: string;
  facts: OutputPreviewFact[];
  mappings: OutputPreviewMapping[];
  notes: string[];
  title: string;
}

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

function parseOutputSelection(value: string | null) {
  return Array.from(
    new Set(
      (value ?? "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getNestedRecord(
  object: Record<string, unknown>,
  key: string,
): Record<string, unknown> | null {
  const value = object[key];
  return isRecord(value) ? value : null;
}

function getStringValue(value: unknown) {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function getBooleanValue(value: unknown) {
  return typeof value === "boolean" ? value : null;
}

function getNumberValue(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatPreviewValue(value: string | null, fallback = "Not configured") {
  return value ?? fallback;
}

function formatResampleSummary(resampleConfig: Record<string, unknown> | null) {
  if (!resampleConfig) {
    return "Original cadence";
  }

  const method = getStringValue(resampleConfig.method);
  const frequency = getNumberValue(resampleConfig.freq_hz);

  if (!method && frequency === null) {
    return "Configured";
  }

  if (!method) {
    return `${frequency} Hz`;
  }

  if (frequency === null) {
    return formatSentenceCase(method);
  }

  return `${formatSentenceCase(method)} at ${frequency} Hz`;
}

function getPreviewMappings(config: Record<string, unknown>): OutputPreviewMapping[] {
  if (!isRecord(config.mapping)) {
    return [];
  }

  return Object.entries(config.mapping).flatMap(([targetField, sourceTopics]) => {
    if (!Array.isArray(sourceTopics)) {
      return [];
    }

    const normalizedSourceTopics = sourceTopics.filter(
      (sourceTopic): sourceTopic is string =>
        typeof sourceTopic === "string" && sourceTopic.trim().length > 0,
    );

    if (!targetField.trim() || normalizedSourceTopics.length === 0) {
      return [];
    }

    return [
      {
        sourceTopics: normalizedSourceTopics,
        targetField,
      },
    ];
  });
}

function getJsonArtifactRole(fileName: string) {
  const normalizedFileName = fileName.toLowerCase();

  if (normalizedFileName.includes("manifest")) {
    return "Manifest sidecar";
  }

  if (normalizedFileName.includes("schema")) {
    return "Schema sidecar";
  }

  if (normalizedFileName.includes("tag")) {
    return "Tag output";
  }

  return "JSON artifact";
}

function countSiblingDatasets(output: OutputDetail) {
  return output.sibling_output_files.filter(
    (siblingOutput) =>
      siblingOutput !== output.output_file &&
      /\.(parquet|tfrecord|tfrecords)$/i.test(siblingOutput),
  ).length;
}

function buildOutputPreview(output: OutputDetail, actionCount: number): OutputPreviewModel {
  const outputConfig = getNestedRecord(output.config, "output");
  const resampleConfig = getNestedRecord(output.config, "resample");
  const mappings = getPreviewMappings(output.config);
  const writeManifest = getBooleanValue(output.config.write_manifest);
  const siblingDatasetCount = countSiblingDatasets(output);

  if (output.format === "parquet") {
    return {
      description: "Columnar dataset summary for analytics-style review and downstream compute.",
      facts: [
        {
          label: "Compression",
          value: formatPreviewValue(
            getStringValue(outputConfig?.compression)
              ? formatSentenceCase(getStringValue(outputConfig?.compression) as string)
              : null,
            "Default",
          ),
        },
        {
          label: "Mapped fields",
          value: String(mappings.length || 0),
        },
        {
          label: "Manifest",
          value:
            writeManifest === null ? "Not specified" : writeManifest ? "Written" : "Skipped",
        },
        {
          label: "Resample",
          value: formatResampleSummary(resampleConfig),
        },
      ],
      mappings,
      notes: [
        "Parquet outputs are a good fit for quick tabular inspection, filtering, and batch analytics.",
        siblingDatasetCount > 0
          ? `This conversion also reported ${formatCount(siblingDatasetCount, "sibling dataset")} alongside the selected file.`
          : "No additional dataset siblings were reported for this conversion.",
      ],
      title: "Parquet preview",
    };
  }

  if (output.format === "tfrecord") {
    return {
      description: "Sequential record summary tailored for ML ingestion and sample-based compute.",
      facts: [
        {
          label: "Compression",
          value: formatPreviewValue(
            getStringValue(outputConfig?.compression)
              ? formatSentenceCase(getStringValue(outputConfig?.compression) as string)
              : null,
            "Default",
          ),
        },
        {
          label: "Payload encoding",
          value: formatPreviewValue(
            getStringValue(outputConfig?.payload_encoding)
              ? formatSentenceCase(getStringValue(outputConfig?.payload_encoding) as string)
              : null,
          ),
        },
        {
          label: "Null encoding",
          value: formatPreviewValue(
            getStringValue(outputConfig?.null_encoding)
              ? formatSentenceCase(getStringValue(outputConfig?.null_encoding) as string)
              : null,
          ),
        },
        {
          label: "Mapped fields",
          value: String(mappings.length || 0),
        },
      ],
      mappings,
      notes: [
        "TFRecord outputs are optimized for sequential readers and model-serving style pipelines.",
        actionCount > 0
          ? `This output already has ${formatCount(actionCount, "compute action")} attached to it.`
          : "No compute actions have been launched from this TFRecord yet.",
      ],
      title: "TFRecord preview",
    };
  }

  if (output.format === "json") {
    return {
      description: "JSON sidecar summary based on file naming and conversion siblings.",
      facts: [
        {
          label: "Artifact role",
          value: getJsonArtifactRole(output.file_name),
        },
        {
          label: "Sibling datasets",
          value: String(siblingDatasetCount),
        },
        {
          label: "Mapped fields",
          value: String(mappings.length || 0),
        },
        {
          label: "Compute actions",
          value: String(actionCount),
        },
      ],
      mappings,
      notes: [
        siblingDatasetCount > 0
          ? "This JSON file appears to accompany one or more dataset artifacts from the same conversion."
          : "No dataset siblings were reported, so this may be the primary artifact for the run.",
        "JSON outputs are useful as lightweight manifests, summaries, or intermediate compute results.",
      ],
      title: "JSON preview",
    };
  }

  return {
    description: "Fallback summary for derived artifacts that do not map to a richer preview yet.",
    facts: [
      {
        label: "Artifact role",
        value: "Derived output",
      },
      {
        label: "Mapped fields",
        value: String(mappings.length || 0),
      },
      {
        label: "Sibling files",
        value: String(output.sibling_output_files.length),
      },
      {
        label: "Compute actions",
        value: String(actionCount),
      },
    ],
    mappings,
    notes: [
      "This output type does not have a dedicated preview card yet, so the page falls back to metadata and config.",
    ],
    title: "Artifact preview",
  };
}

function parseActionPrefill(searchParams: URLSearchParams): OutputActionDialogPrefill {
  const sampleCap = searchParams.get("sample_cap")?.trim() ?? "";
  const sampleCapValue = Number(sampleCap);

  return {
    overwrite: ["1", "true", "yes"].includes(
      (searchParams.get("overwrite") ?? "").trim().toLowerCase(),
    ),
    promptTemplate: searchParams.get("prompt")?.trim() || undefined,
    sampleCap:
      sampleCap && Number.isFinite(sampleCapValue) && sampleCapValue > 0
        ? sampleCapValue
        : undefined,
    targetField: searchParams.get("target_field")?.trim() || undefined,
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

function getLatestActionsByOutput(actions: OutputActionDetail[]) {
  const latestActions = new Map<string, OutputActionDetail>();

  for (const action of actions) {
    const currentAction = latestActions.get(action.output_id);

    if (!currentAction) {
      latestActions.set(action.output_id, action);
      continue;
    }

    const currentTimestamp = new Date(currentAction.updated_at).getTime();
    const nextTimestamp = new Date(action.updated_at).getTime();

    if (nextTimestamp >= currentTimestamp) {
      latestActions.set(action.output_id, action);
    }
  }

  return latestActions;
}

function formatOutputActionSummary(action: OutputActionDetail) {
  if (action.summary_text) {
    return action.summary_text;
  }

  if (action.status === "queued") {
    return "Waiting to begin.";
  }

  if (action.status === "running") {
    return "Processing samples now.";
  }

  if (action.error_message) {
    return action.error_message;
  }

  return "No summary available yet.";
}

function OutputPreviewPanel({
  actionCount,
  output,
}: {
  actionCount: number;
  output: OutputDetail;
}) {
  const preview = buildOutputPreview(output, actionCount);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{preview.title}</CardTitle>
        <CardDescription>{preview.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-2">
          {preview.facts.map((fact) => (
            <div className="rounded-lg border bg-muted/15 px-4 py-3" key={fact.label}>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">{fact.label}</p>
              <p className="mt-1 text-sm font-medium text-foreground">{fact.value}</p>
            </div>
          ))}
        </div>

        {preview.mappings.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Mapped fields</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {preview.mappings.slice(0, 6).map((mapping) => (
                <div className="rounded-lg border bg-muted/15 px-3 py-3" key={mapping.targetField}>
                  <p className="text-sm font-medium text-foreground">{mapping.targetField}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {mapping.sourceTopics.slice(0, 2).join(", ")}
                    {mapping.sourceTopics.length > 2
                      ? ` +${mapping.sourceTopics.length - 2} more`
                      : ""}
                  </p>
                </div>
              ))}
            </div>
            {preview.mappings.length > 6 ? (
              <p className="text-xs text-muted-foreground">
                Showing the first 6 mapped fields from the stored conversion config.
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="space-y-2">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Preview notes</p>
          {preview.notes.map((note) => (
            <div className="rounded-lg border bg-muted/10 px-3 py-3 text-sm text-foreground" key={note}>
              {note}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function OutputDetailPanel({
  assetsById,
  currentHref,
  onClearSelection,
  onCopyPath,
  onCopyResultJson,
  onRunVlmTagging,
  output,
  outputActions,
  selectionMissing,
}: {
  assetsById: Map<string, AssetSummary>;
  currentHref: string;
  onClearSelection: () => void;
  onCopyPath: (output: OutputDetail) => Promise<void>;
  onCopyResultJson: (action: OutputActionDetail) => Promise<void>;
  onRunVlmTagging: (output: OutputDetail) => void;
  output: OutputDetail | null;
  outputActions: OutputActionDetail[];
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
  const latestAction = outputActions[0] ?? null;

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
            <Button onClick={() => onRunVlmTagging(output)} size="sm" type="button">
              <Sparkles className="size-3.5" />
              Run VLM tagging
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

          {latestAction ? (
            <div className="space-y-2 rounded-lg border bg-muted/15 px-3 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{formatOutputActionType(latestAction.action_type)}</Badge>
                <WorkflowStatusBadge status={latestAction.status} />
              </div>
              <p className="text-sm text-foreground">{formatOutputActionSummary(latestAction)}</p>
            </div>
          ) : null}

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

      <OutputPreviewPanel actionCount={outputActions.length} output={output} />

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

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle>Compute actions</CardTitle>
            <CardDescription>
              Track output-scoped work such as VLM tagging without leaving the outputs page.
            </CardDescription>
          </div>
          <Button onClick={() => onRunVlmTagging(output)} size="sm" type="button" variant="outline">
            <Sparkles className="size-3.5" />
            Run VLM tagging
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {outputActions.length > 0 ? (
            outputActions.map((action) => (
              <div key={action.id} className="space-y-3 rounded-xl border bg-muted/15 px-4 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 space-y-1">
                    <p className="text-sm font-medium text-foreground">
                      {formatOutputActionType(action.action_type)}
                    </p>
                    <p className="break-all font-mono text-xs text-muted-foreground">{action.id}</p>
                  </div>
                  <WorkflowStatusBadge status={action.status} />
                </div>
                <dl className="grid gap-3 sm:grid-cols-2">
                  <MetadataField label="Created" value={formatDateTime(action.created_at)} />
                  <MetadataField label="Finished" value={formatDateTime(action.finished_at)} />
                  <MetadataField label="Target field" value={action.config.target_field} />
                  <MetadataField label="Sample cap" value={action.config.sample_cap} />
                </dl>
                <p className="text-sm text-foreground">{formatOutputActionSummary(action)}</p>
                {action.output_path ? (
                  <div className="space-y-1">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Result path</p>
                    <p className="break-all text-sm text-foreground">{action.output_path}</p>
                  </div>
                ) : null}
                {action.result_json ? (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Result JSON</p>
                      <Button onClick={() => void onCopyResultJson(action)} size="sm" type="button" variant="ghost">
                        Copy JSON
                      </Button>
                    </div>
                    <pre className="overflow-x-auto rounded-lg border bg-muted/20 p-3 text-xs text-foreground">
                      {JSON.stringify(action.result_json, null, 2)}
                    </pre>
                  </div>
                ) : null}
              </div>
            ))
          ) : (
            <div className="rounded-lg border border-dashed px-4 py-8 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">No compute actions yet</p>
              <p className="mt-2">
                Launch VLM tagging here when you want to start downstream work on this output.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

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
  allVisibleSelected,
  assetsById,
  currentHref,
  latestActionsByOutput,
  onCopyPath,
  onRunVlmTagging,
  onSelectOutput,
  onToggleAllVisible,
  onToggleOutputSelection,
  outputs,
  selectedOutputIds,
  selectedOutputId,
}: {
  allVisibleSelected: boolean;
  assetsById: Map<string, AssetSummary>;
  currentHref: string;
  latestActionsByOutput: Map<string, OutputActionDetail>;
  onCopyPath: (output: OutputDetail) => Promise<void>;
  onRunVlmTagging: (output: OutputDetail) => void;
  onSelectOutput: (outputId: string) => void;
  onToggleAllVisible: () => void;
  onToggleOutputSelection: (outputId: string) => void;
  outputs: OutputDetail[];
  selectedOutputIds: Set<string>;
  selectedOutputId: string;
}) {
  const someVisibleSelected = !allVisibleSelected && outputs.some((output) => selectedOutputIds.has(output.id));

  return (
    <div className="hidden overflow-x-auto md:block">
      <Table className="min-w-[940px]">
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">
              <Checkbox
                aria-label="Select all visible outputs"
                checked={allVisibleSelected ? true : someVisibleSelected ? "indeterminate" : false}
                onCheckedChange={() => onToggleAllVisible()}
              />
            </TableHead>
            <TableHead>Output file</TableHead>
            <TableHead>Format</TableHead>
            <TableHead>Source assets</TableHead>
            <TableHead>Created</TableHead>
            <TableHead>Availability</TableHead>
            <TableHead>Latest action</TableHead>
            <TableHead className="w-56 text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {outputs.map((output) => {
            const isSelected = output.id === selectedOutputId;
            const isBatchSelected = selectedOutputIds.has(output.id);
            const latestAction = latestActionsByOutput.get(output.id) ?? null;

            return (
              <TableRow
                key={output.id}
                className={isSelected ? "bg-muted/35" : undefined}
                onClick={() => onSelectOutput(output.id)}
              >
                <TableCell>
                  <Checkbox
                    aria-label={`Select ${output.file_name}`}
                    checked={isBatchSelected}
                    onCheckedChange={() => onToggleOutputSelection(output.id)}
                    onClick={(event) => event.stopPropagation()}
                  />
                </TableCell>
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
                <TableCell>
                  {latestAction ? (
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">{formatOutputActionType(latestAction.action_type)}</Badge>
                        <WorkflowStatusBadge status={latestAction.status} />
                      </div>
                      <p className="line-clamp-2 text-xs text-muted-foreground">
                        {formatOutputActionSummary(latestAction)}
                      </p>
                    </div>
                  ) : (
                    <span className="text-sm text-muted-foreground">No actions yet</span>
                  )}
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
                    <Button
                      onClick={(event) => {
                        event.stopPropagation();
                        onRunVlmTagging(output);
                      }}
                      size="sm"
                      type="button"
                    >
                      VLM tags
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
  latestActionsByOutput,
  onCopyPath,
  onRunVlmTagging,
  onSelectOutput,
  onToggleOutputSelection,
  outputs,
  selectedOutputIds,
}: {
  assetsById: Map<string, AssetSummary>;
  currentHref: string;
  latestActionsByOutput: Map<string, OutputActionDetail>;
  onCopyPath: (output: OutputDetail) => Promise<void>;
  onRunVlmTagging: (output: OutputDetail) => void;
  onSelectOutput: (outputId: string) => void;
  onToggleOutputSelection: (outputId: string) => void;
  outputs: OutputDetail[];
  selectedOutputIds: Set<string>;
}) {
  return (
    <div className="space-y-3 md:hidden">
      {outputs.map((output) => {
        const isBatchSelected = selectedOutputIds.has(output.id);
        const latestAction = latestActionsByOutput.get(output.id) ?? null;

        return (
          <div key={output.id} className="space-y-3 rounded-xl border bg-muted/15 px-4 py-4">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <p className="font-medium text-foreground">{output.file_name}</p>
                <p className="break-all text-xs text-muted-foreground">{output.relative_path}</p>
              </div>
              <Checkbox
                aria-label={`Select ${output.file_name}`}
                checked={isBatchSelected}
                onCheckedChange={() => onToggleOutputSelection(output.id)}
              />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{formatOutputFormat(output.format)}</Badge>
              <OutputAvailabilityBadge availability={output.availability} />
              {isBatchSelected ? <Badge variant="secondary">Selected</Badge> : null}
            </div>
            {latestAction ? (
              <div className="space-y-2 rounded-lg border bg-muted/20 px-3 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{formatOutputActionType(latestAction.action_type)}</Badge>
                  <WorkflowStatusBadge status={latestAction.status} />
                </div>
                <p className="text-sm text-muted-foreground">{formatOutputActionSummary(latestAction)}</p>
              </div>
            ) : null}
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
              <Button onClick={() => onRunVlmTagging(output)} size="sm" type="button">
                VLM tags
              </Button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function OutputsPage() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { notify } = useFeedback();
  const query = React.useMemo(() => buildOutputsQuery(searchParams), [searchParams]);
  const presetValue = searchParams.get("preset")?.trim() ?? "";
  const preset = React.useMemo(
    () =>
      OUTPUT_PRESET_OPTIONS.some((option) => option.value === presetValue)
        ? (presetValue as OutputPreset)
        : null,
    [presetValue],
  );
  const outputsResponse = useOutputs(query);
  const outputActionsResponse = useOutputActions();
  const selectedOutputId = searchParams.get("output")?.trim() ?? "";
  const selectedOutputIds = React.useMemo(
    () => parseOutputSelection(searchParams.get("selection")),
    [searchParams],
  );
  const actionType = searchParams.get("action")?.trim() ?? "";
  const actionPrefill = React.useMemo(() => parseActionPrefill(searchParams), [searchParams]);
  const selectedOutputResponse = useOutput(selectedOutputId);
  const assetsResponse = useAssets();
  const baseOutputs = React.useMemo(() => outputsResponse.data ?? [], [outputsResponse.data]);
  const outputActions = React.useMemo(
    () => outputActionsResponse.data ?? [],
    [outputActionsResponse.data],
  );
  const activeActionOutputIds = React.useMemo(
    () =>
      new Set(
        outputActions
          .filter((action) => isWorkflowActiveStatus(action.status))
          .map((action) => action.output_id),
      ),
    [outputActions],
  );
  const outputs = React.useMemo(() => {
    if (!preset) {
      return baseOutputs;
    }

    if (preset === "ready_datasets") {
      return baseOutputs.filter(
        (output) =>
          output.availability === "ready" &&
          (output.format === "parquet" || output.format === "tfrecord"),
      );
    }

    if (preset === "active_compute") {
      return baseOutputs.filter((output) => activeActionOutputIds.has(output.id));
    }

    if (preset === "json_sidecars") {
      return baseOutputs.filter((output) => output.format === "json");
    }

    return baseOutputs;
  }, [activeActionOutputIds, baseOutputs, preset]);
  const visibleOutputIds = React.useMemo(
    () => new Set(outputs.map((output) => output.id)),
    [outputs],
  );
  const selectedOutputIdsSet = React.useMemo(
    () => new Set(selectedOutputIds),
    [selectedOutputIds],
  );
  const selectedOutputs = React.useMemo(
    () => outputs.filter((output) => selectedOutputIdsSet.has(output.id)),
    [outputs, selectedOutputIdsSet],
  );
  const currentHref = React.useMemo(() => {
    const queryString = searchParams.toString();
    return queryString ? `${pathname}?${queryString}` : pathname;
  }, [pathname, searchParams]);
  const selectedOutput =
    baseOutputs.find((output) => output.id === selectedOutputId) ?? selectedOutputResponse.data ?? null;
  const latestActionsByOutput = React.useMemo(
    () => getLatestActionsByOutput(outputActions),
    [outputActions],
  );
  const selectedOutputActions = React.useMemo(
    () =>
      selectedOutput
        ? outputActions
            .filter((action) => action.output_id === selectedOutput.id)
            .sort((left, right) => {
              const updatedDifference =
                new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime();

              if (updatedDifference !== 0) {
                return updatedDifference;
              }

              return right.id.localeCompare(left.id);
            })
        : [],
    [outputActions, selectedOutput],
  );
  const assetsById = React.useMemo(
    () => new Map((assetsResponse.data ?? []).map((asset) => [asset.id, asset])),
    [assetsResponse.data],
  );
  const activeActionCount = outputActions.filter((action) => isWorkflowActiveStatus(action.status)).length;
  const actionDialogOutputs = React.useMemo(() => {
    if (selectedOutputs.length > 0) {
      return selectedOutputs;
    }

    return selectedOutput ? [selectedOutput] : [];
  }, [selectedOutput, selectedOutputs]);
  const isActionDialogOpen = actionType === "vlm_tagging" && actionDialogOutputs.length > 0;
  const allVisibleSelected = outputs.length > 0 && selectedOutputs.length === outputs.length;
  const hasAppliedFilters = Boolean(
    query.asset_id ||
      query.availability ||
      query.conversion_id ||
      query.format ||
      query.search ||
      preset ||
      selectedOutputId ||
      selectedOutputIds.length,
  );

  const updateFilters = React.useCallback((updates: Record<string, string | null>) => {
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
  }, [pathname, router, searchParams]);

  const clearActionFlow = React.useCallback(() => {
    updateFilters({
      action: null,
      overwrite: null,
      prompt: null,
      sample_cap: null,
      target_field: null,
    });
  }, [updateFilters]);

  const clearWorkspaceFilters = React.useCallback(() => {
    updateFilters({
      action: null,
      asset_id: null,
      availability: null,
      conversion_id: null,
      format: null,
      output: null,
      overwrite: null,
      preset: null,
      prompt: null,
      sample_cap: null,
      search: null,
      selection: null,
      target_field: null,
    });
  }, [updateFilters]);

  React.useEffect(() => {
    if (activeActionCount === 0) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void outputActionsResponse.mutate();
    }, 1000);

    return () => window.clearInterval(intervalId);
  }, [activeActionCount, outputActionsResponse]);

  React.useEffect(() => {
    if ((outputsResponse.isLoading && !outputsResponse.data) || selectedOutputIds.length === 0) {
      return;
    }

    const trimmedSelection = selectedOutputIds.filter((outputId) => visibleOutputIds.has(outputId));

    if (trimmedSelection.length !== selectedOutputIds.length) {
      updateFilters({
        selection: trimmedSelection.length > 0 ? trimmedSelection.join(",") : null,
      });
    }
  }, [
    outputsResponse.data,
    outputsResponse.isLoading,
    selectedOutputIds,
    updateFilters,
    visibleOutputIds,
  ]);

  React.useEffect(() => {
    if (actionType !== "vlm_tagging") {
      return;
    }

    if (outputsResponse.isLoading || selectedOutputResponse.isLoading) {
      return;
    }

    if (actionDialogOutputs.length === 0) {
      clearActionFlow();
    }
  }, [
    actionDialogOutputs.length,
    actionType,
    clearActionFlow,
    outputsResponse.isLoading,
    selectedOutputResponse.isLoading,
  ]);

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

  async function onCopyResultJson(action: OutputActionDetail) {
    if (!action.result_json) {
      return;
    }

    try {
      await navigator.clipboard.writeText(JSON.stringify(action.result_json, null, 2));
      notify({
        description: action.id,
        title: "Result JSON copied",
        tone: "success",
      });
    } catch (error) {
      notify({
        description: getErrorMessage(error),
        title: "Could not copy result JSON",
        tone: "error",
      });
    }
  }

  async function onCopyViewLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      notify({
        description: "Current filters, selection, and action state are now copied.",
        title: "View link copied",
        tone: "success",
      });
    } catch (error) {
      notify({
        description: getErrorMessage(error),
        title: "Could not copy view link",
        tone: "error",
      });
    }
  }

  function onToggleOutputSelection(outputId: string) {
    const nextSelection = selectedOutputIdsSet.has(outputId)
      ? selectedOutputIds.filter((currentId) => currentId !== outputId)
      : [...selectedOutputIds, outputId];

    updateFilters({
      selection: nextSelection.length > 0 ? nextSelection.join(",") : null,
    });
  }

  function onToggleAllVisible() {
    updateFilters({
      selection: allVisibleSelected ? null : outputs.map((output) => output.id).join(","),
    });
  }

  function openVlmTagging(outputsToTag: OutputDetail[]) {
    if (outputsToTag.length === 0) {
      return;
    }

    const defaults = getDefaultOutputActionPrefill(outputsToTag);

    updateFilters({
      action: "vlm_tagging",
      output: outputsToTag[0]?.id ?? null,
      overwrite: defaults.overwrite ? "1" : null,
      prompt: defaults.promptTemplate,
      sample_cap: String(defaults.sampleCap),
      selection: outputsToTag.length > 1 ? outputsToTag.map((output) => output.id).join(",") : null,
      target_field: defaults.targetField,
    });
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
              <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                {formatCount(activeActionCount, "active action")}
              </span>
            </div>
            <p className="max-w-3xl text-sm text-muted-foreground">
              Browse the files produced by conversion runs without retracing the original job history.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void onCopyViewLink()} size="sm" type="button" variant="outline">
              <Copy className="size-4" />
              Copy view link
            </Button>
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
          {hasAppliedFilters || actionType ? (
            <Button
              onClick={clearWorkspaceFilters}
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
                onChange={(event) =>
                  updateFilters({ output: null, search: event.target.value, selection: null })
                }
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
                onChange={(event) =>
                  updateFilters({
                    format: event.target.value || null,
                    output: null,
                    selection: null,
                  })
                }
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
                  updateFilters({
                    availability: event.target.value || null,
                    output: null,
                    selection: null,
                  })
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
                onChange={(event) =>
                  updateFilters({ asset_id: event.target.value, output: null, selection: null })
                }
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
                onChange={(event) =>
                  updateFilters({
                    conversion_id: event.target.value,
                    output: null,
                    selection: null,
                  })
                }
                placeholder="Filter to one conversion"
                value={query.conversion_id ?? ""}
              />
            </div>
          </div>

          <div className="mt-5 space-y-2">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Common slices</p>
            <div className="flex flex-wrap gap-2">
              {OUTPUT_PRESET_OPTIONS.map((option) => {
                const isActive = preset === option.value;

                return (
                  <Button
                    key={option.value}
                    onClick={() =>
                      updateFilters({
                        output: null,
                        preset: isActive ? null : option.value,
                        selection: null,
                      })
                    }
                    size="sm"
                    type="button"
                    variant={isActive ? "secondary" : "outline"}
                  >
                    {option.label}
                  </Button>
                );
              })}
            </div>
            {preset ? (
              <p className="text-xs text-muted-foreground">
                {
                  OUTPUT_PRESET_OPTIONS.find((option) => option.value === preset)?.description
                }
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Presets are URL-backed, so you can share common output slices without rebuilding the filters each
                time.
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {outputs.length === 0 ? (
        <OutputsEmptyState
          action={
            hasAppliedFilters ? (
              <Button onClick={clearWorkspaceFilters} type="button" variant="outline">
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
                  Select one output to inspect it closely, or select several to launch batch compute work.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {selectedOutputs.length > 0 ? (
                  <div className="mb-4 flex flex-col gap-3 rounded-xl border bg-muted/20 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-foreground">
                        {formatCount(selectedOutputs.length, "selected output")}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Multi-select state lives in the URL, so batch flows and filtered views are easy to share.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button onClick={() => openVlmTagging(selectedOutputs)} size="sm" type="button">
                        <Sparkles className="size-3.5" />
                        Batch VLM tagging
                      </Button>
                      <Button
                        onClick={() => updateFilters({ selection: null })}
                        size="sm"
                        type="button"
                        variant="outline"
                      >
                        Clear selection
                      </Button>
                    </div>
                  </div>
                ) : null}
                <OutputsTable
                  allVisibleSelected={allVisibleSelected}
                  assetsById={assetsById}
                  currentHref={currentHref}
                  latestActionsByOutput={latestActionsByOutput}
                  onCopyPath={onCopyPath}
                  onRunVlmTagging={(output) => openVlmTagging([output])}
                  onSelectOutput={(outputId) => updateFilters({ output: outputId })}
                  onToggleAllVisible={onToggleAllVisible}
                  onToggleOutputSelection={onToggleOutputSelection}
                  outputs={outputs}
                  selectedOutputIds={selectedOutputIdsSet}
                  selectedOutputId={selectedOutputId}
                />
                <OutputsCards
                  assetsById={assetsById}
                  currentHref={currentHref}
                  latestActionsByOutput={latestActionsByOutput}
                  onCopyPath={onCopyPath}
                  onRunVlmTagging={(output) => openVlmTagging([output])}
                  onSelectOutput={(outputId) => updateFilters({ output: outputId })}
                  onToggleOutputSelection={onToggleOutputSelection}
                  outputs={outputs}
                  selectedOutputIds={selectedOutputIdsSet}
                />
              </CardContent>
            </Card>
          </div>

          <OutputDetailPanel
            assetsById={assetsById}
            currentHref={currentHref}
            onClearSelection={() => updateFilters({ output: null })}
            onCopyPath={onCopyPath}
            onCopyResultJson={onCopyResultJson}
            onRunVlmTagging={(output) => openVlmTagging([output])}
            output={selectedOutput}
            outputActions={selectedOutputActions}
            selectionMissing={Boolean(
              selectedOutputId &&
                !selectedOutput &&
                !selectedOutputResponse.isLoading &&
                outputsResponse.data,
            )}
          />
        </div>
      )}

      <OutputActionDialog
        onCreated={(actions) => {
          const firstAction = actions[0];

          if (firstAction && selectedOutputId !== firstAction.output_id) {
            updateFilters({ output: firstAction.output_id });
          }
        }}
        onOpenChange={(open) => {
          if (!open) {
            clearActionFlow();
          }
        }}
        open={isActionDialogOpen}
        outputs={actionDialogOutputs}
        prefill={actionPrefill}
      />
    </div>
  );
}
