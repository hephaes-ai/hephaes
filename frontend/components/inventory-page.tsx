"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  ArrowUpDown,
  ChevronDown,
  ChevronUp,
  FileSearch2,
  FolderOpen,
  RefreshCw,
  Search,
  X,
} from "lucide-react";

import { AssetStatusBadge } from "@/components/asset-status-badge";
import { useFeedback } from "@/components/feedback-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAssets } from "@/hooks/use-backend";
import type { AssetListQuery, AssetRegistrationSkip, AssetSummary, IndexingStatus } from "@/lib/api";
import { getErrorMessage, registerAssetsFromDialog } from "@/lib/api";
import { formatDateTime, formatFileSize } from "@/lib/format";
import { cn } from "@/lib/utils";

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

function summarizeSkipped(skipped: AssetRegistrationSkip[]) {
  if (skipped.length === 0) {
    return "";
  }

  const [firstSkip] = skipped;
  if (skipped.length === 1) {
    return firstSkip.detail;
  }

  return `${firstSkip.detail} ${skipped.length - 1} more file${skipped.length - 1 === 1 ? "" : "s"} were skipped.`;
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

function AssetsTable({
  assets,
  inventoryHref,
  onSelectAll,
  onSelectAsset,
  onSort,
  selectedAssetIds,
  sort,
}: {
  assets: AssetSummary[];
  inventoryHref: string;
  onSelectAll: (checked: boolean | "indeterminate") => void;
  onSelectAsset: (assetId: string, checked: boolean | "indeterminate") => void;
  onSort: (column: SortColumn) => void;
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
          </TableRow>
        </TableHeader>
        <TableBody>
          {assets.map((asset) => {
            const isSelected = selectedAssetIds.has(asset.id);

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
                  </div>
                </TableCell>
                <TableCell className="uppercase text-muted-foreground">{asset.file_type}</TableCell>
                <TableCell>{formatFileSize(asset.file_size)}</TableCell>
                <TableCell>
                  <AssetStatusBadge status={asset.indexing_status} />
                </TableCell>
                <TableCell>{formatDateTime(asset.registered_time)}</TableCell>
                <TableCell>{formatDateTime(asset.last_indexed_time, "Not indexed yet")}</TableCell>
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

  const appliedSearch = searchParams.get("search")?.trim() ?? "";
  const activeType = searchParams.get("type")?.trim() ?? "";
  const activeStatus = searchParams.get("status")?.trim() ?? "";
  const minDuration = searchParams.get("min_duration")?.trim() ?? "";
  const maxDuration = searchParams.get("max_duration")?.trim() ?? "";
  const sizeMinMb = searchParams.get("size_min_mb")?.trim() ?? "";
  const sizeMaxMb = searchParams.get("size_max_mb")?.trim() ?? "";
  const registeredAfter = searchParams.get("registered_after")?.trim() ?? "";
  const registeredBefore = searchParams.get("registered_before")?.trim() ?? "";
  const sort = parseSort(searchParams.get("sort"));

  const [formMessage, setFormMessage] = React.useState<FormMessage | null>(null);
  const [isChoosingFiles, setIsChoosingFiles] = React.useState(false);
  const [searchInput, setSearchInput] = React.useState(appliedSearch);
  const [isBrowsePanelOpen, setIsBrowsePanelOpen] = React.useState(() => searchParams.toString().length > 0);
  const [selectedAssetIds, setSelectedAssetIds] = React.useState<Set<string>>(new Set());

  React.useEffect(() => {
    setSearchInput(appliedSearch);
  }, [appliedSearch]);

  const normalizedMinDuration = parseNonNegativeNumber(minDuration) ?? undefined;
  const normalizedMaxDuration = parseNonNegativeNumber(maxDuration) ?? undefined;
  const normalizedStatus = isValidIndexingStatus(activeStatus) ? activeStatus : undefined;

  const serverQueryCandidate: AssetListQuery = {
    max_duration: normalizedMaxDuration,
    min_duration: normalizedMinDuration,
    search: appliedSearch || undefined,
    status: normalizedStatus,
    type: activeType || undefined,
  };
  const serverQuery = Object.values(serverQueryCandidate).some((value) => value !== undefined)
    ? serverQueryCandidate
    : undefined;
  const hasServerFilters = Boolean(serverQuery);

  const assetsResponse = useAssets(serverQuery);
  const allAssetsResponse = useAssets(hasServerFilters ? undefined : null);

  const assets = assetsResponse.data ?? [];
  const allAssets = hasServerFilters ? (allAssetsResponse.data ?? assets) : assets;
  const totalRegisteredCount = hasServerFilters ? allAssetsResponse.data?.length : assets.length;

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

  async function onChooseFiles() {
    setIsChoosingFiles(true);
    setFormMessage(null);

    try {
      const result = await registerAssetsFromDialog();

      if (result.canceled) {
        setFormMessage({
          description: "The file picker was closed without selecting any files.",
          title: "No files selected",
          tone: "info",
        });
        return;
      }

      if (result.registered_assets.length > 0) {
        await assetsResponse.mutate();

        if (hasServerFilters) {
          await allAssetsResponse.mutate();
        }
      }

      const registeredCount = result.registered_assets.length;
      const skippedCount = result.skipped.length;
      const descriptionParts: string[] = [];

      if (registeredCount > 0) {
        descriptionParts.push(
          `${registeredCount} file${registeredCount === 1 ? "" : "s"} added to inventory.`,
        );
      }

      if (skippedCount > 0) {
        descriptionParts.push(summarizeSkipped(result.skipped));
      }

      if (registeredCount > 0) {
        const tone = skippedCount > 0 ? "info" : "success";
        setFormMessage({
          description: descriptionParts.join(" "),
          title: skippedCount > 0 ? "Files added with warnings" : "Files added",
          tone,
        });
        notify({
          description: descriptionParts.join(" "),
          title: skippedCount > 0 ? "Inventory updated" : "Files added",
          tone,
        });
        return;
      }

      setFormMessage({
        description: descriptionParts.join(" ") || "No new files were added.",
        title: "No files added",
        tone: "error",
      });
      notify({
        description: descriptionParts.join(" ") || "No new files were added.",
        title: "Nothing changed",
        tone: "error",
      });
    } catch (submitError) {
      const message = getErrorMessage(submitError);

      setFormMessage({
        description: message,
        title: "File picker failed",
        tone: "error",
      });
      notify({
        description: message,
        title: "Could not open file picker",
        tone: "error",
      });
    } finally {
      setIsChoosingFiles(false);
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
  const resultsCountLabel = `${visibleAssets.length} result${visibleAssets.length === 1 ? "" : "s"}`;
  const totalCountLabel =
    typeof totalRegisteredCount === "number" ? `${totalRegisteredCount} registered` : "Loading total";
  const inventoryHref = searchParams.toString() ? `${pathname}?${searchParams.toString()}` : pathname;

  const isLoading = assetsResponse.isLoading;
  const isInventoryEmpty = !hasAppliedFilters && totalRegisteredCount === 0;
  const showNoResults = !isLoading && !assetsResponse.error && !isInventoryEmpty && visibleAssets.length === 0;

  return (
    <div className="space-y-8">
      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight">Asset inventory</h1>
              <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                {totalCountLabel}
              </span>
            </div>
            <p className="max-w-3xl text-sm text-muted-foreground">
              Browse the live backend inventory with compact search, filters, and table sorting while keeping the
              registered assets table as the main surface.
            </p>
          </div>
          <Button
            className="shrink-0"
            onClick={onChooseFiles}
            size="sm"
            type="button"
            variant="outline"
          >
            <FileSearch2 className="size-4" />
            {isChoosingFiles ? "Opening..." : "Add files"}
          </Button>
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
            <div className="flex items-center gap-2">
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
                onClick={() => {
                  void assetsResponse.mutate();
                  if (hasServerFilters) {
                    void allAssetsResponse.mutate();
                  }
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

                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
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
              </div>
            </div>
          </div>
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
              onSelectAll={onSelectAll}
              onSelectAsset={onSelectAsset}
              onSort={onSort}
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
    </div>
  );
}
