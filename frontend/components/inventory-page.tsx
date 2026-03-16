"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, FileSearch2, FolderOpen, RefreshCw } from "lucide-react";

import { AssetStatusBadge } from "@/components/asset-status-badge";
import { useFeedback } from "@/components/feedback-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import type { AssetRegistrationSkip, AssetSummary } from "@/lib/api";
import { getErrorMessage, registerAssetsFromDialog } from "@/lib/api";
import { formatDateTime, formatFileSize } from "@/lib/format";
import { useAssets } from "@/hooks/use-backend";

interface FormMessage {
  description?: string;
  title: string;
  tone: "error" | "info" | "success";
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

function AssetsTable({ assets }: { assets: AssetSummary[] }) {
  const router = useRouter();

  function openAsset(assetId: string) {
    router.push(`/assets/${assetId}`);
  }

  function onRowKeyDown(event: React.KeyboardEvent<HTMLTableRowElement>, assetId: string) {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }

    event.preventDefault();
    openAsset(assetId);
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>File name</TableHead>
          <TableHead>File type</TableHead>
          <TableHead>File size</TableHead>
          <TableHead>Indexing status</TableHead>
          <TableHead>Registration date</TableHead>
          <TableHead>Last indexed</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {assets.map((asset) => (
          <TableRow
            key={asset.id}
            aria-label={`Open ${asset.file_name}`}
            className="cursor-pointer"
            onClick={() => openAsset(asset.id)}
            onKeyDown={(event) => onRowKeyDown(event, asset.id)}
            role="link"
            tabIndex={0}
          >
            <TableCell className="max-w-0 min-w-56">
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
        ))}
      </TableBody>
    </Table>
  );
}

function AssetsTableSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className="grid gap-3 rounded-lg border px-4 py-3 md:grid-cols-6">
          <Skeleton className="h-10 md:col-span-2" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      ))}
    </div>
  );
}

export function InventoryPage() {
  const { notify } = useFeedback();
  const { data: assets, error, isLoading, mutate } = useAssets();
  const [formMessage, setFormMessage] = React.useState<FormMessage | null>(null);
  const [isChoosingFiles, setIsChoosingFiles] = React.useState(false);

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
        await mutate(
          (currentAssets) => {
            const mergedAssets = [...result.registered_assets, ...(currentAssets ?? [])];
            const uniqueAssets = new Map(mergedAssets.map((asset) => [asset.id, asset]));
            return Array.from(uniqueAssets.values());
          },
          { revalidate: false },
        );

        React.startTransition(() => {
          void mutate();
        });
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

  return (
    <div className="space-y-8">
      <section className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">Asset inventory</h1>
          <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
            {assets?.length ?? 0} registered
          </span>
        </div>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Connect the frontend to the live backend by registering a local ROS bag file path, reviewing the
          inventory, and opening backend-driven detail pages.
        </p>
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileSearch2 className="size-4" />
              Add files to inventory
            </CardTitle>
            <CardDescription>
              Use the native file explorer to choose one or more <code>.bag</code> or <code>.mcap</code> files.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="choose-files">Open file explorer</Label>
              <Button
                className="w-full"
                id="choose-files"
                onClick={onChooseFiles}
                type="button"
              >
                {isChoosingFiles ? "Opening file explorer..." : "Choose files"}
              </Button>
            </div>

            <p className="text-xs leading-5 text-muted-foreground">
              The backend opens a native file picker locally, then registers the selected files in the asset
              registry.
            </p>

            {formMessage ? (
              <div className="mt-4">
                <FormNotice message={formMessage} />
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <FolderOpen className="size-4" />
                Registered assets
              </CardTitle>
              <CardDescription>
                The list below is loaded directly from <code>GET /assets</code>.
              </CardDescription>
            </div>
            <Button
              className="shrink-0"
              onClick={() => {
                void mutate();
              }}
              size="sm"
              type="button"
              variant="outline"
            >
              <RefreshCw className="size-4" />
              Refresh
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Could not load assets</AlertTitle>
                <AlertDescription>{getErrorMessage(error)}</AlertDescription>
              </Alert>
            ) : null}

            {isLoading ? <AssetsTableSkeleton /> : null}

            {!isLoading && !error && assets && assets.length > 0 ? <AssetsTable assets={assets} /> : null}

            {!isLoading && !error && assets?.length === 0 ? (
              <div className="rounded-xl border border-dashed px-6 py-12 text-center">
                <h2 className="text-sm font-medium text-foreground">No assets registered yet</h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Register a local file path to populate the inventory and verify the backend end-to-end.
                </p>
              </div>
            ) : null}

            {!isLoading && !error && assets && assets.length > 0 ? (
              <div className="flex items-center justify-end">
                <Button asChild size="sm" variant="ghost">
                  <Link href={assets.length > 0 ? `/assets/${assets[0].id}` : "/"}>
                    Open latest asset
                    <ArrowRight className="size-4" />
                  </Link>
                </Button>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
