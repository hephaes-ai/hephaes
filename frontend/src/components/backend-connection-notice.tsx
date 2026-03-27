"use client";

import { getBackendBaseUrl } from "@/lib/api";
import { getDesktopBackendRuntime } from "@/lib/backend-runtime";
import { useHealth } from "@/hooks/use-backend";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export function BackendConnectionNotice() {
  const { error, isLoading } = useHealth();
  const runtime = getDesktopBackendRuntime();

  if (isLoading || !error) {
    return null;
  }

  const isBundledBackend = runtime?.mode === "sidecar";
  const title = isBundledBackend
    ? "Bundled backend unavailable"
    : "Configured backend unavailable";

  return (
    <Alert className="mb-6" variant="destructive">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>
        The desktop frontend could not reach the FastAPI backend at{" "}
        <code className="rounded bg-background/80 px-1.5 py-0.5 text-xs">
          {getBackendBaseUrl()}
        </code>
        . {isBundledBackend
          ? "The app may still be starting its local backend, or the sidecar may have stopped unexpectedly."
          : "Check the configured backend URL and make sure the external service is running."}
      </AlertDescription>
    </Alert>
  );
}
