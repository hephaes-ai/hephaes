"use client";

import * as React from "react";
import {
  ArrowRight,
  ArrowRightLeft,
  ChevronDown,
  FolderOpen,
  RefreshCw,
  Search,
  Tag,
  X,
} from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { InlineNotice } from "@/components/inline-notice";
import { InventoryScanDialog } from "./inventory-scan-dialog";
import { AssetsTable, AssetsTableSkeleton, DEFAULT_SORT, parseSort } from "./inventory-table";
import type { InventorySort, SortColumn } from "./inventory-table";
import { InventoryUploadButton } from "./inventory-upload-dialog";
import { TagActionPanel } from "@/components/tag-controls";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/sonner";
import { useAssets, useBackendCache, useOutputs, useTags } from "@/hooks/use-backend";
import { useIndexAsset } from "@/hooks/use-index-asset";
import type { AssetListQuery, AssetSummary, IndexingStatus, TagSummary } from "@/lib/api";
import { attachTagToAsset, createTag, getErrorMessage } from "@/lib/api";
import {
  AppLink as Link,
  useAppPathname as usePathname,
  useAppRouter as useRouter,
  useAppSearchParams as useSearchParams,
} from "@/lib/app-routing";
import { buildAssetDetailHref, buildConversionHref } from "@/lib/navigation";
import { countOutputsByAsset } from "@/lib/outputs";
import type { ActiveFilterChip, NoticeMessage } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_OPTIONS: IndexingStatus[] = ["pending", "indexing", "indexed", "failed"];

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

function assetHasTag(asset: AssetSummary, tagId: string) {
  return (asset.tags ?? []).some((tag) => tag.id === tagId);
}

function findExistingTagByName(tags: TagSummary[], name: string) {
  const normalizedName = name.trim().toLowerCase();
  return tags.find((tag) => tag.name.trim().toLowerCase() === normalizedName);
}

export function InventoryPageFallback() {
  return (
    <div className="space-y-6">
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
  const { revalidateAssetLists, revalidateTags } = useBackendCache();
  const { pendingAssetIds, runBulkIndex, runIndexAsset, runIndexPending } = useIndexAsset();

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

  const [formMessage, setNoticeMessage] = React.useState<NoticeMessage | null>(null);
  const [isDirectoryScanDialogOpen, setIsDirectoryScanDialogOpen] = React.useState(false);
  const [searchInput, setSearchInput] = React.useState(appliedSearch);
  const [isBrowsePanelOpen, setIsBrowsePanelOpen] = React.useState(false);
  const [isTagDialogOpen, setIsTagDialogOpen] = React.useState(false);
  const [isBulkIndexingSelection, setIsBulkIndexingSelection] = React.useState(false);
  const [isIndexingPendingAssets, setIsIndexingPendingAssets] = React.useState(false);
  const [isUpdatingSelectionTags, setIsUpdatingSelectionTags] = React.useState(false);
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
    setNoticeMessage({
      description,
      title,
      tone: "info",
    });
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
  const isSelectionFullyIndexed =
    selectedVisibleAssets.length > 0 &&
    selectedVisibleAssets.every(
      (asset) => asset.indexing_status === "indexed" && !pendingAssetIds.has(asset.id),
    );
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
  const convertHref = buildConversionHref({
    assetIds: selectedVisibleAssets.map((asset) => asset.id),
    from: inventoryHref,
  });

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

  async function onRunAssetAction(asset: AssetSummary) {
    setNoticeMessage(null);
    const notice = await runIndexAsset(asset);
    if (notice) {
      setNoticeMessage(notice);
      toast.error("Could not index asset", { description: notice.description });
    }
  }

  async function onRunBulkIndex() {
    setNoticeMessage(null);
    setIsBulkIndexingSelection(true);

    try {
      const notice = await runBulkIndex(actionableSelectedAssets);
      if (notice) {
        setNoticeMessage(notice);
        toast[notice.tone](notice.title, { description: notice.description });
      }
    } finally {
      setIsBulkIndexingSelection(false);
    }
  }

  async function onIndexPendingAssets() {
    setNoticeMessage(null);
    setIsIndexingPendingAssets(true);

    try {
      const notice = await runIndexPending();
      if (notice) {
        if (notice.tone === "info" && notice.title === "Nothing to index") {
          toast.info(notice.title, { description: notice.description });
        } else if (notice.tone === "error") {
          setNoticeMessage(notice);
          toast.error(notice.title, { description: notice.description });
        } else {
          setNoticeMessage(notice);
          toast.info(notice.title, { description: notice.description });
        }
      }
    } finally {
      setIsIndexingPendingAssets(false);
    }
  }

  async function refreshTagAwareData() {
    await Promise.all([revalidateAssetLists(), revalidateTags()]);
  }

  async function applyTagToSelectedAssets(tag: TagSummary) {
    const assetsNeedingTag = selectedVisibleAssets.filter((asset) => !assetHasTag(asset, tag.id));

    if (assetsNeedingTag.length === 0) {
      setNoticeMessage({
        description: `All selected assets already have the ${tag.name} tag.`,
        title: "Selection already tagged",
        tone: "info",
      });
      return;
    }

    setNoticeMessage(null);
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
        setNoticeMessage({
          description,
          title: "Tags applied with warnings",
          tone: "info",
        });
        toast.info("Bulk tag update finished", { description });
        return;
      }

      const description = failureMessages[0] ?? `No selected assets could be tagged with ${tag.name}.`;
      setNoticeMessage({
        description,
        title: "Could not apply tag",
        tone: "error",
      });
      toast.error("Bulk tag update failed", { description });
    } finally {
      setIsUpdatingSelectionTags(false);
    }
  }

  async function onApplyExistingTagToSelection(tagId: string) {
    const selectedTag = availableTags.find((tag) => tag.id === tagId);
    if (!selectedTag) {
      setNoticeMessage({
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

    setNoticeMessage(null);
    setIsUpdatingSelectionTags(true);

    try {
      const createdTag = await createTag({ name });
      await revalidateTags();
      await applyTagToSelectedAssets(createdTag);
    } catch (tagError) {
      const message = getErrorMessage(tagError);
      setNoticeMessage({
        description: message,
        title: "Could not create tag",
        tone: "error",
      });
      toast.error("Tag creation failed", { description: message });
      await revalidateTags();
    } finally {
      setIsUpdatingSelectionTags(false);
    }
  }

  return (
    <div className="space-y-6">
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
              Search, filter, sort through assets.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <InventoryUploadButton
              onUploadComplete={(notice) => {
                setNoticeMessage(notice);
              }}
            />
            <Button
              className="shrink-0"
              onClick={() => setIsDirectoryScanDialogOpen(true)}
              size="sm"
              type="button"
              variant="outline"
            >
              <FolderOpen className="size-4" />
              Scan directory
            </Button>
            <Button
              className="shrink-0"
              onClick={() => {
                void assetsResponse.mutate();
                if (hasServerFilters) {
                  void allAssetsResponse.mutate();
                }
                void revalidateTags();
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
      </section>

      {formMessage ? <InlineNotice description={formMessage.description} title={formMessage.title} tone={formMessage.tone} /> : null}

      <Card className="flex-1 overflow-visible">
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
                isSelectionFullyIndexed ? (
                  <Button asChild size="sm" variant="outline">
                    <Link href={convertHref}>
                      <ArrowRightLeft className="size-3.5" />
                      Convert
                    </Link>
                  </Button>
                ) : (
                  <Button
                    disabled
                    size="sm"
                    title="All selected assets must be indexed before conversion."
                    type="button"
                    variant="outline"
                  >
                    <ArrowRightLeft className="size-3.5" />
                    Convert
                  </Button>
                )
              ) : null}
              {selectedCount > 0 ? (
                <Button onClick={() => setIsTagDialogOpen(true)} size="sm" type="button" variant="outline">
                  <Tag className="size-3.5" />
                  Tag
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
            </div>
          </div>

          <div
            className={cn(
              "grid transition-all duration-200 ease-out",
              isBrowsePanelOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0 pointer-events-none",
            )}
          >
            <div className="min-h-0 overflow-hidden">
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
            <EmptyState
              description="Use the add files button above to open the file explorer and populate the inventory."
              title="No assets registered yet"
            />
          ) : null}

          {showNoResults ? (
            <EmptyState
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

      <Dialog onOpenChange={setIsTagDialogOpen} open={isTagDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Tag selected assets</DialogTitle>
            <DialogDescription>
              Apply an existing tag or create a new one for the {selectedCount} selected asset{selectedCount !== 1 ? "s" : ""}.
            </DialogDescription>
          </DialogHeader>
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
        </DialogContent>
      </Dialog>

      <InventoryScanDialog
        onScanComplete={(notice) => {
          setNoticeMessage(notice);
        }}
        onOpenChange={setIsDirectoryScanDialogOpen}
        open={isDirectoryScanDialogOpen}
      />
    </div>
  );
}
