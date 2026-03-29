"use client";

import * as React from "react";
import { ExternalLink, MoreHorizontal } from "lucide-react";

import {
  OutputContentButton,
  OutputRoleBadge,
  OutputSourceLinks,
} from "@/components/output-detail-content";
import { OutputAvailabilityBadge } from "@/components/output-availability-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { formatDateTime, formatFileSize, formatOutputFormat } from "@/lib/format";

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
  assetsById,
  currentHref,
  onSelectOutput,
  outputs,
}: {
  assetsById: Map<string, AssetSummary>;
  currentHref: string;
  onSelectOutput: (outputId: string) => void;
  outputs: OutputDetail[];
}) {
  return (
    <div className="hidden overflow-x-auto md:block">
      <Table className="min-w-[920px]">
        <TableHeader>
          <TableRow>
            <TableHead>Output file</TableHead>
            <TableHead>Source assets</TableHead>
            <TableHead>Size</TableHead>
            <TableHead>Availability</TableHead>
            <TableHead>Updated</TableHead>
            <TableHead className="w-12 text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {outputs.map((output) => {
            const imagePayloadContract = getImagePayloadContract(output);

            return (
              <TableRow key={output.id} onClick={() => onSelectOutput(output.id)}>
                <TableCell>
                  <div className="space-y-2">
                    <p className="whitespace-nowrap font-medium text-foreground">{output.file_name}</p>
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
                <TableCell className="text-muted-foreground">
                  {formatDateTime(output.updated_at)}
                </TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        className="size-8"
                        onClick={(event) => event.stopPropagation()}
                        size="icon"
                        variant="ghost"
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
  onSelectOutput,
  outputs,
}: {
  assetsById: Map<string, AssetSummary>;
  currentHref: string;
  onSelectOutput: (outputId: string) => void;
  outputs: OutputDetail[];
}) {
  return (
    <div className="space-y-3 md:hidden">
      {outputs.map((output) => {
        const imagePayloadContract = getImagePayloadContract(output);

        return (
          <div className="space-y-3 rounded-xl border bg-muted/15 px-4 py-4" key={output.id}>
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

            <div className="flex flex-wrap items-center gap-2">
              <OutputAvailabilityBadge availability={output.availability_status} />
            </div>

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
            </div>
          </div>
        );
      })}
    </div>
  );
}
