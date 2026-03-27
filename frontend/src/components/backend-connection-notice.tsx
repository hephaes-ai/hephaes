"use client"

import { getBackendBaseUrl } from "@/lib/api"
import { useHealth } from "@/hooks/use-backend"
import { useDesktopBackendRuntime } from "@/hooks/use-desktop-backend-runtime"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

export function BackendConnectionNotice() {
  const { error, isLoading } = useHealth()
  const runtime = useDesktopBackendRuntime()
  const isBundledBackend = runtime?.mode === "sidecar"
  const bundledBackendStopped = isBundledBackend && runtime.status === "stopped"

  if (!bundledBackendStopped && (isLoading || !error)) {
    return null
  }

  const title = bundledBackendStopped
    ? "Bundled backend stopped"
    : isBundledBackend
      ? "Bundled backend unavailable"
      : "Configured backend unavailable"
  const details = [
    bundledBackendStopped
      ? "The bundled backend stopped after startup."
      : "The desktop frontend could not reach the FastAPI backend.",
    `Target URL: ${getBackendBaseUrl()}.`,
    isBundledBackend
      ? "The app may still be starting its local backend, or the sidecar may have stopped unexpectedly."
      : "Check the configured backend URL and make sure the external service is running.",
    runtime?.error?.trim() ? `Error: ${runtime.error.trim()}` : null,
    runtime?.backendLogDir ? `Backend logs: ${runtime.backendLogDir}.` : null,
    runtime?.desktopLogDir ? `Desktop logs: ${runtime.desktopLogDir}.` : null,
  ]
    .filter(Boolean)
    .join(" ")

  return (
    <Alert className="mb-6" variant="destructive">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{details}</AlertDescription>
    </Alert>
  )
}
