"use client";

import { ArrowRight, Copy, ExternalLink } from "lucide-react";

import { MetadataField } from "@/components/metadata-field";
import { OutputAvailabilityBadge } from "@/components/output-availability-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { AssetSummary, OutputDetail, OutputRole } from "@/lib/api";
import { resolveBackendUrl } from "@/lib/api";
import { AppLink } from "@/lib/app-routing";
import {
  formatDateTime,
  formatFileSize,
  formatOutputAvailability,
  formatOutputFormat,
  formatOutputRole,
} from "@/lib/format";
import { buildAssetDetailHref, buildJobDetailHref } from "@/lib/navigation";

interface OutputPreviewFact {
  label: string;
  value: string;
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

function getPayloadRepresentation(
  output: OutputDetail,
): {
  imagePayloadContract: string | null;
  nullEncoding: string | null;
  payloadEncoding: string | null;
} {
  const manifest = getNestedRecord(output.metadata, "manifest");
  const payloadRepresentation = getNestedRecord(manifest ?? undefined, "payload_representation");

  return {
    imagePayloadContract: getStringValue(payloadRepresentation?.image_payload_contract),
    nullEncoding: getStringValue(payloadRepresentation?.null_encoding),
    payloadEncoding: getStringValue(payloadRepresentation?.payload_encoding),
  };
}

export function buildOutputPreview(output: OutputDetail) {
  const manifest = getNestedRecord(output.metadata, "manifest");
  const dataset = getNestedRecord(manifest ?? undefined, "dataset");
  const temporal = getNestedRecord(manifest ?? undefined, "temporal");
  const parquet = getNestedRecord(output.metadata, "parquet");
  const payloadRepresentation = getPayloadRepresentation(output);
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
    facts.push({
      label: "Image payload",
      value: payloadRepresentation.imagePayloadContract ?? "bytes_v2",
    });

    notes.push(
      payloadRepresentation.imagePayloadContract === "legacy_list_v1"
        ? "This TFRecord uses legacy list image payload compatibility."
        : "This TFRecord uses training-ready bytes image payload features.",
    );
    notes.push(
      `Loader expectation: payload=${payloadRepresentation.payloadEncoding ?? "typed_features"}, nulls=${payloadRepresentation.nullEncoding ?? "presence_flag"}.`,
    );
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
    if (payloadRepresentation.imagePayloadContract) {
      facts.push({
        label: "Image payload",
        value: payloadRepresentation.imagePayloadContract,
      });
    }
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
          <AppLink href={buildAssetDetailHref(assetId, currentHref)}>
            {assetsById.get(assetId)?.file_name ?? assetId}
          </AppLink>
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
  onCopyReference,
  output,
}: {
  assetsById: Map<string, AssetSummary>;
  currentHref: string;
  onCopyReference: (output: OutputDetail) => Promise<void>;
  output: OutputDetail;
}) {
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

          <div className="space-y-2">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Source assets</p>
            <OutputSourceLinks assetIds={output.asset_ids} assetsById={assetsById} currentHref={currentHref} />
          </div>

          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline">
              <AppLink href={buildJobDetailHref(output.job_id, currentHref)}>
                Open job
                <ArrowRight className="size-3.5" />
              </AppLink>
            </Button>
            {output.asset_ids.length === 1 ? (
              <Button asChild size="sm" variant="outline">
                <AppLink href={buildAssetDetailHref(output.asset_ids[0], currentHref)}>
                  Open asset
                  <ArrowRight className="size-3.5" />
                </AppLink>
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
    </div>
  );
}
