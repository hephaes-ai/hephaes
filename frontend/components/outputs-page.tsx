"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  ChevronDown,
  Copy,
  Database,
  ExternalLink,
  ListFilter,
  MoreHorizontal,
  RefreshCw,
  Search,
  Sparkles,
  Wrench,
  X,
} from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { MetadataField } from "@/components/metadata-field";
import { OutputAvailabilityBadge } from "@/components/output-availability-badge";
import { WorkflowStatusBadge } from "@/components/workflow-status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useAssets,
  useCreateOutputAction,
  useOutputs,
} from "@/hooks/use-backend";
import type {
  AssetSummary,
  OutputActionDetail,
  OutputAvailability,
  OutputDetail,
  OutputFormat,
  OutputRole,
  OutputsQuery,
} from "@/lib/api";
import { getErrorMessage, resolveBackendUrl } from "@/lib/api";
import {
  formatDateTime,
  formatFileSize,
  formatCount,
  formatOutputActionType,
  formatOutputAvailability,
  formatOutputFormat,
  formatOutputRole,
  isWorkflowActiveStatus,
} from "@/lib/format";
import {
  buildAssetDetailHref,
  buildJobDetailHref,
  buildOutputDetailHref,
} from "@/lib/navigation";
import type { ActiveFilterChip } from "@/lib/types";
import { cn } from "@/lib/utils";

const OUTPUT_FORMAT_OPTIONS: OutputFormat[] = ["parquet", "tfrecord", "json", "jsonl", "unknown"];
const OUTPUT_ROLE_OPTIONS: OutputRole[] = ["dataset", "manifest", "sidecar"];
const OUTPUT_AVAILABILITY_OPTIONS: OutputAvailability[] = ["ready", "missing", "invalid"];
const OUTPUT_PRESET_OPTIONS = [
  {
    description: "Show dataset artifacts that are currently available on disk.",
    label: "Ready datasets",
    value: "ready_datasets",
  },
  {
    description: "Focus on outputs with queued or running backend actions.",
    label: "Active compute",
    value: "active_compute",
  },
  {
    description: "Show JSON and JSONL sidecars such as manifests and summaries.",
    label: "JSON sidecars",
    value: "json_sidecars",
  },
] as const;

type OutputPreset = (typeof OUTPUT_PRESET_OPTIONS)[number]["value"];

interface OutputPreviewFact {
  label: string;
  value: string;
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

function buildOutputsQuery(searchParams: URLSearchParams): OutputsQuery {
  const search = searchParams.get("search")?.trim() ?? "";
  const format = searchParams.get("format")?.trim() ?? "";
  const role = searchParams.get("role")?.trim() ?? "";
  const assetId = searchParams.get("asset_id")?.trim() ?? "";
  const availability = searchParams.get("availability")?.trim() ?? "";
  const conversionId = searchParams.get("conversion_id")?.trim() ?? "";

  return {
    asset_id: assetId || undefined,
    availability: availability || undefined,
    conversion_id: conversionId || undefined,
    format: format || undefined,
    limit: 500,
    role: role || undefined,
    search: search || undefined,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getNestedRecord(
  value: Record<string, unknown> | undefined,
  key: string,
): Record<string, unknown> | null {
  if (!value) {
    return null;
  }

  const nestedValue = value[key];
  return isRecord(nestedValue) ? nestedValue : null;
}

function getNumberValue(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function getStringValue(value: unknown) {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function getStringList(value: unknown) {
  if (!Array.isArray(value)) {
    return [] as string[];
  }

  return value.filter(
    (item): item is string => typeof item === "string" && item.trim().length > 0,
  );
}

function applyOutputPreset(outputs: OutputDetail[], preset: OutputPreset | null) {
  if (!preset) {
    return outputs;
  }

  if (preset === "ready_datasets") {
    return outputs.filter(
      (output) => output.role === "dataset" && output.availability_status === "ready",
    );
  }

  if (preset === "active_compute") {
    return outputs.filter(
      (output) =>
        output.latest_action !== null && isWorkflowActiveStatus(output.latest_action.status),
    );
  }

  if (preset === "json_sidecars") {
    return outputs.filter(
      (output) =>
        output.format === "json" ||
        output.format === "jsonl" ||
        output.role === "manifest" ||
        output.role === "sidecar",
    );
  }

  return outputs;
}

export function formatOutputActionSummary(action: OutputActionDetail) {
  if (action.error_message) {
    return action.error_message;
  }

  if (action.status === "queued") {
    return "Queued on the backend.";
  }

  if (action.status === "running") {
    return "Running on the backend now.";
  }

  if (action.action_type === "refresh_metadata") {
    const availability = getStringValue(action.result.availability_status);
    const sizeBytes = getNumberValue(action.result.size_bytes);
    const parts = ["Metadata refreshed"];

    if (availability) {
      parts.push(formatOutputAvailability(availability));
    }

    if (sizeBytes !== null) {
      parts.push(formatFileSize(sizeBytes));
    }

    return parts.join(" . ");
  }

  if (Object.keys(action.result).length > 0) {
    return "Completed and returned a result payload.";
  }

  return action.status === "succeeded" ? "Completed." : "No summary available yet.";
}

export function buildOutputPreview(output: OutputDetail) {
  const manifest = getNestedRecord(output.metadata, "manifest");
  const dataset = getNestedRecord(manifest ?? undefined, "dataset");
  const temporal = getNestedRecord(manifest ?? undefined, "temporal");
  const parquet = getNestedRecord(output.metadata, "parquet");
  const schemaFields = getStringList(parquet?.schema_fields);
  const facts: OutputPreviewFact[] = [
    {
      label: "Role",
      value: formatOutputRole(output.role),
    },
    {
      label: "Size",
      value: formatFileSize(output.size_bytes),
    },
  ];
  const notes: string[] = [];

  if (output.format === "parquet") {
    facts.push({
      label: "Rows written",
      value: String(getNumberValue(dataset?.rows_written) ?? "Not available"),
    });
    facts.push({
      label: "Row groups",
      value: String(getNumberValue(parquet?.row_group_count) ?? "Not available"),
    });
    facts.push({
      label: "Schema fields",
      value: schemaFields.length > 0 ? String(schemaFields.length) : "Not available",
    });

    if (schemaFields.length > 0) {
      notes.push(`Schema starts with ${schemaFields.slice(0, 3).join(", ")}.`);
    }
  } else if (output.format === "tfrecord") {
    facts.push({
      label: "Rows written",
      value: String(getNumberValue(dataset?.rows_written) ?? "Not available"),
    });
    facts.push({
      label: "Message count",
      value: String(getNumberValue(temporal?.message_count) ?? "Not available"),
    });
    facts.push({
      label: "Media type",
      value: output.media_type ?? "Not available",
    });
  } else if (output.role === "manifest" || output.format === "json" || output.format === "jsonl") {
    facts.push({
      label: "Episode ID",
      value: getStringValue(manifest?.episode_id) ?? "Not available",
    });
    facts.push({
      label: "Dataset format",
      value: getStringValue(dataset?.format) ?? "Not available",
    });
    facts.push({
      label: "Duration",
      value:
        getNumberValue(temporal?.duration_seconds) !== null
          ? `${getNumberValue(temporal?.duration_seconds)} s`
          : "Not available",
    });
  } else {
    facts.push({
      label: "Availability",
      value: formatOutputAvailability(output.availability_status),
    });
    facts.push({
      label: "Media type",
      value: output.media_type ?? "Not available",
    });
  }

  if (output.latest_action) {
    notes.push(
      `Latest backend action: ${formatOutputActionType(output.latest_action.action_type)} (${formatOutputActionSummary(output.latest_action)}).`,
    );
  }

  if (notes.length === 0) {
    notes.push("This preview is built from the backend output artifact metadata and manifest summaries.");
  }

  return {
    description:
      output.role === "dataset"
        ? "Artifact facts surfaced from the backend output catalog."
        : "Sidecar and metadata facts surfaced from the backend output catalog.",
    facts,
    notes,
    title:
      output.role === "manifest"
        ? "Manifest preview"
        : output.format === "parquet"
          ? "Parquet preview"
          : output.format === "tfrecord"
            ? "TFRecord preview"
            : "Artifact preview",
  };
}

export function getCopyableReference(output: OutputDetail) {
  return output.file_path?.trim() || resolveBackendUrl(output.content_url);
}

function OutputsPageSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-9 w-44" />
      <Skeleton className="h-28 rounded-xl" />
      <Skeleton className="h-[640px] rounded-xl" />
    </div>
  );
}

export function OutputsPageFallback() {
  return <OutputsPageSkeleton />;
}


export function OutputRoleBadge({ role }: { role: OutputRole }) {
  return <Badge variant="outline">{formatOutputRole(role)}</Badge>;
}

export function OutputSourceLinks({
  assetIds,
  assetsById,
  compact = false,
  currentHref,
}: {
  assetIds: string[];
  assetsById: Map<string, AssetSummary>;
  compact?: boolean;
  currentHref: string;
}) {
  if (assetIds.length === 0) {
    return <span className="text-sm text-muted-foreground">No assets</span>;
  }

  if (compact && assetIds.length > 1) {
    return (
      <Badge
        className="font-mono text-xs"
        onClick={(event) => event.stopPropagation()}
        title={`${assetIds.length} source assets`}
        variant="outline"
      >
        +{assetIds.length}
      </Badge>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5" onClick={(event) => event.stopPropagation()}>
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

export function OutputContentButton({
  output,
  size = "sm",
  variant = "outline",
}: {
  output: OutputDetail;
  size?: "sm" | "xs" | "default";
  variant?: "outline" | "ghost" | "secondary" | "default";
}) {
  if (output.availability_status !== "ready") {
    return (
      <Button disabled size={size} type="button" variant={variant}>
        Content unavailable
      </Button>
    );
  }

  return (
    <Button asChild size={size} variant={variant}>
      <a
        href={resolveBackendUrl(output.content_url)}
        onClick={(event) => event.stopPropagation()}
        rel="noreferrer"
        target="_blank"
      >
        Open content
        <ExternalLink className="size-3.5" />
      </a>
    </Button>
  );
}

export function OutputPreviewPanel({ output }: { output: OutputDetail }) {
  const preview = buildOutputPreview(output);

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

export function OutputDetailContent({
  assetsById,
  currentHref,
  isRefreshing,
  onCopyReference,
  onCopyResultJson,
  onRefreshMetadata,
  onShowVlmTaggingStub,
  output,
  outputActions,
  outputActionsError,
}: {
  assetsById: Map<string, AssetSummary>;
  currentHref: string;
  isRefreshing: boolean;
  onCopyReference: (output: OutputDetail) => Promise<void>;
  onCopyResultJson: (action: OutputActionDetail) => Promise<void>;
  onRefreshMetadata: (outputs: OutputDetail[]) => Promise<void>;
  onShowVlmTaggingStub: (scopeLabel: string) => void;
  output: OutputDetail;
  outputActions: OutputActionDetail[];
  outputActionsError: unknown;
}) {
  const latestAction = output.latest_action;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            <CardTitle className="break-all text-xl">{output.file_name}</CardTitle>
            <CardDescription className="break-all">{output.relative_path}</CardDescription>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <OutputAvailabilityBadge availability={output.availability_status} />
            <OutputRoleBadge role={output.role} />
            <OutputContentButton output={output} />
            <Button onClick={() => void onCopyReference(output)} size="sm" type="button" variant="outline">
              <Copy className="size-3.5" />
              Copy reference
            </Button>
            <Button
              disabled={isRefreshing}
              onClick={() => void onRefreshMetadata([output])}
              size="sm"
              type="button"
              variant="outline"
            >
              <Wrench className="size-3.5" />
              Refresh metadata
            </Button>
            <Button onClick={() => onShowVlmTaggingStub(output.file_name)} size="sm" type="button">
              <Sparkles className="size-3.5" />
              VLM tagging soon
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <dl className="grid gap-4 sm:grid-cols-2">
            <MetadataField label="Format" value={formatOutputFormat(output.format)} />
            <MetadataField label="Size" value={formatFileSize(output.size_bytes)} />
            <MetadataField label="Created" value={formatDateTime(output.created_at)} />
            <MetadataField label="Updated" value={formatDateTime(output.updated_at)} />
            <MetadataField label="Media type" value={output.media_type ?? "Not available"} />
            <MetadataField label="Role" value={formatOutputRole(output.role)} />
            <MetadataField label="Conversion ID" value={<span className="break-all font-mono text-xs">{output.conversion_id}</span>} />
            <MetadataField label="Job ID" value={<span className="break-all font-mono text-xs">{output.job_id}</span>} />
            <div className="space-y-1 sm:col-span-2">
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Local file path</dt>
              <dd className="break-all text-sm font-medium text-foreground">
                {output.file_path ?? "Not available from the list response"}
              </dd>
            </div>
            <div className="space-y-1 sm:col-span-2">
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Content URL</dt>
              <dd className="break-all text-sm font-medium text-foreground">
                {resolveBackendUrl(output.content_url)}
              </dd>
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

      <OutputPreviewPanel output={output} />

      {Object.keys(output.metadata).length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Artifact metadata</CardTitle>
            <CardDescription>
              Backend-supplied metadata, manifest summaries, and artifact inspection results.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto rounded-lg border bg-muted/20 p-3 text-xs text-foreground">
              {JSON.stringify(output.metadata, null, 2)}
            </pre>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle>Compute actions</CardTitle>
            <CardDescription>
              Refresh backend metadata now, and leave room for future actions like VLM tagging.
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={isRefreshing}
              onClick={() => void onRefreshMetadata([output])}
              size="sm"
              type="button"
              variant="outline"
            >
              <Wrench className="size-3.5" />
              Refresh metadata
            </Button>
            <Button onClick={() => onShowVlmTaggingStub(output.file_name)} size="sm" type="button">
              <Sparkles className="size-3.5" />
              VLM tagging soon
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {outputActionsError ? (
            <Alert variant="destructive">
              <AlertTitle>Could not load output actions</AlertTitle>
              <AlertDescription>{getErrorMessage(outputActionsError)}</AlertDescription>
            </Alert>
          ) : null}

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
                  <MetadataField label="Action type" value={formatOutputActionType(action.action_type)} />
                  <MetadataField label="Started" value={formatDateTime(action.started_at)} />
                </dl>
                <p className="text-sm text-foreground">{formatOutputActionSummary(action)}</p>
                {action.output_file_path ? (
                  <div className="space-y-1">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Output file path</p>
                    <p className="break-all text-sm text-foreground">{action.output_file_path}</p>
                  </div>
                ) : null}
                {action.output_path ? (
                  <div className="space-y-1">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Result path</p>
                    <p className="break-all text-sm text-foreground">{action.output_path}</p>
                  </div>
                ) : null}
                {Object.keys(action.config).length > 0 ? (
                  <div className="space-y-2">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Config</p>
                    <pre className="overflow-x-auto rounded-lg border bg-muted/20 p-3 text-xs text-foreground">
                      {JSON.stringify(action.config, null, 2)}
                    </pre>
                  </div>
                ) : null}
                {Object.keys(action.result).length > 0 ? (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Result JSON</p>
                      <Button onClick={() => void onCopyResultJson(action)} size="sm" type="button" variant="ghost">
                        Copy JSON
                      </Button>
                    </div>
                    <pre className="overflow-x-auto rounded-lg border bg-muted/20 p-3 text-xs text-foreground">
                      {JSON.stringify(action.result, null, 2)}
                    </pre>
                  </div>
                ) : null}
              </div>
            ))
          ) : (
            <div className="rounded-lg border border-dashed px-4 py-8 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">No backend actions yet</p>
              <p className="mt-2">
                Run `Refresh metadata` when you want the backend to rescan the artifact and update its catalog record.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function OutputsTable({
  allVisibleSelected,
  assetsById,
  currentHref,
  isRefreshing,
  onRefreshMetadata,
  onSelectOutput,
  onToggleAllVisible,
  onToggleOutputSelection,
  outputs,
  selectedOutputId,
  selectedOutputIds,
}: {
  allVisibleSelected: boolean;
  assetsById: Map<string, AssetSummary>;
  currentHref: string;
  isRefreshing: boolean;
  onRefreshMetadata: (outputs: OutputDetail[]) => Promise<void>;
  onSelectOutput: (outputId: string) => void;
  onToggleAllVisible: () => void;
  onToggleOutputSelection: (outputId: string) => void;
  outputs: OutputDetail[];
  selectedOutputId: string;
  selectedOutputIds: Set<string>;
}) {
  const someVisibleSelected =
    !allVisibleSelected && outputs.some((output) => selectedOutputIds.has(output.id));

  return (
    <div className="hidden overflow-x-auto md:block">
      <Table className="min-w-[980px]">
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">
              <div className="flex items-center justify-center">
                <Checkbox
                  aria-label="Select all visible outputs"
                  checked={allVisibleSelected ? true : someVisibleSelected ? "indeterminate" : false}
                  onCheckedChange={() => onToggleAllVisible()}
                />
              </div>
            </TableHead>
            <TableHead>Output file</TableHead>
            <TableHead>Source assets</TableHead>
            <TableHead>Size</TableHead>
            <TableHead>Availability</TableHead>
            <TableHead>Latest action</TableHead>
            <TableHead className="w-12 text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {outputs.map((output) => {
            const isSelected = output.id === selectedOutputId;
            const isBatchSelected = selectedOutputIds.has(output.id);
            const latestAction = output.latest_action;

            return (
              <TableRow
                className={isSelected ? "bg-muted/35" : undefined}
                key={output.id}
                onClick={() => onSelectOutput(output.id)}
              >
                <TableCell>
                  <div className="flex items-center justify-center">
                    <Checkbox
                      aria-label={`Select ${output.file_name}`}
                      checked={isBatchSelected}
                      onCheckedChange={() => onToggleOutputSelection(output.id)}
                      onClick={(event) => event.stopPropagation()}
                    />
                  </div>
                </TableCell>
                <TableCell>
                  <div className="space-y-2">
                    <p className="font-medium text-foreground whitespace-nowrap">{output.file_name}</p>
                    <p className="text-xs text-muted-foreground">{output.relative_path}</p>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{formatOutputFormat(output.format)}</Badge>
                      <OutputRoleBadge role={output.role} />
                    </div>
                  </div>
                </TableCell>
                <TableCell>
                  <OutputSourceLinks
                    assetIds={output.asset_ids}
                    assetsById={assetsById}
                    compact
                    currentHref={currentHref}
                  />
                </TableCell>
                <TableCell>{formatFileSize(output.size_bytes)}</TableCell>
                <TableCell>
                  <OutputAvailabilityBadge availability={output.availability_status} />
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
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="size-8"
                        onClick={(event) => event.stopPropagation()}
                      >
                        <MoreHorizontal className="size-4" />
                        <span className="sr-only">Actions</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={(event) => {
                          event.stopPropagation();
                          onSelectOutput(output.id);
                        }}
                      >
                        Inspect
                      </DropdownMenuItem>
                      {output.availability_status === "ready" ? (
                        <DropdownMenuItem asChild>
                          <a
                            href={resolveBackendUrl(output.content_url)}
                            rel="noreferrer"
                            target="_blank"
                          >
                            Open content
                            <ExternalLink className="size-4" />
                          </a>
                        </DropdownMenuItem>
                      ) : null}
                      <DropdownMenuItem
                        disabled={isRefreshing}
                        onClick={(event) => {
                          event.stopPropagation();
                          void onRefreshMetadata([output]);
                        }}
                      >
                        Refresh
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
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
  isRefreshing,
  onRefreshMetadata,
  onSelectOutput,
  onToggleOutputSelection,
  outputs,
  selectedOutputIds,
}: {
  assetsById: Map<string, AssetSummary>;
  currentHref: string;
  isRefreshing: boolean;
  onRefreshMetadata: (outputs: OutputDetail[]) => Promise<void>;
  onSelectOutput: (outputId: string) => void;
  onToggleOutputSelection: (outputId: string) => void;
  outputs: OutputDetail[];
  selectedOutputIds: Set<string>;
}) {
  return (
    <div className="space-y-3 md:hidden">
      {outputs.map((output) => {
        const isBatchSelected = selectedOutputIds.has(output.id);
        const latestAction = output.latest_action;

        return (
          <div className="space-y-3 rounded-xl border bg-muted/15 px-4 py-4" key={output.id}>
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-2">
                <p className="font-medium text-foreground">{output.file_name}</p>
                <p className="break-all text-xs text-muted-foreground">{output.relative_path}</p>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{formatOutputFormat(output.format)}</Badge>
                  <OutputRoleBadge role={output.role} />
                </div>
              </div>
              <Checkbox
                aria-label={`Select ${output.file_name}`}
                checked={isBatchSelected}
                onCheckedChange={() => onToggleOutputSelection(output.id)}
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <OutputAvailabilityBadge availability={output.availability_status} />
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
              <OutputSourceLinks
                assetIds={output.asset_ids}
                assetsById={assetsById}
                compact
                currentHref={currentHref}
              />
            </div>

            <p className="text-sm text-muted-foreground">
              {formatFileSize(output.size_bytes)} . Updated {formatDateTime(output.updated_at)}
            </p>

            <div className="flex flex-wrap gap-2">
              <Button onClick={() => onSelectOutput(output.id)} size="sm" type="button" variant="secondary">
                Inspect
              </Button>
              <OutputContentButton output={output} size="sm" variant="outline" />
              <Button
                disabled={isRefreshing}
                onClick={() => void onRefreshMetadata([output])}
                size="sm"
                type="button"
              >
                Refresh
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

  const { isCreating, trigger } = useCreateOutputAction();

  const query = React.useMemo(() => buildOutputsQuery(searchParams), [searchParams]);
  const presetValue = searchParams.get("preset")?.trim() ?? "";
  const preset = React.useMemo(
    () =>
      OUTPUT_PRESET_OPTIONS.some((option) => option.value === presetValue)
        ? (presetValue as OutputPreset)
        : null,
    [presetValue],
  );
  const selectedOutputId = searchParams.get("output")?.trim() ?? "";
  const selectedOutputIds = React.useMemo(
    () => parseOutputSelection(searchParams.get("selection")),
    [searchParams],
  );
  const [searchInput, setSearchInput] = React.useState(query.search ?? "");
  const [isFiltersOpen, setIsFiltersOpen] = React.useState(false);

  const outputsResponse = useOutputs(query);
  const assetsResponse = useAssets();

  const baseOutputs = React.useMemo(() => outputsResponse.data ?? [], [outputsResponse.data]);
  const outputs = React.useMemo(
    () => applyOutputPreset(baseOutputs, preset),
    [baseOutputs, preset],
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
  const assetsById = React.useMemo(
    () => new Map((assetsResponse.data ?? []).map((asset) => [asset.id, asset])),
    [assetsResponse.data],
  );
  const visibleOutputIds = React.useMemo(
    () => new Set(outputs.map((output) => output.id)),
    [outputs],
  );
  const activeActionCount = outputs.filter(
    (output) =>
      output.latest_action !== null && isWorkflowActiveStatus(output.latest_action.status),
  ).length;
  const allVisibleSelected = outputs.length > 0 && selectedOutputs.length === outputs.length;
  const activeFilterChips: ActiveFilterChip[] = [];

  if (query.search) {
    activeFilterChips.push({
      key: "search",
      label: `Search: ${query.search}`,
      updates: { output: null, search: null, selection: null },
    });
  }

  if (query.format) {
    activeFilterChips.push({
      key: "format",
      label: `Format: ${formatOutputFormat(query.format as OutputFormat)}`,
      updates: { format: null, output: null, selection: null },
    });
  }

  if (query.role) {
    activeFilterChips.push({
      key: "role",
      label: `Role: ${formatOutputRole(query.role as OutputRole)}`,
      updates: { output: null, role: null, selection: null },
    });
  }

  if (query.availability) {
    activeFilterChips.push({
      key: "availability",
      label: `Availability: ${formatOutputAvailability(query.availability as OutputAvailability)}`,
      updates: { availability: null, output: null, selection: null },
    });
  }

  if (query.asset_id) {
    activeFilterChips.push({
      key: "asset_id",
      label: `Asset: ${query.asset_id}`,
      updates: { asset_id: null, output: null, selection: null },
    });
  }

  if (query.conversion_id) {
    activeFilterChips.push({
      key: "conversion_id",
      label: `Conversion: ${query.conversion_id}`,
      updates: { conversion_id: null, output: null, selection: null },
    });
  }

  if (preset) {
    activeFilterChips.push({
      key: "preset",
      label: `Preset: ${OUTPUT_PRESET_OPTIONS.find((option) => option.value === preset)?.label ?? preset}`,
      updates: { output: null, preset: null, selection: null },
    });
  }

  const hasAppliedFilters = activeFilterChips.length > 0;
  const updateFilters = React.useCallback(
    (updates: Record<string, string | null>) => {
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
    },
    [pathname, router, searchParams],
  );

  React.useEffect(() => {
    setSearchInput(query.search ?? "");
  }, [query.search]);

  React.useEffect(() => {
    if (hasAppliedFilters) {
      setIsFiltersOpen(true);
    }
  }, [hasAppliedFilters]);

  const clearWorkspaceFilters = React.useCallback(() => {
    updateFilters({
      asset_id: null,
      availability: null,
      conversion_id: null,
      format: null,
      output: null,
      preset: null,
      role: null,
      search: null,
      selection: null,
    });
  }, [updateFilters]);

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
    if (activeActionCount === 0) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void outputsResponse.mutate();
    }, 1000);

    return () => window.clearInterval(intervalId);
  }, [activeActionCount, outputsResponse]);

  function onSearchSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    updateFilters({
      output: null,
      search: searchInput,
      selection: null,
    });
  }

  function onClearSearch() {
    setSearchInput("");
    updateFilters({
      output: null,
      search: null,
      selection: null,
    });
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

  function onShowVlmTaggingStub(scopeLabel: string) {
    toast.info("Coming soon", {
      description: `VLM tagging is not wired to the backend yet for ${scopeLabel}.`,
    });
  }

  async function onRefreshMetadata(outputsToRefresh: OutputDetail[]) {
    if (outputsToRefresh.length === 0) {
      return;
    }

    try {
      const createdActions: OutputActionDetail[] = [];

      for (const output of outputsToRefresh) {
        const action = await trigger(output.id, {
          action_type: "refresh_metadata",
          config: {
            reason:
              outputsToRefresh.length > 1
                ? "batch_refresh_from_outputs_page"
                : "manual_refresh_from_outputs_page",
          },
        });
        createdActions.push(action);
      }

      const firstOutput = outputsToRefresh[0];
      toast.success(
        outputsToRefresh.length === 1
          ? `Metadata refreshed for ${firstOutput?.file_name ?? "the selected output"}.`
          : `Metadata refreshed for ${outputsToRefresh.length} selected outputs.`,
      );
    } catch (error) {
      toast.error("Could not refresh output metadata", {
        description: getErrorMessage(error),
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
              <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                {formatCount(activeActionCount, "active action")}
              </span>
            </div>
            <p className="max-w-3xl text-sm text-muted-foreground">Output artifacts and actions.</p>
          </div>
          <div className="flex flex-wrap gap-2">
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

      <Card className="flex-1">
        <CardHeader className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Database className="size-4" />
                Output catalog
              </CardTitle>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="h-6" variant="secondary">
                {formatCount(outputs.length, "result")}
              </Badge>
              {selectedOutputs.length > 0 ? (
                <>
                  <Badge className="h-6" variant="outline">
                    {selectedOutputs.length} selected
                  </Badge>
                  <Button
                    disabled={isCreating}
                    onClick={() => void onRefreshMetadata(selectedOutputs)}
                    size="sm"
                    type="button"
                  >
                    <Wrench className="size-3.5" />
                    Batch refresh metadata
                  </Button>
                  <Button
                    disabled
                    size="sm"
                    type="button"
                    variant="outline"
                  >
                    <Sparkles className="size-3.5" />
                    Batch VLM tagging soon
                  </Button>
                  <Button
                    onClick={() => updateFilters({ selection: null })}
                    size="sm"
                    type="button"
                    variant="ghost"
                  >
                    Clear selection
                  </Button>
                </>
              ) : null}
              <Button
                aria-expanded={isFiltersOpen}
                onClick={() => setIsFiltersOpen((current) => !current)}
                size="sm"
                type="button"
                variant="outline"
              >
                <ListFilter className="size-4" />
                Search & filters{hasAppliedFilters ? ` (${activeFilterChips.length})` : ""}
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
                <form className="flex flex-col gap-3 lg:flex-row" onSubmit={onSearchSubmit}>
                  <div className="flex-1">
                    <label className="mb-2 block text-xs uppercase tracking-wide text-muted-foreground" htmlFor="outputs-search">
                      Search
                    </label>
                    <div className="flex gap-2">
                      <Input
                        id="outputs-search"
                        onChange={(event) => setSearchInput(event.target.value)}
                        placeholder="Search file name, path, format, or conversion ID"
                        value={searchInput}
                      />
                      <Button size="sm" type="submit" variant="outline">
                        <Search className="size-4" />
                        Search
                      </Button>
                      {(searchInput.length > 0 || (query.search ?? "").length > 0) && (
                        <Button onClick={onClearSearch} size="sm" type="button" variant="ghost">
                          <X className="size-4" />
                          Clear
                        </Button>
                      )}
                    </div>
                  </div>
                </form>

                <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)]">
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
                    <label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="outputs-role">
                      Role
                    </label>
                    <NativeSelect
                      id="outputs-role"
                      onChange={(event) =>
                        updateFilters({
                          output: null,
                          role: event.target.value || null,
                          selection: null,
                        })
                      }
                      value={query.role ?? ""}
                    >
                      <option value="">All roles</option>
                      {OUTPUT_ROLE_OPTIONS.map((role) => (
                        <option key={role} value={role}>
                          {formatOutputRole(role)}
                        </option>
                      ))}
                    </NativeSelect>
                  </div>
                  <div className="space-y-2">
                    <label
                      className="text-xs uppercase tracking-wide text-muted-foreground"
                      htmlFor="outputs-availability"
                    >
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
                    <label
                      className="text-xs uppercase tracking-wide text-muted-foreground"
                      htmlFor="outputs-conversion"
                    >
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

                <div className="space-y-2">
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
                  <p className="text-xs text-muted-foreground">
                    {preset
                      ? OUTPUT_PRESET_OPTIONS.find((option) => option.value === preset)?.description
                      : "Presets are URL-backed, so you can share common output slices without rebuilding the filters each time."}
                  </p>
                </div>

                {hasAppliedFilters ? (
                  <div className="flex flex-wrap items-center gap-2">
                    {activeFilterChips.map((filter) => (
                      <Button
                        key={filter.key}
                        onClick={() => {
                          if (filter.key === "search") {
                            setSearchInput("");
                          }
                          updateFilters(filter.updates!);
                        }}
                        size="xs"
                        type="button"
                        variant="outline"
                      >
                        {filter.label}
                        <X className="size-3" />
                      </Button>
                    ))}
                    <Button onClick={clearWorkspaceFilters} size="xs" type="button" variant="ghost">
                      Clear filters
                    </Button>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {outputs.length === 0 ? (
            <EmptyState
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
                  : "Run a conversion and its registered output artifacts will appear here for inspection."
              }
              title={hasAppliedFilters ? "No outputs match these filters" : "No outputs yet"}
            />
          ) : (
            <>
              <OutputsTable
                allVisibleSelected={allVisibleSelected}
                assetsById={assetsById}
                currentHref={currentHref}
                isRefreshing={isCreating}
                onRefreshMetadata={onRefreshMetadata}
                onSelectOutput={(outputId) => router.push(buildOutputDetailHref(outputId, currentHref))}
                onToggleAllVisible={onToggleAllVisible}
                onToggleOutputSelection={onToggleOutputSelection}
                outputs={outputs}
                selectedOutputId={selectedOutputId}
                selectedOutputIds={selectedOutputIdsSet}
              />
              <OutputsCards
                assetsById={assetsById}
                currentHref={currentHref}
                isRefreshing={isCreating}
                onRefreshMetadata={onRefreshMetadata}
                onSelectOutput={(outputId) => router.push(buildOutputDetailHref(outputId, currentHref))}
                onToggleOutputSelection={onToggleOutputSelection}
                outputs={outputs}
                selectedOutputIds={selectedOutputIdsSet}
              />
            </>
          )}
        </CardContent>
      </Card>

    </div>
  );
}
