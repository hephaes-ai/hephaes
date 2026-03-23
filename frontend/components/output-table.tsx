"use client";

import * as React from "react";
import { ExternalLink, MoreHorizontal } from "lucide-react";

import {
  formatOutputActionSummary,
  OutputContentButton,
  OutputRoleBadge,
  OutputSourceLinks,
} from "@/components/output-detail-content";
import { OutputAvailabilityBadge } from "@/components/output-availability-badge";
import { WorkflowStatusBadge } from "@/components/workflow-status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { AssetSummary, OutputDetail } from "@/lib/api";
import { resolveBackendUrl } from "@/lib/api";
import {
  formatDateTime,
  formatFileSize,
  formatOutputActionType,
  formatOutputFormat,
} from "@/lib/format";

function getImagePayloadContract(output: OutputDetail) {
  const manifest = output.metadata?.manifest;
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    return null;
  }

  const payloadRepresentation = (manifest as Record<string, unknown>).payload_representation;
  if (
    !payloadRepresentation ||
    typeof payloadRepresentation !== "object" ||
    Array.isArray(payloadRepresentation)
  ) {
    return null;
  }

  const contract = (payloadRepresentation as Record<string, unknown>).image_payload_contract;
  return typeof contract === "string" && contract.trim().length > 0
    ? contract.trim()
    : null;
}

export function OutputsTable({
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
            const imagePayloadContract = getImagePayloadContract(output);

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
                      {imagePayloadContract ? (
                        <Badge variant="secondary">{imagePayloadContract}</Badge>
                      ) : null}
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

export function OutputsCards({
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
        const imagePayloadContract = getImagePayloadContract(output);

        return (
          <div className="space-y-3 rounded-xl border bg-muted/15 px-4 py-4" key={output.id}>
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-2">
                <p className="font-medium text-foreground">{output.file_name}</p>
                <p className="break-all text-xs text-muted-foreground">{output.relative_path}</p>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{formatOutputFormat(output.format)}</Badge>
                  <OutputRoleBadge role={output.role} />
                  {imagePayloadContract ? (
                    <Badge variant="secondary">{imagePayloadContract}</Badge>
                  ) : null}
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
