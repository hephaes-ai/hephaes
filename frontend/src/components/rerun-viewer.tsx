"use client"

import * as React from "react"
import { WebViewer as RerunWebViewer } from "@rerun-io/web-viewer"

import { resolveBackendUrl, type ViewerSourceKind } from "@/lib/api"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

const SUPPORTED_RERUN_VIEWER_VERSION = "0.22.1"
const DEFAULT_RERUN_TIMELINE = "timestamp"

function normalizeRerunVersion(version: string | null | undefined) {
  if (!version) {
    return null
  }

  const normalized = version.trim()
  if (!normalized) {
    return null
  }

  const parts = normalized.split(".")
  if (parts.length >= 3) {
    return parts.slice(0, 3).join(".")
  }

  if (parts.length >= 2) {
    return parts.slice(0, 2).join(".")
  }

  return normalized
}

function isCompatibleRerunVersion(version: string | null | undefined) {
  const normalizedVersion = normalizeRerunVersion(version)
  const normalizedSupportedVersion = normalizeRerunVersion(
    SUPPORTED_RERUN_VIEWER_VERSION
  )

  if (!normalizedVersion || !normalizedSupportedVersion) {
    return true
  }

  if (normalizedVersion === normalizedSupportedVersion) {
    return true
  }

  const versionSegments = normalizedVersion.split(".")
  const supportedSegments = normalizedSupportedVersion.split(".")
  return (
    versionSegments.slice(0, 2).join(".") ===
    supportedSegments.slice(0, 2).join(".")
  )
}

function buildRrdSourceUrl(
  sourceUrl: string,
  updatedAt: string | null | undefined
) {
  const resolvedUrl = new URL(resolveBackendUrl(sourceUrl))

  if (updatedAt) {
    resolvedUrl.searchParams.set("_ts", updatedAt)
  }

  return resolvedUrl.toString()
}

function getErrorMessage(error: unknown) {
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message
  }

  return "The Rerun web viewer could not be initialized."
}

export function RerunViewer({
  currentTimestampNs,
  isPlaying,
  sourceKind,
  sourceUrl,
  updatedAt,
  viewerVersion,
}: {
  currentTimestampNs: number | null
  isPlaying: boolean
  sourceKind: ViewerSourceKind | null
  sourceUrl: string
  updatedAt?: string | null
  viewerVersion?: string | null
}) {
  const viewerParentRef = React.useRef<HTMLDivElement | null>(null)
  const viewerHandleRef = React.useRef<RerunWebViewer | null>(null)
  const activeRecordingIdRef = React.useRef<string | null>(null)
  const activeTimelineRef = React.useRef(DEFAULT_RERUN_TIMELINE)
  const [status, setStatus] = React.useState<"loading" | "ready" | "error">(
    "loading"
  )
  const [viewerError, setViewerError] = React.useState<string | null>(null)
  const isVersionCompatible = isCompatibleRerunVersion(viewerVersion)
  const resolvedSourceUrl = React.useMemo(
    () => buildRrdSourceUrl(sourceUrl, updatedAt),
    [sourceUrl, updatedAt]
  )

  React.useEffect(() => {
    if (sourceKind !== "rrd_url") {
      setStatus("error")
      setViewerError(
        "This embedded viewer currently supports backend-managed RRD recordings only."
      )
      return
    }

    if (!isVersionCompatible) {
      setStatus("error")
      setViewerError(
        `Viewer version ${viewerVersion ?? "unknown"} is not compatible with the embedded Rerun viewer ${SUPPORTED_RERUN_VIEWER_VERSION}.`
      )
      return
    }

    const parent = viewerParentRef.current
    if (!parent) {
      return
    }

    let isDisposed = false
    let resolveRecordingTimeoutId: number | null = null
    const viewer = new RerunWebViewer()

    viewerHandleRef.current = viewer
    activeRecordingIdRef.current = null
    activeTimelineRef.current = DEFAULT_RERUN_TIMELINE
    setStatus("loading")
    setViewerError(null)

    const resolveRecordingContext = () => {
      if (isDisposed) {
        return
      }

      const recordingId = viewer.get_active_recording_id()
      if (!recordingId) {
        resolveRecordingTimeoutId = window.setTimeout(
          resolveRecordingContext,
          100
        )
        return
      }

      const timestampRange = viewer.get_time_range(
        recordingId,
        DEFAULT_RERUN_TIMELINE
      )
      const nextTimeline =
        viewer.get_active_timeline(recordingId) ??
        (timestampRange ? DEFAULT_RERUN_TIMELINE : null)

      if (!nextTimeline) {
        resolveRecordingTimeoutId = window.setTimeout(
          resolveRecordingContext,
          100
        )
        return
      }

      activeRecordingIdRef.current = recordingId
      activeTimelineRef.current = nextTimeline

      if (nextTimeline === DEFAULT_RERUN_TIMELINE) {
        viewer.set_active_timeline(recordingId, DEFAULT_RERUN_TIMELINE)
      }

      setStatus("ready")
    }

    if (viewer.ready) {
      resolveRecordingContext()
    } else {
      viewer
        .start(resolvedSourceUrl, parent, {
          hide_welcome_screen: true,
          width: "100%",
          height: "100%",
        })
        .then(() => {
          if (isDisposed) {
            return
          }

          resolveRecordingContext()
        })
        .catch((error: unknown) => {
          if (isDisposed) {
            return
          }

          setStatus("error")
          setViewerError(getErrorMessage(error))
        })
    }

    return () => {
      isDisposed = true

      if (resolveRecordingTimeoutId !== null) {
        window.clearTimeout(resolveRecordingTimeoutId)
      }

      const activeRecordingId = activeRecordingIdRef.current
      activeRecordingIdRef.current = null
      activeTimelineRef.current = DEFAULT_RERUN_TIMELINE
      if (viewerHandleRef.current === viewer) {
        viewerHandleRef.current = null
      }

      try {
        if (activeRecordingId && viewer.ready) {
          viewer.set_playing(activeRecordingId, false)
        }
      } catch {
        // Ignore disposal-time viewer errors.
      }

      try {
        viewer.stop()
      } catch {
        // Ignore disposal-time viewer errors.
      }
    }
  }, [isVersionCompatible, resolvedSourceUrl, sourceKind, viewerVersion])

  React.useEffect(() => {
    const viewer = viewerHandleRef.current
    const recordingId = activeRecordingIdRef.current
    const timeline = activeTimelineRef.current

    if (
      status !== "ready" ||
      !viewer ||
      !recordingId ||
      currentTimestampNs === null
    ) {
      return
    }

    viewer.set_active_recording_id(recordingId)
    viewer.set_active_timeline(recordingId, timeline)
    viewer.set_current_time(recordingId, timeline, currentTimestampNs)
  }, [currentTimestampNs, status])

  React.useEffect(() => {
    const viewer = viewerHandleRef.current
    const recordingId = activeRecordingIdRef.current

    if (status !== "ready" || !viewer || !recordingId) {
      return
    }

    viewer.set_playing(recordingId, isPlaying)
  }, [isPlaying, status])

  return (
    <div className="space-y-3">
      {status === "error" ? (
        <Alert variant="destructive">
          <AlertTitle>Viewer unavailable</AlertTitle>
          <AlertDescription>
            {viewerError ?? "The Rerun web viewer could not be loaded."}
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="overflow-hidden rounded-lg border bg-black/5">
        <div
          className="relative h-[460px] w-full bg-black/10"
          ref={viewerParentRef}
        >
          {status !== "ready" ? (
            <div className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
              {status === "loading"
                ? "Loading viewer..."
                : "Viewer failed to load."}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
