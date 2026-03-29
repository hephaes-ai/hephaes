"use client";

import * as React from "react";
import {
  ArrowUpDown,
  ChevronDown,
  ChevronUp,
  MoreHorizontal,
  RefreshCw,
} from "lucide-react";

import { AssetStatusBadge } from "@/components/asset-status-badge";
import { TagBadgeList } from "@/components/tag-controls";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { AssetSummary, IndexingStatus } from "@/lib/api";
import {
  AppLink as Link,
  useAppRouter as useRouter,
} from "@/lib/app-routing";
import { formatDateTime, formatFileSize, getIndexActionLabel } from "@/lib/format";
import { buildAssetDetailHref } from "@/lib/navigation";
import { buildOutputsHref } from "@/lib/outputs";
import { cn } from "@/lib/utils";

export type InventorySort =
  | "file_name-asc"
  | "file_name-desc"
  | "file_size-asc"
  | "file_size-desc"
  | "registered-desc"
  | "registered-asc";

export type SortColumn = "file_name" | "file_size" | "registered";
export type SortDirection = "asc" | "desc";

export const DEFAULT_SORT: InventorySort = "registered-desc";

export function isValidSort(value: string | null): value is InventorySort {
  return (
    value === "file_name-asc" ||
    value === "file_name-desc" ||
    value === "file_size-asc" ||
    value === "file_size-desc" ||
    value === "registered-desc" ||
    value === "registered-asc"
  );
}

export function parseSort(value: string | null) {
  const normalizedValue = isValidSort(value) ? value : DEFAULT_SORT;
  const [column, direction] = normalizedValue.split("-") as [SortColumn, SortDirection];

  return {
    column,
    direction,
    value: normalizedValue,
  };
}

function getAssetTags(asset: AssetSummary) {
  return asset.tags ?? [];
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

export function AssetsTableSkeleton() {
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

export function AssetsTable({
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
    <div className="[&_[data-slot=table-container]]:overflow-x-auto">
      <Table className="w-auto min-w-[860px]">
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
            <TableHead className="w-12 text-right">Action</TableHead>
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
                    <div className="truncate font-medium text-foreground" title={asset.file_name}>
                      {asset.file_name}
                    </div>
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
                  <div data-stop-row-click="true">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button size="icon" variant="ghost" className="size-8">
                          <MoreHorizontal className="size-4" />
                          <span className="sr-only">Actions</span>
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          disabled={isRunningAction || asset.indexing_status === "indexing"}
                          onClick={() => onRunAssetAction(asset)}
                        >
                          {isRunningAction ? <RefreshCw className="size-4 animate-spin" /> : null}
                          {getIndexActionLabel(asset.indexing_status, isRunningAction)}
                        </DropdownMenuItem>
                        {outputCount > 0 ? (
                          <DropdownMenuItem asChild>
                            <Link href={buildOutputsHref({ assetId: asset.id })}>Outputs</Link>
                          </DropdownMenuItem>
                        ) : null}
                      </DropdownMenuContent>
                    </DropdownMenu>
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
