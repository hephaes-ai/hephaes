"use client";

import { getBackendBaseUrl } from "@/lib/api";
import { useHealth } from "@/hooks/use-backend";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export function BackendConnectionNotice() {
  const { error, isLoading } = useHealth();

  if (isLoading || !error) {
    return null;
  }

  return (
    <Alert className="mb-6" variant="destructive">
      <AlertTitle>Standalone backend unavailable</AlertTitle>
      <AlertDescription>
        The desktop frontend could not reach the FastAPI backend at{" "}
        <code className="rounded bg-background/80 px-1.5 py-0.5 text-xs">
          {getBackendBaseUrl()}
        </code>
        . Start the backend separately, or point the desktop app at a different
        base URL before relaunching.
      </AlertDescription>
    </Alert>
  );
}
