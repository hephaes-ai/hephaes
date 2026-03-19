"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRightLeft,
  ArrowRight,
  ArrowUpDown,
  ChevronDown,
  ChevronUp,
  FolderOpen,
  RefreshCw,
  Search,
  Upload,
  X,
} from "lucide-react";

import { AssetStatusBadge } from "@/components/asset-status-badge";
import { ConversionDialog } from "@/components/conversion-dialog";
import { useFeedback } from "@/components/feedback-provider";
import { TagActionPanel, TagBadgeList } from "@/components/tag-controls";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAssets, useBackendCache, useOutputs, useTags } from "@/hooks/use-backend";
import type {
  AssetListQuery,
  AssetRegistrationSkip,
  AssetSummary,
  IndexingStatus,
  TagSummary,
} from "@/lib/api";
import {
  attachTagToAsset,
  BackendApiError,
  createTag,
  getErrorMessage,
  indexAsset,
  reindexAllAssets,
  scanDirectoryForAssets,
  uploadAssetFile,
} from "@/lib/api";
import type { AssetSelectionScope } from "@/lib/future-workflows";
import { formatDateTime, formatFileSize, getIndexActionLabel } from "@/lib/format";
import { buildOutputsHref, countOutputsByAsset } from "@/lib/outputs";
import { cn } from "@/lib/utils";
import { buildReplayHref } from "@/lib/visualization";

type InventorySort =
  | "file_name-asc"
  | "file_name-desc"
  | "file_size-asc"
  | "file_size-desc"
  | "registered-desc"
  | "registered-asc";
type SortColumn = "file_name" | "file_size" | "registered";
type SortDirection = "asc" | "desc";

const DEFAULT_SORT: InventorySort = "registered-desc";
const STATUS_OPTIONS: IndexingStatus[] = ["pending", "indexing", "indexed", "failed"];

interface FormMessage {
  description?: string;
  title: string;
  tone: "error" | "info" | "success";
}

interface ActiveFilterChip {
  key: string;
  label: string;
}

interface DirectoryScanFormState {
  directoryPath: string;
  recursive: boolean;
}

interface UploadProgressState {
  completed: number;
  total: number;
}

const DEFAULT_DIRECTORY_SCAN_FORM: DirectoryScanFormState = {
  directoryPath: "",
  recursive: true,
};

function FormNotice({ message }: { message: FormMessage }) {
  const className =
    message.tone === "success"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200"
      : message.tone === "info"
        ? "border-border bg-card"
        : "";

  return (
    <Alert className={className} variant={message.tone === "error" ? "destructive" : "default"}>
      <AlertTitle>{message.title}</AlertTitle>
      {message.description ? <AlertDescription>{message.description}</AlertDescription> : null}
    </Alert>
  );
}

function formatCount(count: number, noun: string) {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function summarizeSkipped(skipped: AssetRegistrationSkip[]) {
  if (skipped.length === 0) {
    return "";
  }

  const duplicateCount = skipped.filter((item) => item.reason === "duplicate").length;
  const invalidCount = skipped.filter((item) => item.reason === "invalid_path").length;
  const parts: string[] = [];

  if (duplicateCount > 0) {
    parts.push(`${formatCount(duplicateCount, "duplicate")} skipped`);
  }

  if (invalidCount > 0) {
    parts.push(`${formatCount(invalidCount, "invalid file")} skipped`);
  }

  const firstDetail = skipped[0]?.detail;
  if (firstDetail) {
    parts.push(firstDetail);
  }

  return parts.join(". ");
}

function classifyUploadedFileSkip(file: File, error: unknown): AssetRegistrationSkip | null {
  if (!(error instanceof BackendApiError)) {
    return null;
  }

  if (error.status === 409) {
    return {
      detail: error.message,
      file_path: file.name,
      reason: "duplicate",
    };
  }

  if (error.status === 400) {
    return {
      detail: error.message,
      file_path: file.name,
      reason: "invalid_path",
    };
  }

  return null;
}

function isValidSort(value: string | null): value is InventorySort {
  return (
    value === "file_name-asc" ||
    value === "file_name-desc" ||
    value === "file_size-asc" ||
    value === "file_size-desc" ||
    value === "registered-desc" ||
    value === "registered-asc"
  );
}

function parseSort(value: string | null) {
  const normalizedValue = isValidSort(value) ? value : DEFAULT_SORT;
  const [column, direction] = normalizedValue.split("-") as [SortColumn, SortDirection];

  return {
    column,
    direction,
    value: normalizedValue,
  };
}

function buildAssetDetailHref(assetId: string, inventoryHref: string) {
  return `/assets/${assetId}?from=${encodeURIComponent(inventoryHref)}`;
}

function buildInventoryReplayHref(assetId: string, inventoryHref: string) {
  return buildReplayHref({
    assetId,
    from: inventoryHref,
  });
}

function parseNonNegativeNumber(value: string | null) {
  if (!value) {
    return null;
  }

  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return null;
  }

  return parsed;
}

function parseMegabytesToBytes(value: string | null) {
  const megabytes = parseNonNegativeNumber(value);
  return megabytes === null ? null : megabytes * 1024 * 1024;
}

function parseDateBoundary(value: string | null, boundary: "start" | "end") {
  if (!value) {
    return null;
  }

  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  if (boundary === "end") {
    date.setHours(23, 59, 59, 999);
  }

  return date;
}

function formatFilterValue(value: string) {
  return value.replace(/_/g, " ");
}

function isValidIndexingStatus(value: string): value is IndexingStatus {
  return STATUS_OPTIONS.includes(value as IndexingStatus);
}

function SortButton({
  active,
  direction,
  disabled = false,
  label,
  onClick,
}: {
  active: boolean;
  direction: SortDirection;
  disabled?: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-1 py-1 text-left text-xs font-semibold tracking-wide text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-40",
        active && "text-foreground",
      )}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {label}
      {active ? (
        direction === "asc" ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />
      ) : (
        <ArrowUpDown className="size-3.5" />
      )}
    </button>
  );
}

function InventoryEmptyState({
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

function getBulkIndexActionLabel(assets: AssetSummary[], pendingAssetIds: Set<string>) {
  const actionableAssets = assets.filter(
    (asset) => asset.indexing_status !== "indexing" && !pendingAssetIds.has(asset.id),
  );

  if (actionableAssets.length === 0) {
    return "Index selected";
  }

  if (actionableAssets.every((asset) => asset.indexing_status === "failed")) {
    return "Retry selected";
  }

  if (actionableAssets.every((asset) => asset.indexing_status === "indexed")) {
    return "Reindex selected";
  }

  return "Index selected";
}

function getAssetTags(asset: AssetSummary) {
  return asset.tags ?? [];
}

function assetHasTag(asset: AssetSummary, tagId: string) {
  return getAssetTags(asset).some((tag) => tag.id === tagId);
}

function findExistingTagByName(tags: TagSummary[], name: string) {
  const normalizedName = name.trim().toLowerCase();
  return tags.find((tag) => tag.name.trim().toLowerCase() === normalizedName);
}

function getAssetSelectionScope({
  hasSearch,
  hasServerFilters,
  selectedCount,
}: {
  hasSearch: boolean;
  hasServerFilters: boolean;
  selectedCount: number;
}): AssetSelectionScope {
  if (selectedCount > 0) {
    return "selected-assets";
  }

  if (hasSearch) {
    return "search-results";
  }

  if (hasServerFilters) {
    return "filtered-assets";
  }

  return "all-assets";
}

function AssetsTable({
  assets,
  inventoryHref,
  onRunAssetAction,
  onSelectAll,
  onSelectAsset,
  onSort,
  outputCountsByAsset,
  pendingAssetIds,
  selectedAssetIds,
  sort,
}: {
  assets: AssetSummary[];
  inventoryHref: string;
  onRunAssetAction: (asset: AssetSummary) => void;
  onSelectAll: (checked: boolean | "indeterminate") => void;
  onSelectAsset: (assetId: string, checked: boolean | "indeterminate") => void;
  onSort: (column: SortColumn) => void;
  outputCountsByAsset: Map<string, number>;
  pendingAssetIds: Set<string>;
  selectedAssetIds: Set<string>;
  sort: ReturnType<typeof parseSort>;
}) {
  const router = useRouter();

  const selectedCount = assets.filter((asset) => selectedAssetIds.has(asset.id)).length;
  const allVisibleSelected = assets.length > 0 && selectedCount === assets.length;
  const someVisibleSelected = selectedCount > 0 && selectedCount < assets.length;

  function openAsset(assetId: string) {
    router.push(buildAssetDetailHref(assetId, inventoryHref));
  }

  function onRowKeyDown(event: React.KeyboardEvent<HTMLTableRowElement>, assetId: string) {
    if (event.target instanceof Element && event.target.closest("[data-stop-row-click='true']")) {
      return;
    }

    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }

    event.preventDefault();
    openAsset(assetId);
  }

  function onRowClick(event: React.MouseEvent<HTMLTableRowElement>, assetId: string) {
    if (event.target instanceof Element && event.target.closest("[data-stop-row-click='true']")) {
      return;
    }

    openAsset(assetId);
  }

  return (
    <div className="overflow-x-auto">
      <Table className="min-w-[860px]">
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">
              <div className="flex items-center justify-center" data-stop-row-click="true">
                <Checkbox
                  aria-label="Select all visible assets"
                  checked={allVisibleSelected ? true : someVisibleSelected ? "indeterminate" : false}
                  onCheckedChange={onSelectAll}
                />
              </div>
            </TableHead>
            <TableHead className="min-w-72">
              <SortButton
                active={sort.column === "file_name"}
                direction={sort.direction}
                label="File name"
                onClick={() => onSort("file_name")}
              />
            </TableHead>
            <TableHead>File type</TableHead>
            <TableHead>
              <SortButton
                active={sort.column === "file_size"}
                direction={sort.direction}
                label="File size"
                onClick={() => onSort("file_size")}
              />
            </TableHead>
            <TableHead>Indexing status</TableHead>
            <TableHead>
              <SortButton
                active={sort.column === "registered"}
                direction={sort.direction}
                label="Date added"
                onClick={() => onSort("registered")}
              />
            </TableHead>
            <TableHead>Last indexed</TableHead>
            <TableHead className="w-28 text-right">Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {assets.map((asset) => {
            const isSelected = selectedAssetIds.has(asset.id);
            const isRunningAction = pendingAssetIds.has(asset.id);
            const effectiveStatus: IndexingStatus = isRunningAction ? "indexing" : asset.indexing_status;
            const outputCount = outputCountsByAsset.get(asset.id) ?? 0;

            return (
              <TableRow
                key={asset.id}
                aria-label={`Open ${asset.file_name}`}
                className={cn("cursor-pointer", isSelected && "bg-muted/35")}
                onClick={(event) => onRowClick(event, asset.id)}
                onKeyDown={(event) => onRowKeyDown(event, asset.id)}
                role="link"
                tabIndex={0}
              >
                <TableCell>
                  <div className="flex items-center justify-center" data-stop-row-click="true">
                    <Checkbox
                      aria-label={`Select ${asset.file_name}`}
                      checked={isSelected}
                      onCheckedChange={(checked) => onSelectAsset(asset.id, checked)}
                    />
                  </div>
                </TableCell>
                <TableCell className="max-w-0">
                  <div className="space-y-1">
                    <div className="font-medium text-foreground">{asset.file_name}</div>
                    <div className="truncate text-xs text-muted-foreground">{asset.file_path}</div>
                    {getAssetTags(asset).length > 0 ? (
                      <TagBadgeList className="pt-1" maxVisible={2} tags={getAssetTags(asset)} />
                    ) : null}
                    {outputCount > 0 ? (
                      <div className="pt-1">
                        <Badge variant="outline">
                          {outputCount} output{outputCount === 1 ? "" : "s"}
                        </Badge>
                      </div>
                    ) : null}
                  </div>
                </TableCell>
                <TableCell className="uppercase text-muted-foreground">{asset.file_type}</TableCell>
                <TableCell>{formatFileSize(asset.file_size)}</TableCell>
                <TableCell>
                  <AssetStatusBadge status={effectiveStatus} />
                </TableCell>
                <TableCell>{formatDateTime(asset.registered_time)}</TableCell>
                <TableCell>{formatDateTime(asset.last_indexed_time, "Not indexed yet")}</TableCell>
                <TableCell className="text-right">
                  <div className="flex flex-wrap justify-end gap-2" data-stop-row-click="true">
                    {outputCount > 0 ? (
                      <Button asChild size="sm" type="button" variant="outline">
                        <Link href={buildOutputsHref({ assetId: asset.id })}>Outputs</Link>
                      </Button>
                    ) : null}
                    {asset.indexing_status === "indexed" ? (
                      <Button asChild size="sm" type="button" variant="secondary">
                        <Link href={buildInventoryReplayHref(asset.id, inventoryHref)}>Replay</Link>
                      </Button>
                    ) : null}
                    <Button
                      disabled={isRunningAction || asset.indexing_status === "indexing"}
                      onClick={() => onRunAssetAction(asset)}
                      size="sm"
                      type="button"
                      variant={asset.indexing_status === "failed" ? "destructive" : "outline"}
                    >
                      {isRunningAction ? <RefreshCw className="size-3.5 animate-spin" /> : null}
                      {getIndexActionLabel(asset.indexing_status, isRunningAction)}
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

function AssetsTableSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className="grid gap-3 rounded-lg border px-4 py-3 md:grid-cols-[40px_2fr_0.7fr_0.9fr_1fr_1fr_1fr]">
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      ))}
    </div>
  );
}

export function InventoryPageFallback() {
  return (
    <div className="space-y-8">
      <section className="space-y-2">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-5 w-96 max-w-full" />
      </section>

      <Card>
        <CardHeader className="space-y-4">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-24 rounded-xl" />
        </CardHeader>
        <CardContent>
          <AssetsTableSkeleton />
        </CardContent>
      </Card>
    </div>
  );
}

export function InventoryPage() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { notify } = useFeedback();
  const { revalidateAssetLists, revalidateJobs, revalidateTags } = useBackendCache();
  const uploadInputRef = React.useRef<HTMLInputElement | null>(null);

  const appliedSearch = searchParams.get("search")?.trim() ?? "";
  const activeTag = searchParams.get("tag")?.trim() ?? "";
  const activeType = searchParams.get("type")?.trim() ?? "";
  const activeStatus = searchParams.get("status")?.trim() ?? "";
  const minDuration = searchParams.get("min_duration")?.trim() ?? "";
  const maxDuration = searchParams.get("max_duration")?.trim() ?? "";
  const sizeMinMb = searchParams.get("size_min_mb")?.trim() ?? "";
  const sizeMaxMb = searchParams.get("size_max_mb")?.trim() ?? "";
  const registeredAfter = searchParams.get("registered_after")?.trim() ?? "";
  const registeredBefore = searchParams.get("registered_before")?.trim() ?? "";
  const sort = parseSort(searchParams.get("sort"));
  const searchParamsString = searchParams.toString();

  const [formMessage, setFormMessage] = React.useState<FormMessage | null>(null);
  const [isUploadingFiles, setIsUploadingFiles] = React.useState(false);
  const [uploadProgress, setUploadProgress] = React.useState<UploadProgressState | null>(null);
  const [isDirectoryScanDialogOpen, setIsDirectoryScanDialogOpen] = React.useState(false);
  const [directoryScanForm, setDirectoryScanForm] =
    React.useState<DirectoryScanFormState>(DEFAULT_DIRECTORY_SCAN_FORM);
  const [directoryScanMessage, setDirectoryScanMessage] = React.useState<FormMessage | null>(null);
  const [isScanningDirectory, setIsScanningDirectory] = React.useState(false);
  const [searchInput, setSearchInput] = React.useState(appliedSearch);
  const [isBrowsePanelOpen, setIsBrowsePanelOpen] = React.useState(false);
  const [isConversionDialogOpen, setIsConversionDialogOpen] = React.useState(false);
  const [isBulkIndexingSelection, setIsBulkIndexingSelection] = React.useState(false);
  const [isIndexingPendingAssets, setIsIndexingPendingAssets] = React.useState(false);
  const [isUpdatingSelectionTags, setIsUpdatingSelectionTags] = React.useState(false);
  const [pendingAssetIds, setPendingAssetIds] = React.useState<Set<string>>(new Set());
  const [selectedAssetIds, setSelectedAssetIds] = React.useState<Set<string>>(new Set());

  React.useEffect(() => {
    setSearchInput(appliedSearch);
  }, [appliedSearch]);

  React.useEffect(() => {
    if (searchParamsString.length > 0) {
      setIsBrowsePanelOpen(true);
    }
  }, [searchParamsString]);

  const normalizedMinDuration = parseNonNegativeNumber(minDuration) ?? undefined;
  const normalizedMaxDuration = parseNonNegativeNumber(maxDuration) ?? undefined;
  const normalizedStatus = isValidIndexingStatus(activeStatus) ? activeStatus : undefined;

  const serverQueryCandidate: AssetListQuery = {
    max_duration: normalizedMaxDuration,
    min_duration: normalizedMinDuration,
    search: appliedSearch || undefined,
    status: normalizedStatus,
    tag: activeTag || undefined,
    type: activeType || undefined,
  };
  const serverQuery = Object.values(serverQueryCandidate).some((value) => value !== undefined)
    ? serverQueryCandidate
    : undefined;
  const hasServerFilters = Boolean(serverQuery);

  const assetsResponse = useAssets(serverQuery);
  const allAssetsResponse = useAssets(hasServerFilters ? undefined : null);
  const outputsResponse = useOutputs();
  const tagsResponse = useTags();

  const assets = assetsResponse.data ?? [];
  const allAssets = hasServerFilters ? (allAssetsResponse.data ?? assets) : assets;
  const totalRegisteredCount = hasServerFilters ? allAssetsResponse.data?.length : assets.length;
  const outputCountsByAsset = React.useMemo(
    () => countOutputsByAsset(outputsResponse.data),
    [outputsResponse.data],
  );
  const availableTags = tagsResponse.data ?? [];
  const selectableFilterTags = availableTags.filter((tag) => {
    if (tag.asset_count > 0) {
      return true;
    }

    return activeTag.length > 0 && tag.name.trim().toLowerCase() === activeTag.toLowerCase();
  });

  const availableFileTypes = Array.from(new Set(allAssets.map((asset) => asset.file_type))).sort((left, right) =>
    left.localeCompare(right, undefined, { sensitivity: "base" }),
  );

  const minSizeBytes = parseMegabytesToBytes(sizeMinMb);
  const maxSizeBytes = parseMegabytesToBytes(sizeMaxMb);
  const registeredAfterDate = parseDateBoundary(registeredAfter, "start");
  const registeredBeforeDate = parseDateBoundary(registeredBefore, "end");

  const locallyFilteredAssets = assets.filter((asset) => {
    if (minSizeBytes !== null && asset.file_size < minSizeBytes) {
      return false;
    }

    if (maxSizeBytes !== null && asset.file_size > maxSizeBytes) {
      return false;
    }

    if (registeredAfterDate || registeredBeforeDate) {
      const registeredTime = new Date(asset.registered_time);
      if (Number.isNaN(registeredTime.getTime())) {
        return false;
      }

      if (registeredAfterDate && registeredTime < registeredAfterDate) {
        return false;
      }

      if (registeredBeforeDate && registeredTime > registeredBeforeDate) {
        return false;
      }
    }

    return true;
  });

  const visibleAssets = [...locallyFilteredAssets].sort((left, right) => {
    if (sort.column === "file_name") {
      const comparison = left.file_name.localeCompare(right.file_name, undefined, {
        sensitivity: "base",
      });
      return sort.direction === "asc" ? comparison : -comparison;
    }

    if (sort.column === "file_size") {
      const comparison = left.file_size - right.file_size;
      return sort.direction === "asc" ? comparison : -comparison;
    }

    const leftTime = new Date(left.registered_time).getTime();
    const rightTime = new Date(right.registered_time).getTime();
    const comparison = leftTime - rightTime;
    return sort.direction === "asc" ? comparison : -comparison;
  });

  React.useEffect(() => {
    const visibleIds = new Set(visibleAssets.map((asset) => asset.id));

    setSelectedAssetIds((current) => {
      let changed = false;
      const next = new Set<string>();

      for (const assetId of current) {
        if (visibleIds.has(assetId)) {
          next.add(assetId);
        } else {
          changed = true;
        }
      }

      return changed ? next : current;
    });
  }, [visibleAssets]);

  function updateBrowseState(updates: Record<string, string | null>) {
    const nextParams = new URLSearchParams(searchParams.toString());

    for (const [key, value] of Object.entries(updates)) {
      const normalizedValue = value?.trim() ?? "";
      if (!normalizedValue) {
        nextParams.delete(key);
      } else {
        nextParams.set(key, normalizedValue);
      }
    }

    const nextQueryString = nextParams.toString();
    const nextHref = nextQueryString ? `${pathname}?${nextQueryString}` : pathname;

    React.startTransition(() => {
      router.replace(nextHref, { scroll: false });
    });
  }

  function resetBrowseState() {
    setSearchInput("");
    setSelectedAssetIds(new Set());
    setIsBrowsePanelOpen(false);

    React.startTransition(() => {
      router.replace(pathname, { scroll: false });
    });
  }

  function onShowPlannedFeature(title: string, description: string) {
    setFormMessage({
      description,
      title,
      tone: "info",
    });
  }

  function onOpenUploadPicker() {
    if (isUploadingFiles) {
      return;
    }

    uploadInputRef.current?.click();
  }

  async function onUploadFiles(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";

    if (files.length === 0) {
      return;
    }

    setFormMessage(null);
    setIsUploadingFiles(true);
    setUploadProgress({
      completed: 0,
      total: files.length,
    });

    const registeredAssets: AssetSummary[] = [];
    const skipped: AssetRegistrationSkip[] = [];
    const unexpectedErrors: string[] = [];

    try {
      for (const [index, file] of files.entries()) {
        try {
          const asset = await uploadAssetFile(file);
          registeredAssets.push(asset);
        } catch (uploadError) {
          const classifiedSkip = classifyUploadedFileSkip(file, uploadError);
          if (classifiedSkip) {
            skipped.push(classifiedSkip);
          } else {
            unexpectedErrors.push(`${file.name}: ${getErrorMessage(uploadError)}`);
          }
        } finally {
          setUploadProgress({
            completed: index + 1,
            total: files.length,
          });
        }
      }

      if (registeredAssets.length > 0) {
        await revalidateAssetLists();
      }

      const descriptionParts: string[] = [];

      if (registeredAssets.length > 0) {
        descriptionParts.push(`${formatCount(registeredAssets.length, "file")} uploaded to inventory`);
      }

      if (skipped.length > 0) {
        descriptionParts.push(summarizeSkipped(skipped));
      }

      if (unexpectedErrors.length > 0) {
        descriptionParts.push(
          `${unexpectedErrors[0]}${unexpectedErrors.length > 1 ? ` ${unexpectedErrors.length - 1} more upload${unexpectedErrors.length - 1 === 1 ? "" : "s"} failed.` : ""}`,
        );
      }

      const description = descriptionParts.join(". ") || "No uploaded files changed the inventory.";
      const tone: FormMessage["tone"] =
        unexpectedErrors.length > 0 && registeredAssets.length === 0 && skipped.length === 0
          ? "error"
          : registeredAssets.length > 0 && skipped.length === 0 && unexpectedErrors.length === 0
            ? "success"
            : "info";
      const title =
        registeredAssets.length > 0 && skipped.length === 0 && unexpectedErrors.length === 0
          ? "Uploads finished"
          : registeredAssets.length > 0
            ? "Uploads finished with warnings"
            : unexpectedErrors.length > 0 && skipped.length === 0
              ? "Uploads failed"
              : "No uploaded files were added";

      setFormMessage({
        description,
        title,
        tone,
      });
      if (tone !== "success") {
        notify({
          description,
          title,
          tone,
        });
      }
    } finally {
      setIsUploadingFiles(false);
      setUploadProgress(null);
    }
  }

  function onDirectoryScanDialogChange(nextOpen: boolean) {
    if (!nextOpen && isScanningDirectory) {
      return;
    }

    setIsDirectoryScanDialogOpen(nextOpen);

    if (!nextOpen) {
      setDirectoryScanForm(DEFAULT_DIRECTORY_SCAN_FORM);
      setDirectoryScanMessage(null);
    }
  }

  async function onScanDirectory(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const normalizedPath = directoryScanForm.directoryPath.trim();
    if (!normalizedPath) {
      setDirectoryScanMessage({
        description: "Enter a local directory path before scanning.",
        title: "Directory required",
        tone: "error",
      });
      return;
    }

    setDirectoryScanMessage(null);
    setIsScanningDirectory(true);

    try {
      const result = await scanDirectoryForAssets({
        directory_path: normalizedPath,
        recursive: directoryScanForm.recursive,
      });

      if (result.registered_assets.length > 0) {
        await revalidateAssetLists();
      }

      const descriptionParts = [
        `Scanned ${result.scanned_directory} and found ${formatCount(result.discovered_file_count, "supported file")}`,
      ];

      if (result.registered_assets.length > 0) {
        descriptionParts.push(`${formatCount(result.registered_assets.length, "file")} added to inventory`);
      }

      if (result.skipped.length > 0) {
        descriptionParts.push(summarizeSkipped(result.skipped));
      }

      if (result.discovered_file_count === 0) {
        descriptionParts.push("No supported .bag or .mcap files were discovered");
      }

      const description = descriptionParts.join(". ");
      const tone: FormMessage["tone"] =
        result.registered_assets.length > 0 && result.skipped.length === 0
          ? "success"
          : result.registered_assets.length > 0 || result.skipped.length > 0 || result.discovered_file_count === 0
            ? "info"
            : "error";
      const title =
        result.registered_assets.length > 0 && result.skipped.length === 0
          ? "Directory scanned"
          : result.registered_assets.length > 0
            ? "Directory scanned with warnings"
            : result.discovered_file_count === 0
              ? "No supported files found"
              : "No new files were added";

      setIsDirectoryScanDialogOpen(false);
      setDirectoryScanForm(DEFAULT_DIRECTORY_SCAN_FORM);
      setFormMessage({
        description,
        title,
        tone,
      });
      notify({
        description,
        title,
        tone,
      });
    } catch (scanError) {
      const message = getErrorMessage(scanError);
      setDirectoryScanMessage({
        description: message,
        title: "Could not scan directory",
        tone: "error",
      });
      notify({
        description: message,
        title: "Directory scan failed",
        tone: "error",
      });
    } finally {
      setIsScanningDirectory(false);
    }
  }

  function onSearchSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    updateBrowseState({ search: searchInput });
  }

  function onClearSearch() {
    setSearchInput("");
    updateBrowseState({ search: null });
  }

  function onToggleTypeFilter(fileType: string) {
    updateBrowseState({ type: activeType === fileType ? null : fileType });
  }

  function onToggleStatusFilter(status: IndexingStatus) {
    updateBrowseState({ status: activeStatus === status ? null : status });
  }

  function onSort(column: SortColumn) {
    const nextSortValue =
      sort.column === column
        ? (`${column}-${sort.direction === "asc" ? "desc" : "asc"}` as InventorySort)
        : ((column === "registered" ? "registered-desc" : `${column}-asc`) as InventorySort);

    updateBrowseState({
      sort: nextSortValue === DEFAULT_SORT ? null : nextSortValue,
    });
  }

  function onSelectAsset(assetId: string, checked: boolean | "indeterminate") {
    setSelectedAssetIds((current) => {
      const next = new Set(current);

      if (checked === true) {
        next.add(assetId);
      } else {
        next.delete(assetId);
      }

      return next;
    });
  }

  function onSelectAll(checked: boolean | "indeterminate") {
    setSelectedAssetIds((current) => {
      const next = new Set(current);

      if (checked === true || checked === "indeterminate") {
        for (const asset of visibleAssets) {
          next.add(asset.id);
        }
      } else {
        for (const asset of visibleAssets) {
          next.delete(asset.id);
        }
      }

      return next;
    });
  }

  const activeFilterChips: ActiveFilterChip[] = [];

  if (appliedSearch) {
    activeFilterChips.push({ key: "search", label: `Search: ${appliedSearch}` });
  }

  if (activeTag) {
    const activeTagName = availableTags.find((tag) => tag.name.trim().toLowerCase() === activeTag.toLowerCase())?.name;
    activeFilterChips.push({ key: "tag", label: `Tag: ${activeTagName ?? activeTag}` });
  }

  if (activeType) {
    activeFilterChips.push({ key: "type", label: `Type: ${formatFilterValue(activeType)}` });
  }

  if (activeStatus) {
    activeFilterChips.push({ key: "status", label: `Status: ${formatFilterValue(activeStatus)}` });
  }

  if (minDuration) {
    activeFilterChips.push({ key: "min_duration", label: `Min duration: ${minDuration} s` });
  }

  if (maxDuration) {
    activeFilterChips.push({ key: "max_duration", label: `Max duration: ${maxDuration} s` });
  }

  if (sizeMinMb) {
    activeFilterChips.push({ key: "size_min_mb", label: `Min size: ${sizeMinMb} MB` });
  }

  if (sizeMaxMb) {
    activeFilterChips.push({ key: "size_max_mb", label: `Max size: ${sizeMaxMb} MB` });
  }

  if (registeredAfter) {
    activeFilterChips.push({ key: "registered_after", label: `Added after: ${registeredAfter}` });
  }

  if (registeredBefore) {
    activeFilterChips.push({ key: "registered_before", label: `Added before: ${registeredBefore}` });
  }

  const hasAppliedFilters = activeFilterChips.length > 0;
  const selectedCount = selectedAssetIds.size;
  const selectedVisibleAssets = visibleAssets.filter((asset) => selectedAssetIds.has(asset.id));
  const actionableSelectedAssets = selectedVisibleAssets.filter(
    (asset) => asset.indexing_status !== "indexing" && !pendingAssetIds.has(asset.id),
  );
  const pendingOrFailedAssetCount = allAssets.filter(
    (asset) => asset.indexing_status === "pending" || asset.indexing_status === "failed",
  ).length;
  const resultsCountLabel = `${visibleAssets.length} result${visibleAssets.length === 1 ? "" : "s"}`;
  const totalCountLabel =
    typeof totalRegisteredCount === "number" ? `${totalRegisteredCount} registered` : "Loading total";
  const inventoryHref = searchParamsString ? `${pathname}?${searchParamsString}` : pathname;
  const selectionScope = getAssetSelectionScope({
    hasSearch: appliedSearch.length > 0,
    hasServerFilters,
    selectedCount,
  });
  const uploadButtonLabel =
    isUploadingFiles && uploadProgress
      ? `Uploading ${uploadProgress.completed}/${uploadProgress.total}`
      : "Upload files";

  const isLoading = assetsResponse.isLoading;
  const isInventoryEmpty = !hasAppliedFilters && totalRegisteredCount === 0;
  const showNoResults = !isLoading && !assetsResponse.error && !isInventoryEmpty && visibleAssets.length === 0;
  const shouldPollAssets =
    isBulkIndexingSelection ||
    isIndexingPendingAssets ||
    pendingAssetIds.size > 0 ||
    assets.some((asset) => asset.indexing_status === "indexing") ||
    allAssets.some((asset) => asset.indexing_status === "indexing");

  React.useEffect(() => {
    if (!shouldPollAssets) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void assetsResponse.mutate();
      if (hasServerFilters) {
        void allAssetsResponse.mutate();
      }
    }, 1500);

    return () => window.clearInterval(intervalId);
  }, [allAssetsResponse, assetsResponse, hasServerFilters, shouldPollAssets]);

  async function refreshAssetLists() {
    await Promise.all([revalidateAssetLists(), revalidateJobs()]);
  }

  async function refreshTagAwareData() {
    await Promise.all([revalidateAssetLists(), revalidateTags()]);
  }

  async function onRunAssetAction(asset: AssetSummary) {
    if (asset.indexing_status === "indexing" || pendingAssetIds.has(asset.id)) {
      return;
    }

    setFormMessage(null);
    setPendingAssetIds((current) => new Set(current).add(asset.id));

    try {
      await indexAsset(asset.id);
      await refreshAssetLists();
    } catch (indexError) {
      const message = getErrorMessage(indexError);

      setFormMessage({
        description: `${asset.file_name}: ${message}`,
        title: "Indexing failed",
        tone: "error",
      });
      notify({
        description: `${asset.file_name}: ${message}`,
        title: "Could not index asset",
        tone: "error",
      });
      await refreshAssetLists();
    } finally {
      setPendingAssetIds((current) => {
        const next = new Set(current);
        next.delete(asset.id);
        return next;
      });
    }
  }

  async function onRunBulkIndex() {
    if (actionableSelectedAssets.length === 0) {
      return;
    }

    setFormMessage(null);
    setIsBulkIndexingSelection(true);

    try {
      setPendingAssetIds((current) => {
        const next = new Set(current);
        for (const asset of actionableSelectedAssets) {
          next.add(asset.id);
        }
        return next;
      });

      let indexedCount = 0;
      const failureMessages: string[] = [];

      for (const asset of actionableSelectedAssets) {
        try {
          await indexAsset(asset.id);
          indexedCount += 1;
        } catch (indexError) {
          failureMessages.push(`${asset.file_name}: ${getErrorMessage(indexError)}`);
        } finally {
          setPendingAssetIds((current) => {
            const next = new Set(current);
            next.delete(asset.id);
            return next;
          });
          await refreshAssetLists();
        }
      }

      if (indexedCount > 0 && failureMessages.length === 0) {
        return;
      }

      if (indexedCount > 0 && failureMessages.length > 0) {
        const description = `${indexedCount} asset${indexedCount === 1 ? "" : "s"} indexed. ${failureMessages[0]}${failureMessages.length > 1 ? ` ${failureMessages.length - 1} more failed.` : ""}`;

        setFormMessage({
          description,
          title: "Selection indexed with warnings",
          tone: "info",
        });
        notify({
          description,
          title: "Partial indexing complete",
          tone: "info",
        });
        return;
      }

      const description = failureMessages[0] ?? "No selected assets could be indexed.";
      setFormMessage({
        description,
        title: "Selected assets failed to index",
        tone: "error",
      });
      notify({
        description,
        title: "Bulk indexing failed",
        tone: "error",
      });
    } finally {
      setIsBulkIndexingSelection(false);
    }
  }

  async function onIndexPendingAssets() {
    setFormMessage(null);
    setIsIndexingPendingAssets(true);

    try {
      const result = await reindexAllAssets();
      await refreshAssetLists();

      if (result.total_requested === 0) {
        notify({
          description: "There were no pending or failed assets to index.",
          title: "Nothing to index",
          tone: "info",
        });
        return;
      }

      if (result.failed_assets.length > 0) {
        const description = `${result.indexed_assets.length} asset${result.indexed_assets.length === 1 ? "" : "s"} indexed. ${result.failed_assets.length} asset${result.failed_assets.length === 1 ? "" : "s"} failed.`;

        setFormMessage({
          description,
          title: "Pending indexing completed with warnings",
          tone: "info",
        });
        notify({
          description,
          title: "Index pending finished",
          tone: "info",
        });
        return;
      }
    } catch (indexError) {
      const message = getErrorMessage(indexError);

      setFormMessage({
        description: message,
        title: "Could not index pending assets",
        tone: "error",
      });
      notify({
        description: message,
        title: "Index pending failed",
        tone: "error",
      });
      await refreshAssetLists();
    } finally {
      setIsIndexingPendingAssets(false);
    }
  }

  async function applyTagToSelectedAssets(tag: TagSummary) {
    const assetsNeedingTag = selectedVisibleAssets.filter((asset) => !assetHasTag(asset, tag.id));

    if (assetsNeedingTag.length === 0) {
      setFormMessage({
        description: `All selected assets already have the ${tag.name} tag.`,
        title: "Selection already tagged",
        tone: "info",
      });
      return;
    }

    setFormMessage(null);
    setIsUpdatingSelectionTags(true);

    try {
      let taggedCount = 0;
      const failureMessages: string[] = [];

      for (const asset of assetsNeedingTag) {
        try {
          await attachTagToAsset(asset.id, { tag_id: tag.id });
          taggedCount += 1;
        } catch (tagError) {
          failureMessages.push(`${asset.file_name}: ${getErrorMessage(tagError)}`);
        }
      }

      await refreshTagAwareData();

      if (failureMessages.length === 0) {
        return;
      }

      if (taggedCount > 0) {
        const description = `${taggedCount} asset${taggedCount === 1 ? "" : "s"} tagged with ${tag.name}. ${failureMessages[0]}${failureMessages.length > 1 ? ` ${failureMessages.length - 1} more failed.` : ""}`;
        setFormMessage({
          description,
          title: "Tags applied with warnings",
          tone: "info",
        });
        notify({
          description,
          title: "Bulk tag update finished",
          tone: "info",
        });
        return;
      }

      const description = failureMessages[0] ?? `No selected assets could be tagged with ${tag.name}.`;
      setFormMessage({
        description,
        title: "Could not apply tag",
        tone: "error",
      });
      notify({
        description,
        title: "Bulk tag update failed",
        tone: "error",
      });
    } finally {
      setIsUpdatingSelectionTags(false);
    }
  }

  async function onApplyExistingTagToSelection(tagId: string) {
    const selectedTag = availableTags.find((tag) => tag.id === tagId);
    if (!selectedTag) {
      setFormMessage({
        description: "Select an existing tag to apply it to the current selection.",
        title: "Tag not found",
        tone: "error",
      });
      return;
    }

    await applyTagToSelectedAssets(selectedTag);
  }

  async function onCreateAndApplyTagToSelection(name: string) {
    const existingTag = findExistingTagByName(availableTags, name);

    if (existingTag) {
      await applyTagToSelectedAssets(existingTag);
      return;
    }

    setFormMessage(null);
    setIsUpdatingSelectionTags(true);

    try {
      const createdTag = await createTag({ name });
      await revalidateTags();
      await applyTagToSelectedAssets(createdTag);
    } catch (tagError) {
      const message = getErrorMessage(tagError);
      setFormMessage({
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
      setIsUpdatingSelectionTags(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="space-y-2">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">Asset inventory</h1>
            <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
              {totalCountLabel}
            </span>
          </div>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Browse the live backend inventory with search, filters, and table sorting while keeping the
            registered assets table as the main surface.
          </p>
        </div>
      </section>

      {formMessage ? <FormNotice message={formMessage} /> : null}

      <Card className="flex-1">
        <CardHeader className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <FolderOpen className="size-4" />
                Registered assets
              </CardTitle>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="h-6" variant="secondary">
                {resultsCountLabel}
              </Badge>
              {typeof totalRegisteredCount === "number" && totalRegisteredCount !== visibleAssets.length ? (
                <Badge className="h-6" variant="outline">
                  of {totalRegisteredCount}
                </Badge>
              ) : null}
              {selectedCount > 0 ? (
                <Badge className="h-6" variant="outline">
                  {selectedCount} selected
                </Badge>
              ) : null}
              {pendingOrFailedAssetCount > 0 || isIndexingPendingAssets ? (
                <Button
                  disabled={isIndexingPendingAssets}
                  onClick={onIndexPendingAssets}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  {isIndexingPendingAssets ? <RefreshCw className="size-3.5 animate-spin" /> : null}
                  Index pending
                </Button>
              ) : null}
              {selectedCount > 0 ? (
                <Button
                  disabled={actionableSelectedAssets.length === 0}
                  onClick={onRunBulkIndex}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  {actionableSelectedAssets.length === 0 ? null : isBulkIndexingSelection ? (
                    <RefreshCw className="size-3.5 animate-spin" />
                  ) : null}
                  {getBulkIndexActionLabel(selectedVisibleAssets, pendingAssetIds)}
                </Button>
              ) : null}
              {selectedCount > 0 ? (
                <Button onClick={() => setIsConversionDialogOpen(true)} size="sm" type="button" variant="outline">
                  <ArrowRightLeft className="size-3.5" />
                  Convert
                </Button>
              ) : null}
              {selectedCount > 0 ? (
                <Button onClick={() => setSelectedAssetIds(new Set())} size="sm" type="button" variant="ghost">
                  Clear selection
                </Button>
              ) : null}
              <Button
                aria-expanded={isBrowsePanelOpen}
                onClick={() => setIsBrowsePanelOpen((current) => !current)}
                size="sm"
                type="button"
                variant="outline"
              >
                Search & filters{hasAppliedFilters ? ` (${activeFilterChips.length})` : ""}
                <ChevronDown className={cn("size-4 transition-transform", isBrowsePanelOpen && "rotate-180")} />
              </Button>
              <Button
                className="shrink-0"
                disabled={isUploadingFiles}
                onClick={onOpenUploadPicker}
                size="sm"
                type="button"
                variant="outline"
              >
                <Upload className="size-4" />
                {uploadButtonLabel}
              </Button>
              <Button
                className="shrink-0"
                disabled={isScanningDirectory}
                onClick={() => setIsDirectoryScanDialogOpen(true)}
                size="sm"
                type="button"
                variant="outline"
              >
                <FolderOpen className="size-4" />
                {isScanningDirectory ? "Scanning..." : "Scan directory"}
              </Button>
              <Button
                className="shrink-0"
                onClick={() => {
                  void Promise.all([revalidateAssetLists(), revalidateTags()]);
                }}
                size="sm"
                type="button"
                variant="outline"
              >
                <RefreshCw className="size-4" />
                Refresh
              </Button>
            </div>
          </div>

          <div
            className={cn(
              "grid transition-all duration-200 ease-out",
              isBrowsePanelOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
            )}
          >
            <div className="overflow-hidden">
              <div className="space-y-4 rounded-xl border bg-muted/20 p-4">
                <form className="flex flex-col gap-3 lg:flex-row" onSubmit={onSearchSubmit}>
                  <div className="flex-1">
                    <Label className="mb-2 text-xs uppercase tracking-wide text-muted-foreground" htmlFor="asset-search">
                      Search
                    </Label>
                    <div className="flex gap-2">
                      <Input
                        id="asset-search"
                        onChange={(event) => setSearchInput(event.target.value)}
                        placeholder="Search by file name"
                        value={searchInput}
                      />
                      <Button size="sm" type="submit" variant="outline">
                        <Search className="size-4" />
                        Search
                      </Button>
                      {(searchInput.length > 0 || appliedSearch.length > 0) && (
                        <Button onClick={onClearSearch} size="sm" type="button" variant="ghost">
                          <X className="size-4" />
                          Clear
                        </Button>
                      )}
                    </div>
                  </div>
                </form>

                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,240px)]">
                  <div className="space-y-2">
                    <Label className="text-xs uppercase tracking-wide text-muted-foreground">File type</Label>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        onClick={() => updateBrowseState({ type: null })}
                        size="sm"
                        type="button"
                        variant={activeType ? "outline" : "secondary"}
                      >
                        All
                      </Button>
                      {availableFileTypes.map((fileType) => (
                        <Button
                          key={fileType}
                          onClick={() => onToggleTypeFilter(fileType)}
                          size="sm"
                          type="button"
                          variant={activeType === fileType ? "secondary" : "outline"}
                        >
                          {fileType.toUpperCase()}
                        </Button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-xs uppercase tracking-wide text-muted-foreground">Indexing status</Label>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        onClick={() => updateBrowseState({ status: null })}
                        size="sm"
                        type="button"
                        variant={activeStatus ? "outline" : "secondary"}
                      >
                        All
                      </Button>
                      {STATUS_OPTIONS.map((status) => (
                        <Button
                          key={status}
                          onClick={() => onToggleStatusFilter(status)}
                          size="sm"
                          type="button"
                          variant={activeStatus === status ? "secondary" : "outline"}
                        >
                          {formatFilterValue(status)}
                        </Button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="tag-filter">
                      Tag
                    </Label>
                    <NativeSelect
                      id="tag-filter"
                      onChange={(event) => updateBrowseState({ tag: event.target.value || null })}
                      value={activeTag}
                    >
                      <option value="">All tags</option>
                      {selectableFilterTags.map((tag) => (
                        <option key={tag.id} value={tag.name}>
                          {tag.name}
                        </option>
                      ))}
                    </NativeSelect>
                    {tagsResponse.error ? (
                      <p className="text-xs text-destructive">Could not load tags for filtering.</p>
                    ) : null}
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  <div className="space-y-2">
                    <Label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="min-duration">
                      Min duration (s)
                    </Label>
                    <Input
                      id="min-duration"
                      min="0"
                      onChange={(event) => updateBrowseState({ min_duration: event.target.value })}
                      placeholder="Any"
                      step="1"
                      type="number"
                      value={minDuration}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="max-duration">
                      Max duration (s)
                    </Label>
                    <Input
                      id="max-duration"
                      min="0"
                      onChange={(event) => updateBrowseState({ max_duration: event.target.value })}
                      placeholder="Any"
                      step="1"
                      type="number"
                      value={maxDuration}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="size-min">
                      Min size (MB)
                    </Label>
                    <Input
                      id="size-min"
                      min="0"
                      onChange={(event) => updateBrowseState({ size_min_mb: event.target.value })}
                      placeholder="Any"
                      step="0.1"
                      type="number"
                      value={sizeMinMb}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="size-max">
                      Max size (MB)
                    </Label>
                    <Input
                      id="size-max"
                      min="0"
                      onChange={(event) => updateBrowseState({ size_max_mb: event.target.value })}
                      placeholder="Any"
                      step="0.1"
                      type="number"
                      value={sizeMaxMb}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="registered-after">
                      Added after
                    </Label>
                    <Input
                      id="registered-after"
                      onChange={(event) => updateBrowseState({ registered_after: event.target.value })}
                      type="date"
                      value={registeredAfter}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="registered-before">
                      Added before
                    </Label>
                    <Input
                      id="registered-before"
                      onChange={(event) => updateBrowseState({ registered_before: event.target.value })}
                      type="date"
                      value={registeredBefore}
                    />
                  </div>
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
                          updateBrowseState({ [filter.key]: null });
                        }}
                        size="xs"
                        type="button"
                        variant="outline"
                      >
                        {filter.label}
                        <X className="size-3" />
                      </Button>
                    ))}
                    <Button onClick={resetBrowseState} size="xs" type="button" variant="ghost">
                      Clear all
                    </Button>
                  </div>
                ) : null}

                  <div className="rounded-lg border bg-background/70 p-3">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Future workflows</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Button
                        onClick={() =>
                          onShowPlannedFeature(
                            "Saved searches are planned",
                            "Saved query presets will be added in a future phase without changing the current URL state contract.",
                          )
                        }
                        size="xs"
                        type="button"
                        variant="outline"
                      >
                        Saved searches
                      </Button>
                      <Button
                        onClick={() =>
                          onShowPlannedFeature(
                            "Saved selections are planned",
                            "Selection collections will be added in a future phase and reuse current selection scope behavior.",
                          )
                        }
                        size="xs"
                        type="button"
                        variant="outline"
                      >
                        Saved selections
                      </Button>
                    </div>
                  </div>
              </div>
            </div>
          </div>

          {selectedCount > 0 ? (
            <div className="space-y-3 rounded-xl border bg-muted/20 p-4">
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">Selected assets</p>
                <p className="text-sm text-muted-foreground">
                  Apply an existing tag or create a new one for the current selection.
                </p>
                <p className="text-xs text-muted-foreground">Selection scope: {selectionScope.replace(/-/g, " ")}</p>
              </div>
              <TagActionPanel
                applyButtonLabel="Apply tag"
                availableTags={availableTags}
                createButtonLabel="Create and apply"
                createInputLabel="Create a new tag"
                disabled={isUpdatingSelectionTags}
                emptyState="Create a tag first, then apply it to the selected assets."
                onApplyTag={onApplyExistingTagToSelection}
                onCreateTag={onCreateAndApplyTagToSelection}
                selectLabel="Apply an existing tag"
              />
            </div>
          ) : null}
        </CardHeader>

        <CardContent className="space-y-4">
          {assetsResponse.error ? (
            <Alert variant="destructive">
              <AlertTitle>Could not load assets</AlertTitle>
              <AlertDescription>{getErrorMessage(assetsResponse.error)}</AlertDescription>
            </Alert>
          ) : null}

          {isLoading ? <AssetsTableSkeleton /> : null}

          {!isLoading && !assetsResponse.error && visibleAssets.length > 0 ? (
            <AssetsTable
              assets={visibleAssets}
              inventoryHref={inventoryHref}
              onRunAssetAction={onRunAssetAction}
              onSelectAll={onSelectAll}
              onSelectAsset={onSelectAsset}
              onSort={onSort}
              outputCountsByAsset={outputCountsByAsset}
              pendingAssetIds={pendingAssetIds}
              selectedAssetIds={selectedAssetIds}
              sort={sort}
            />
          ) : null}

          {!isLoading && !assetsResponse.error && isInventoryEmpty ? (
            <InventoryEmptyState
              description="Use the add files button above to open the file explorer and populate the inventory."
              title="No assets registered yet"
            />
          ) : null}

          {showNoResults ? (
            <InventoryEmptyState
              action={
                <Button onClick={resetBrowseState} size="sm" type="button" variant="outline">
                  Clear filters
                </Button>
              }
              description="No assets matched the current search, filters, and local refinements. Clear one or more filters to broaden the result set."
              title="No matching assets"
            />
          ) : null}

          {!isLoading && !assetsResponse.error && visibleAssets.length > 0 ? (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Button asChild size="sm" variant="ghost">
                <Link href={buildAssetDetailHref(visibleAssets[0].id, inventoryHref)}>
                  Open latest result
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <ConversionDialog
        assets={selectedVisibleAssets}
        onOpenChange={setIsConversionDialogOpen}
        open={isConversionDialogOpen}
      />

      <Dialog onOpenChange={onDirectoryScanDialogChange} open={isDirectoryScanDialogOpen}>
        <DialogContent className="max-w-lg" showCloseButton={!isScanningDirectory}>
          <DialogHeader>
            <DialogTitle>Scan directory</DialogTitle>
            <DialogDescription>
              Register every supported `.bag` or `.mcap` file in a local directory without selecting them one by one.
            </DialogDescription>
          </DialogHeader>

          <form className="space-y-4" onSubmit={onScanDirectory}>
            {directoryScanMessage ? <FormNotice message={directoryScanMessage} /> : null}

            <div className="space-y-2">
              <Label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="directory-scan-path">
                Directory path
              </Label>
              <Input
                disabled={isScanningDirectory}
                id="directory-scan-path"
                onChange={(event) =>
                  setDirectoryScanForm((current) => ({
                    ...current,
                    directoryPath: event.target.value,
                  }))
                }
                placeholder="/path/to/recordings"
                value={directoryScanForm.directoryPath}
              />
            </div>

            <label className="flex items-start gap-3 rounded-lg border bg-muted/20 px-3 py-3">
              <Checkbox
                checked={directoryScanForm.recursive}
                disabled={isScanningDirectory}
                onCheckedChange={(checked) =>
                  setDirectoryScanForm((current) => ({
                    ...current,
                    recursive: checked === true,
                  }))
                }
              />
              <span className="space-y-1">
                <span className="block text-sm font-medium text-foreground">Scan recursively</span>
                <span className="block text-sm text-muted-foreground">
                  Include supported files from nested directories instead of only the top-level folder.
                </span>
              </span>
            </label>

            <DialogFooter>
              <Button
                disabled={isScanningDirectory}
                onClick={() => onDirectoryScanDialogChange(false)}
                type="button"
                variant="ghost"
              >
                Cancel
              </Button>
              <Button disabled={isScanningDirectory} type="submit">
                {isScanningDirectory ? <RefreshCw className="size-3.5 animate-spin" /> : null}
                {isScanningDirectory ? "Scanning..." : "Scan directory"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <input
        accept=".bag,.mcap"
        className="sr-only"
        multiple
        onChange={onUploadFiles}
        ref={uploadInputRef}
        type="file"
      />
    </div>
  );
}
