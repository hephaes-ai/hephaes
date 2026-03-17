"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, ArrowRightLeft, Database, Eye, RefreshCw, Waves } from "lucide-react";

import { AssetStatusBadge } from "@/components/asset-status-badge";
import { ConversionDialog } from "@/components/conversion-dialog";
import { useFeedback } from "@/components/feedback-provider";
import { TagActionPanel, TagBadgeList } from "@/components/tag-controls";
import { WorkflowStatusBadge } from "@/components/workflow-status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAsset, useBackendCache, useTags } from "@/hooks/use-backend";
import {
  attachTagToAsset,
  type AssetTag,
  BackendApiError,
  createTag,
  getErrorMessage,
  indexAsset,
    removeTagFromAsset,
    type TagSummary,
    type TopicModality,
  } from "@/lib/api";
import {
  formatDateTime,
  formatDuration,
  formatFileSize,
  formatJobType,
  getIndexActionLabel,
  isWorkflowActiveStatus,
} from "@/lib/format";

function AssetDetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-32" />
      <Skeleton className="h-28 rounded-xl" />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1.1fr)]">
        <Skeleton className="h-72 rounded-xl" />
        <Skeleton className="h-72 rounded-xl" />
      </div>
      <Skeleton className="h-80 rounded-xl" />
    </div>
  );
}

export function AssetDetailPageFallback() {
  return <AssetDetailSkeleton />;
}

function formatLabel(value: string) {
  return value.replace(/_/g, " ");
}

function findExistingTagByName(tags: TagSummary[], name: string) {
  const normalizedName = name.trim().toLowerCase();
  return tags.find((tag) => tag.name.trim().toLowerCase() === normalizedName);
}

function formatModality(modality: TopicModality) {
  if (modality === "scalar_series") {
    return "Scalar series";
  }

  return `${modality.slice(0, 1).toUpperCase()}${modality.slice(1)}`;
}

function formatRate(rateHz: number) {
  return `${rateHz.toFixed(rateHz >= 10 ? 0 : 1)} Hz`;
}

function InlineNotice({
  description,
  title,
  tone,
}: {
  description?: string;
  title: string;
  tone: "error" | "info";
}) {
  const className = tone === "info" ? "border-border bg-card" : "";

  return (
    <Alert className={className} variant={tone === "error" ? "destructive" : "default"}>
      <AlertTitle>{title}</AlertTitle>
      {description ? <AlertDescription>{description}</AlertDescription> : null}
    </Alert>
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

function MetadataEmptyState({
  description,
  title,
}: {
  description: string;
  title: string;
}) {
  return (
    <div className="rounded-lg border border-dashed px-4 py-8 text-sm text-muted-foreground">
      <p className="font-medium text-foreground">{title}</p>
      <p className="mt-2">{description}</p>
    </div>
  );
}

function buildJobDetailHref(jobId: string, returnHref: string) {
  return `/jobs/${jobId}?from=${encodeURIComponent(returnHref)}`;
}

export function AssetDetailPage({ assetId }: { assetId: string }) {
  const searchParams = useSearchParams();
  const { notify } = useFeedback();
  const { revalidateAssetLists, revalidateConversions, revalidateJobs, revalidateTags } = useBackendCache();
  const { data, error, isLoading, mutate } = useAsset(assetId);
  const tagsResponse = useTags();
  const [isConversionDialogOpen, setIsConversionDialogOpen] = React.useState(false);
  const [isRunningIndexAction, setIsRunningIndexAction] = React.useState(false);
  const [isUpdatingTags, setIsUpdatingTags] = React.useState(false);
  const [requestMessage, setRequestMessage] = React.useState<{
    description?: string;
    title: string;
    tone: "error" | "info";
  } | null>(null);

  const returnHref = (() => {
    const from = searchParams.get("from");
    if (!from || !from.startsWith("/") || from.startsWith("//")) {
      return "/";
    }

    return from;
  })();
  const currentDetailHref = React.useMemo(() => {
    const currentQuery = searchParams.toString();
    return currentQuery ? `/assets/${assetId}?${currentQuery}` : `/assets/${assetId}`;
  }, [assetId, searchParams]);

  React.useEffect(() => {
    if (!data) {
      return;
    }

    const isIndexingActive = (isRunningIndexAction ? "indexing" : data.asset.indexing_status) === "indexing";
    const hasActiveJobs = data.related_jobs.some((job) => isWorkflowActiveStatus(job.status));
    const hasActiveConversions = data.conversions.some((conversion) =>
      isWorkflowActiveStatus(conversion.status),
    );

    if (!isIndexingActive && !hasActiveJobs && !hasActiveConversions) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void mutate();
      void revalidateAssetLists();
      void revalidateJobs();
      void revalidateConversions();
    }, 1500);

    return () => window.clearInterval(intervalId);
  }, [data, isRunningIndexAction, mutate, revalidateAssetLists, revalidateConversions, revalidateJobs]);

  if (isLoading) {
    return <AssetDetailSkeleton />;
  }

  if (error) {
    const isMissingAsset = error instanceof BackendApiError && error.status === 404;

    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back to inventory
          </Link>
        </Button>
        <Alert variant="destructive">
          <AlertTitle>{isMissingAsset ? "Asset not found" : "Could not load asset"}</AlertTitle>
          <AlertDescription>{getErrorMessage(error)}</AlertDescription>
        </Alert>
        {!isMissingAsset ? (
          <div>
            <Button onClick={() => void mutate()} type="button" variant="outline">
              Try again
            </Button>
          </div>
        ) : null}
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const { asset, metadata } = data;
  const assetTags = data.tags;
  const relatedJobs = data.related_jobs;
  const conversions = data.conversions;
  const availableTags = tagsResponse.data ?? [];
  const effectiveStatus = isRunningIndexAction ? "indexing" : asset.indexing_status;
  const isActionDisabled = isRunningIndexAction || asset.indexing_status === "indexing";
  const modalityCounts = new Map<TopicModality, number>();

  for (const topic of metadata?.topics ?? []) {
    modalityCounts.set(topic.modality, (modalityCounts.get(topic.modality) ?? 0) + 1);
  }

  const modalitySummary = Array.from(modalityCounts.entries()).sort(([left], [right]) =>
    left.localeCompare(right),
  );
  const rawMetadataEntries = Object.entries(metadata?.raw_metadata ?? {}).filter(([, value]) => {
    if (value === null || value === undefined) {
      return false;
    }

    if (typeof value === "string") {
      return value.trim().length > 0;
    }

    return true;
  });

  async function onRunIndexAction() {
    if (isActionDisabled) {
      return;
    }

    setRequestMessage(null);
    setIsRunningIndexAction(true);

    try {
      const result = await indexAsset(asset.id);
      await mutate(result, { revalidate: false });
      await Promise.all([revalidateAssetLists(), revalidateJobs()]);
    } catch (indexError) {
      const message = getErrorMessage(indexError);

      setRequestMessage({
        description: message,
        title: "Could not index asset",
        tone: "error",
      });
      notify({
        description: message,
        title: "Indexing failed",
        tone: "error",
      });
      await Promise.all([mutate(), revalidateAssetLists(), revalidateJobs()]);
    } finally {
      setIsRunningIndexAction(false);
    }
  }

  async function refreshTagData() {
    await Promise.all([revalidateAssetLists(), revalidateTags()]);
  }

  async function attachTag(tag: TagSummary) {
    if (assetTags.some((existingTag) => existingTag.id === tag.id)) {
      setRequestMessage({
        description: `${asset.file_name} already has the ${tag.name} tag.`,
        title: "Tag already attached",
        tone: "info",
      });
      return;
    }

    setRequestMessage(null);
    setIsUpdatingTags(true);

    try {
      const result = await attachTagToAsset(asset.id, { tag_id: tag.id });
      await mutate(result, { revalidate: false });
      await refreshTagData();
    } catch (tagError) {
      const message = getErrorMessage(tagError);
      setRequestMessage({
        description: message,
        title: "Could not add tag",
        tone: "error",
      });
      notify({
        description: message,
        title: "Tag update failed",
        tone: "error",
      });
      await Promise.all([mutate(), refreshTagData()]);
    } finally {
      setIsUpdatingTags(false);
    }
  }

  async function onApplyExistingTag(tagId: string) {
    const selectedTag = availableTags.find((tag) => tag.id === tagId);
    if (!selectedTag) {
      setRequestMessage({
        description: "Select an existing tag to add it to this asset.",
        title: "Tag not found",
        tone: "error",
      });
      return;
    }

    await attachTag(selectedTag);
  }

  async function onCreateAndAttachTag(name: string) {
    const existingTag = findExistingTagByName(availableTags, name);
    if (existingTag) {
      await attachTag(existingTag);
      return;
    }

    setRequestMessage(null);
    setIsUpdatingTags(true);

    try {
      const createdTag = await createTag({ name });
      await revalidateTags();
      await attachTag(createdTag);
    } catch (tagError) {
      const message = getErrorMessage(tagError);
      setRequestMessage({
        description: message,
        title: "Could not create tag",
        tone: "error",
      });
      notify({
        description: message,
        title: "Tag creation failed",
        tone: "error",
      });
      await revalidateTags();
    } finally {
      setIsUpdatingTags(false);
    }
  }

  async function onRemoveTag(tag: AssetTag) {
    setRequestMessage(null);
    setIsUpdatingTags(true);

    try {
      const result = await removeTagFromAsset(asset.id, tag.id);
      await mutate(result, { revalidate: false });
      await refreshTagData();
    } catch (tagError) {
      const message = getErrorMessage(tagError);
      setRequestMessage({
        description: message,
        title: "Could not remove tag",
        tone: "error",
      });
      notify({
        description: message,
        title: "Tag removal failed",
        tone: "error",
      });
      await Promise.all([mutate(), refreshTagData()]);
    } finally {
      setIsUpdatingTags(false);
    }
  }

  return (
    <div className="space-y-6">
      <Button asChild size="sm" variant="ghost">
        <Link href={returnHref}>
          <ArrowLeft className="size-4" />
          Back to inventory
        </Link>
      </Button>

      <Card>
        <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            <CardTitle className="text-xl">{asset.file_name}</CardTitle>
            <CardDescription className="break-all">{asset.file_path}</CardDescription>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <AssetStatusBadge status={effectiveStatus} />
            <Button onClick={() => setIsConversionDialogOpen(true)} size="sm" type="button" variant="outline">
              <ArrowRightLeft className="size-3.5" />
              Convert
            </Button>
            <Button
              disabled={isActionDisabled}
              onClick={onRunIndexAction}
              size="sm"
              type="button"
              variant={asset.indexing_status === "failed" ? "destructive" : "outline"}
            >
              {effectiveStatus === "indexing" ? <RefreshCw className="size-3.5 animate-spin" /> : null}
              {getIndexActionLabel(asset.indexing_status, isRunningIndexAction)}
            </Button>
          </div>
        </CardHeader>
      </Card>

      {requestMessage ? (
        <InlineNotice
          description={requestMessage.description}
          title={requestMessage.title}
          tone={requestMessage.tone}
        />
      ) : null}

      {effectiveStatus === "pending" && !metadata ? (
        <InlineNotice
          description="Run indexing to extract duration, topic summaries, and visualization readiness for this asset."
          title="This asset has not been indexed yet"
          tone="info"
        />
      ) : null}

      {effectiveStatus === "indexing" ? (
        <InlineNotice
          description="The detail page is polling for updates and will show extracted metadata as soon as indexing completes."
          title="Indexing in progress"
          tone="info"
        />
      ) : null}

      {effectiveStatus === "failed" ? (
        <InlineNotice
          description={metadata?.indexing_error ?? "The backend could not extract metadata for this asset."}
          title="The latest indexing run failed"
          tone="error"
        />
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1.1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Asset details</CardTitle>
            <CardDescription>Current registry details from the backend.</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-4 sm:grid-cols-2">
              <MetadataField label="File type" value={<span className="uppercase">{asset.file_type}</span>} />
              <MetadataField label="File size" value={formatFileSize(asset.file_size)} />
              <MetadataField label="Registered" value={formatDateTime(asset.registered_time)} />
              <MetadataField
                label="Last indexed"
                value={formatDateTime(asset.last_indexed_time, "Not indexed yet")}
              />
              <div className="space-y-1 sm:col-span-2">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Asset ID</dt>
                <dd className="break-all text-sm font-medium text-foreground">{asset.id}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Tags</CardTitle>
            <CardDescription>Organize this asset with lightweight labels.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <TagBadgeList
              emptyLabel="No tags on this asset yet."
              onRemove={(tag) => void onRemoveTag(tag)}
              removable
              tags={assetTags}
            />
            <TagActionPanel
              applyButtonLabel="Add tag"
              availableTags={availableTags}
              createButtonLabel="Create and add"
              createInputLabel="Create a new tag"
              disabled={isUpdatingTags}
              emptyState="Create a tag below or reuse one from another asset."
              excludeTagIds={assetTags.map((tag) => tag.id)}
              onApplyTag={onApplyExistingTag}
              onCreateTag={onCreateAndAttachTag}
              selectLabel="Add an existing tag"
            />
            {tagsResponse.error ? (
              <p className="text-sm text-destructive">Could not load existing tags.</p>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="size-4" />
            Indexed metadata
          </CardTitle>
          <CardDescription>Persisted metadata from the latest indexing run.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {metadata ? (
            <>
              <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <MetadataField label="Duration" value={formatDuration(metadata.duration)} />
                <MetadataField label="Default episode" value={metadata.default_episode?.label ?? "Not available"} />
                <MetadataField label="Start time" value={formatDateTime(metadata.start_time)} />
                <MetadataField label="End time" value={formatDateTime(metadata.end_time)} />
                <MetadataField label="Topic count" value={metadata.topic_count} />
                <MetadataField label="Message count" value={metadata.message_count} />
                <MetadataField
                  label="Visual data"
                  value={metadata.visualization_summary?.has_visualizable_streams ? "Available" : "Not available"}
                />
                <MetadataField
                  label="Viewer lanes"
                  value={metadata.visualization_summary?.default_lane_count ?? "Not available"}
                />
              </dl>

              <div className="space-y-2">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Sensor types</p>
                {metadata.sensor_types.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {metadata.sensor_types.map((sensorType) => (
                      <Badge key={sensorType} variant="outline">
                        {sensorType}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No sensor categories were reported.</p>
                )}
              </div>

              <div className="space-y-2">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Modality mix</p>
                {modalitySummary.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {modalitySummary.map(([modality, count]) => (
                      <Badge key={modality} variant="secondary">
                        {formatModality(modality)} {count}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Modality summaries will appear after indexing.</p>
                )}
              </div>

              {rawMetadataEntries.length > 0 ? (
                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Profile details</p>
                  <div className="flex flex-wrap gap-2">
                    {rawMetadataEntries.map(([key, value]) => (
                      <Badge key={key} variant="outline">
                        {formatLabel(key)}: {String(value)}
                      </Badge>
                    ))}
                  </div>
                </div>
              ) : null}
            </>
          ) : effectiveStatus === "failed" ? (
            <MetadataEmptyState
              description="Retry indexing after fixing the source file or backend issue to regenerate metadata."
              title="No indexed metadata is available yet"
            />
          ) : effectiveStatus === "indexing" ? (
            <MetadataEmptyState
              description="The metadata panels will populate automatically once the backend finishes indexing."
              title="Metadata is on the way"
            />
          ) : (
            <MetadataEmptyState
              description="Use the index action above to extract duration, topic summaries, and visualization readiness."
              title="Metadata has not been generated"
            />
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Related jobs</CardTitle>
            <CardDescription>Recent backend work tied to this asset.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {relatedJobs.length > 0 ? (
              relatedJobs.map((job) => (
                <div key={job.id} className="space-y-3 rounded-xl border bg-muted/20 px-4 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 space-y-1">
                      <p className="text-sm font-medium text-foreground">{formatJobType(job.type)}</p>
                      <p className="break-all font-mono text-xs text-muted-foreground">{job.id}</p>
                    </div>
                    <WorkflowStatusBadge status={job.status} />
                  </div>
                  <dl className="grid gap-3 sm:grid-cols-2">
                    <MetadataField label="Created" value={formatDateTime(job.created_at)} />
                    <MetadataField label="Updated" value={formatDateTime(job.updated_at)} />
                  </dl>
                  {job.output_path ? (
                    <div className="space-y-1">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Output path</p>
                      <p className="break-all text-sm text-foreground">{job.output_path}</p>
                    </div>
                  ) : null}
                  {job.error_message ? (
                    <p className="text-sm text-destructive">{job.error_message}</p>
                  ) : null}
                  <div className="flex justify-end">
                    <Button asChild size="sm" variant="outline">
                      <Link href={buildJobDetailHref(job.id, currentDetailHref)}>
                        Open job
                        <ArrowRight className="size-3.5" />
                      </Link>
                    </Button>
                  </div>
                </div>
              ))
            ) : (
              <MetadataEmptyState
                description="Jobs will appear here after indexing, conversion, or visualization prep runs are started for this asset."
                title="No related jobs yet"
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Conversion history</CardTitle>
            <CardDescription>Recent conversion requests that include this asset.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {conversions.length > 0 ? (
              conversions.map((conversion) => (
                <div key={conversion.id} className="space-y-3 rounded-xl border bg-muted/20 px-4 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 space-y-1">
                      <p className="text-sm font-medium text-foreground">{conversion.id}</p>
                      <p className="text-xs text-muted-foreground">Linked job {conversion.job_id}</p>
                    </div>
                    <WorkflowStatusBadge status={conversion.status} />
                  </div>
                  <dl className="grid gap-3 sm:grid-cols-2">
                    <MetadataField label="Created" value={formatDateTime(conversion.created_at)} />
                    <MetadataField label="Updated" value={formatDateTime(conversion.updated_at)} />
                  </dl>
                  <div className="space-y-1">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Output path</p>
                    <p className="break-all text-sm text-foreground">
                      {conversion.output_path ?? "Not available yet"}
                    </p>
                  </div>
                  {conversion.error_message ? (
                    <p className="text-sm text-destructive">{conversion.error_message}</p>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Open the linked job to inspect output files and the latest execution details.
                    </p>
                  )}
                  <div className="flex justify-end">
                    <Button asChild size="sm" variant="outline">
                      <Link href={buildJobDetailHref(conversion.job_id, currentDetailHref)}>
                        Open job
                        <ArrowRight className="size-3.5" />
                      </Link>
                    </Button>
                  </div>
                </div>
              ))
            ) : (
              <MetadataEmptyState
                description="Conversion requests launched from this asset will show up here once the backend records them."
                title="No conversions yet"
              />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Waves className="size-4" />
              Topic summary
            </CardTitle>
            <CardDescription>Indexed topics, modalities, and stream rates.</CardDescription>
          </div>
          {metadata?.visualization_summary ? (
            <Badge
              className={
                metadata.visualization_summary.has_visualizable_streams
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200"
                  : ""
              }
              variant={metadata.visualization_summary.has_visualizable_streams ? "outline" : "secondary"}
            >
              <Eye className="size-3.5" />
              {metadata.visualization_summary.has_visualizable_streams
                ? `${metadata.visualization_summary.default_lane_count} visual lane${metadata.visualization_summary.default_lane_count === 1 ? "" : "s"} ready`
                : "No visual streams"}
            </Badge>
          ) : null}
        </CardHeader>
        <CardContent>
          {metadata?.topics.length ? (
            <div className="overflow-x-auto">
              <Table className="min-w-[720px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Topic</TableHead>
                    <TableHead>Message type</TableHead>
                    <TableHead>Messages</TableHead>
                    <TableHead>Rate</TableHead>
                    <TableHead>Modality</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {metadata.topics.map((topic) => (
                    <TableRow key={topic.name}>
                      <TableCell className="font-medium">{topic.name}</TableCell>
                      <TableCell className="text-muted-foreground">{topic.message_type}</TableCell>
                      <TableCell>{topic.message_count}</TableCell>
                      <TableCell>{formatRate(topic.rate_hz)}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{formatModality(topic.modality)}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <MetadataEmptyState
              description="Topic summaries appear here after a successful indexing run."
              title="No indexed topics to show"
            />
          )}
        </CardContent>
      </Card>

      <ConversionDialog
        assets={[asset]}
        onOpenChange={setIsConversionDialogOpen}
        open={isConversionDialogOpen}
      />
    </div>
  );
}
