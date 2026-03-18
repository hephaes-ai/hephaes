"use client";

import * as React from "react";

import { resolveBackendUrl, type ViewerSourceKind } from "@/lib/api";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

function buildRerunEmbedUrl(sourceUrl: string) {
  const viewerHost = process.env.NEXT_PUBLIC_RERUN_VIEWER_HOST?.trim() || "https://app.rerun.io";
  const sourceUrlObject = new URL(resolveBackendUrl(sourceUrl));
  sourceUrlObject.searchParams.set("_ts", String(Date.now()));

  const viewerUrl = new URL(viewerHost);
  viewerUrl.searchParams.append("url", sourceUrlObject.toString());
  viewerUrl.searchParams.set("persist", "0");
  viewerUrl.searchParams.set("hide_welcome_screen", "1");
  return viewerUrl.toString();
}

export function RerunViewer({
  sourceKind,
  sourceUrl,
}: {
  sourceKind: ViewerSourceKind | null;
  sourceUrl: string;
}) {
  const embedUrl = React.useMemo(() => buildRerunEmbedUrl(sourceUrl), [sourceUrl]);
  const sourceLabel = sourceKind === "grpc_url" ? "gRPC stream" : "RRD recording";

  return (
    <div className="space-y-3">
      <Alert>
        <AlertTitle>Official Rerun viewer</AlertTitle>
        <AlertDescription>
          Embedded using {sourceLabel}. If the embed is blocked, open it in a new tab.
        </AlertDescription>
      </Alert>

      <div className="overflow-hidden rounded-lg border bg-black/5">
        <iframe
          allow="fullscreen"
          className="h-[460px] w-full"
          loading="lazy"
          src={embedUrl}
          title="Rerun Viewer"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <Button asChild size="sm" type="button" variant="outline">
          <a href={embedUrl} rel="noreferrer" target="_blank">
            Open viewer in new tab
          </a>
        </Button>
        <Button asChild size="sm" type="button" variant="ghost">
          <a href={resolveBackendUrl(sourceUrl)} rel="noreferrer" target="_blank">
            Open source URL
          </a>
        </Button>
      </div>
    </div>
  );
}
