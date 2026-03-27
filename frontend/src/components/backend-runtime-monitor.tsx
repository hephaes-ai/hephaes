"use client"

import * as React from "react"

import { useFeedback } from "@/components/feedback-provider"
import { useDesktopBackendRuntime } from "@/hooks/use-desktop-backend-runtime"

export function BackendRuntimeMonitor() {
  const { notify } = useFeedback()
  const runtime = useDesktopBackendRuntime()
  const previousStatus = React.useRef(runtime?.status)

  React.useEffect(() => {
    if (runtime?.mode !== "sidecar") {
      previousStatus.current = runtime?.status
      return
    }

    const lastStatus = previousStatus.current
    previousStatus.current = runtime.status

    if (lastStatus !== "ready" || runtime.status === "ready") {
      return
    }

    const title =
      runtime.status === "stopped"
        ? "Bundled backend stopped"
        : "Bundled backend unavailable"
    const description = [
      runtime.error?.trim() || null,
      runtime.backendLogDir ? `Backend logs: ${runtime.backendLogDir}` : null,
    ]
      .filter(Boolean)
      .join(" ")

    notify({
      description,
      title,
      tone: "error",
    })
  }, [notify, runtime])

  return null
}
