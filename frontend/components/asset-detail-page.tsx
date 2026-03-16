"use client";

import Link from "next/link";
import { ArrowLeft, Database, FileText, Tags } from "lucide-react";

import { AssetStatusBadge } from "@/components/asset-status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getErrorMessage, BackendApiError } from "@/lib/api";
import { formatDateTime, formatFileSize } from "@/lib/format";
import { useAsset } from "@/hooks/use-backend";

function AssetDetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-32" />
      <Skeleton className="h-28 rounded-xl" />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Skeleton className="h-72 rounded-xl" />
        <Skeleton className="h-72 rounded-xl" />
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Skeleton className="h-40 rounded-xl" />
        <Skeleton className="h-40 rounded-xl" />
        <Skeleton className="h-40 rounded-xl" />
      </div>
    </div>
  );
}

function PlaceholderCard({
  description,
  icon,
  title,
}: {
  description: string;
  icon: React.ReactNode;
  title: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {icon}
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="rounded-lg border border-dashed px-4 py-6 text-sm text-muted-foreground">
          This section is intentionally reserved for a later phase.
        </div>
      </CardContent>
    </Card>
  );
}

export function AssetDetailPage({ assetId }: { assetId: string }) {
  const { data, error, isLoading, mutate } = useAsset(assetId);

  if (isLoading) {
    return <AssetDetailSkeleton />;
  }

  if (error) {
    const isMissingAsset = error instanceof BackendApiError && error.status === 404;

    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href="/">
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

  const { asset } = data;

  return (
    <div className="space-y-6">
      <Button asChild size="sm" variant="ghost">
        <Link href="/">
          <ArrowLeft className="size-4" />
          Back to inventory
        </Link>
      </Button>

      <Card>
        <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle className="text-xl">{asset.file_name}</CardTitle>
            <CardDescription className="mt-1 break-all">{asset.file_path}</CardDescription>
          </div>
          <AssetStatusBadge status={asset.indexing_status} />
        </CardHeader>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Asset details</CardTitle>
            <CardDescription>
              This page reflects the current response from <code>GET /assets/{asset.id}</code>.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">File type</dt>
                <dd className="text-sm font-medium uppercase text-foreground">{asset.file_type}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">File size</dt>
                <dd className="text-sm font-medium text-foreground">{formatFileSize(asset.file_size)}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Registered</dt>
                <dd className="text-sm font-medium text-foreground">{formatDateTime(asset.registered_time)}</dd>
              </div>
              <div className="space-y-1">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Last indexed</dt>
                <dd className="text-sm font-medium text-foreground">
                  {formatDateTime(asset.last_indexed_time, "Not indexed yet")}
                </dd>
              </div>
              <div className="space-y-1 sm:col-span-2">
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Asset ID</dt>
                <dd className="break-all text-sm font-medium text-foreground">{asset.id}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Phase 1 summary</CardTitle>
            <CardDescription>
              The detail route is intentionally lean in this phase and focuses on validating backend shape.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>The asset is being displayed directly from the backend registry without any frontend-only mock data.</p>
            <p>Later phases will expand this view with metadata, tags, conversions, jobs, and visualization tools.</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <PlaceholderCard
          description="Reserved for extracted metadata once indexing persistence is available."
          icon={<Database className="size-4" />}
          title="Metadata"
        />
        <PlaceholderCard
          description="Reserved for asset tags and tag-management actions."
          icon={<Tags className="size-4" />}
          title="Tags"
        />
        <PlaceholderCard
          description="Reserved for conversion history and output tracking."
          icon={<FileText className="size-4" />}
          title="Conversions"
        />
      </div>
    </div>
  );
}
