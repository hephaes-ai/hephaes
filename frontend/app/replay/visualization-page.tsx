"use client"

import * as React from "react"
import { ArrowLeft } from "lucide-react"

import {
  useAsset,
  useAssetEpisode,
  useAssetEpisodes,
  useEpisodeSamples,
  useEpisodeTimeline,
} from "@/hooks/use-backend"
import { useEpisodeReplay } from "@/hooks/use-episode-replay"
import { BackendApiError, getErrorMessage } from "@/lib/api"
import {
  AppLink as Link,
  useAppPathname as usePathname,
  useAppRouter as useRouter,
  useAppSearchParams as useSearchParams,
} from "@/lib/app-routing"
import { formatDateTime, formatDuration } from "@/lib/format"
import { resolveReturnHref } from "@/lib/navigation"
import { buildReplayHref } from "@/lib/visualization"

import { VisualizationControls } from "./visualization-controls"
import { VisualizationScrubber } from "./visualization-scrubber"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { NativeSelect } from "@/components/ui/native-select"
import { Skeleton } from "@/components/ui/skeleton"

function VisualizationShellSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-28" />
      <Skeleton className="h-28 rounded-xl" />
      <Skeleton className="h-16 rounded-xl" />
      <Skeleton className="h-72 rounded-xl" />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Skeleton className="h-[360px] rounded-xl" />
        <Skeleton className="h-[360px] rounded-xl" />
      </div>
    </div>
  )
}

export function VisualizationPageFallback() {
  return <VisualizationShellSkeleton />
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function parsePositiveNumber(value: string | null, fallback: number) {
  if (!value) {
    return fallback
  }

  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

function parseTimestampNs(value: string | null) {
  if (!value) {
    return null
  }

  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function parseLaneIds(value: string | null) {
  if (!value) {
    return []
  }

  return value
    .split(",")
    .map((lane) => lane.trim())
    .filter(Boolean)
}

export function VisualizationPage() {
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()
  const searchParamsString = searchParams.toString()

  const assetId = searchParams.get("asset_id")?.trim() ?? ""
  const selectedEpisodeId = searchParams.get("episode_id")?.trim() ?? ""
  const selectedLanesParam = searchParams.get("lanes")
  const selectedLanesFromUrl = React.useMemo(
    () => parseLaneIds(selectedLanesParam),
    [selectedLanesParam]
  )
  const speedFromUrl = parsePositiveNumber(searchParams.get("speed"), 1)
  const timestampFromUrl = parseTimestampNs(searchParams.get("timestamp_ns"))
  const returnHref = resolveReturnHref(searchParams.get("from"), "/inventory")

  const [isPlaying, setIsPlaying] = React.useState(false)
  const [speed, setSpeed] = React.useState(speedFromUrl)
  const [currentTimestampNs, setCurrentTimestampNs] = React.useState<
    number | null
  >(timestampFromUrl)
  const [selectedLaneIds, setSelectedLaneIds] =
    React.useState<string[]>(selectedLanesFromUrl)
  const [isScrubberDragging, setIsScrubberDragging] = React.useState(false)
  const stepSizeNs = 100_000_000

  const assetResponse = useAsset(assetId)
  const episodesResponse = useAssetEpisodes(assetId)

  const episodes = episodesResponse.data ?? []
  const resolvedEpisodeId =
    selectedEpisodeId || (episodes.length === 1 ? episodes[0].episode_id : "")

  const episodeResponse = useAssetEpisode(assetId, resolvedEpisodeId)
  const selectedEpisode =
    episodes.find((episode) => episode.episode_id === resolvedEpisodeId) ?? null
  const hasVisualizableData =
    (episodeResponse.data?.has_visualizable_streams ??
      selectedEpisode?.has_visualizable_streams) !== false
  const timelineResponse = useEpisodeTimeline(assetId, resolvedEpisodeId)

  const timeline = timelineResponse.data
  const timelineStartNs =
    timeline?.start_timestamp_ns ?? timeline?.start_time_ns ?? 0
  const timelineEndNs =
    timeline?.end_timestamp_ns ??
    timeline?.end_time_ns ??
    (timeline?.duration_ns
      ? timelineStartNs + timeline.duration_ns
      : timelineStartNs + 1_000_000_000)
  const timelineLanes = React.useMemo(
    () => timeline?.lanes ?? [],
    [timeline?.lanes]
  )
  const availableLaneIds = React.useMemo(
    () => new Set(timelineLanes.map((lane) => lane.stream_id)),
    [timelineLanes]
  )
  const normalizedSelectedLaneIds = React.useMemo(() => {
    const filtered = selectedLaneIds.filter((laneId) =>
      availableLaneIds.has(laneId)
    )
    return filtered.length > 0
      ? filtered
      : timelineLanes.map((lane) => lane.stream_id)
  }, [availableLaneIds, selectedLaneIds, timelineLanes])
  const selectedLaneIdSet = React.useMemo(
    () => new Set(normalizedSelectedLaneIds),
    [normalizedSelectedLaneIds]
  )
  const selectedLaneTopicSet = React.useMemo(
    () =>
      new Set(
        timelineLanes
          .filter((lane) => selectedLaneIdSet.has(lane.stream_id))
          .map((lane) => lane.source_topic)
          .filter((topic): topic is string => Boolean(topic))
      ),
    [selectedLaneIdSet, timelineLanes]
  )
  const selectedLaneKeySet = React.useMemo(
    () =>
      new Set(
        timelineLanes
          .filter((lane) => selectedLaneIdSet.has(lane.stream_id))
          .map((lane) => lane.stream_key)
          .filter((streamKey): streamKey is string => Boolean(streamKey))
      ),
    [selectedLaneIdSet, timelineLanes]
  )
  const samplesWindowNs = Math.max(stepSizeNs * 10, 1_000_000_000)
  const replay = useEpisodeReplay({
    assetId,
    cursorNs: currentTimestampNs,
    enabled: Boolean(
      assetId && resolvedEpisodeId && currentTimestampNs !== null
    ),
    episodeId: resolvedEpisodeId,
    interactionMode: isScrubberDragging
      ? "dragging"
      : isPlaying
        ? "playing"
        : "idle",
    isPlaying,
    speed,
    streamIds: normalizedSelectedLaneIds,
    windowAfterNs: samplesWindowNs,
    windowBeforeNs: samplesWindowNs,
  })

  const samplesQuery = React.useMemo(() => {
    if (!assetId || !resolvedEpisodeId || currentTimestampNs === null) {
      return null
    }

    return {
      stream_ids: normalizedSelectedLaneIds,
      timestamp_ns: currentTimestampNs,
      window_after_ns: samplesWindowNs,
      window_before_ns: samplesWindowNs,
    }
  }, [
    assetId,
    currentTimestampNs,
    normalizedSelectedLaneIds,
    resolvedEpisodeId,
    samplesWindowNs,
  ])

  const shouldUseRestSamples =
    samplesQuery !== null &&
    (replay.connectionStatus !== "connected" || replay.samples === null)
  const fallbackSamplesResponse = useEpisodeSamples(
    assetId,
    resolvedEpisodeId,
    shouldUseRestSamples ? samplesQuery : null
  )

  const updateVisualizeState = React.useCallback(
    (updates: Record<string, string | null>) => {
      const nextParams = new URLSearchParams(searchParamsString)

      for (const [key, value] of Object.entries(updates)) {
        const normalized = value?.trim() ?? ""
        if (!normalized) {
          nextParams.delete(key)
        } else {
          nextParams.set(key, normalized)
        }
      }

      const nextQuery = nextParams.toString()
      if (nextQuery === searchParamsString) {
        return
      }

      const nextHref = nextQuery ? `${pathname}?${nextQuery}` : pathname

      router.replace(nextHref, { scroll: false })
    },
    [pathname, router, searchParamsString]
  )

  const seekTo = React.useCallback(
    (timestampNs: number, options?: { updateUrl?: boolean }) => {
      const clampedTimestamp = clamp(
        Math.round(timestampNs),
        timelineStartNs,
        timelineEndNs
      )
      setCurrentTimestampNs(clampedTimestamp)

      if (options?.updateUrl !== false) {
        updateVisualizeState({ timestamp_ns: String(clampedTimestamp) })
      }
    },
    [timelineEndNs, timelineStartNs, updateVisualizeState]
  )

  function onSelectEpisode(nextEpisodeId: string) {
    if (!assetId || !nextEpisodeId) {
      return
    }

    const nextHref = buildReplayHref({
      assetId,
      episodeId: nextEpisodeId,
      from: returnHref,
    })

    router.replace(nextHref, { scroll: false })

    setIsPlaying(false)
    setCurrentTimestampNs(null)
  }

  function onToggleLane(streamId: string) {
    setSelectedLaneIds((current) => {
      const next = new Set(current)
      if (next.has(streamId)) {
        next.delete(streamId)
      } else {
        next.add(streamId)
      }

      const normalized = Array.from(next).filter((laneId) =>
        availableLaneIds.has(laneId)
      )
      updateVisualizeState({
        lanes: normalized.length > 0 ? normalized.join(",") : null,
      })
      setIsPlaying(false)
      return normalized
    })
  }

  function setPlaybackSpeed(nextSpeed: number) {
    setSpeed(nextSpeed)
    updateVisualizeState({ speed: String(nextSpeed) })
  }

  React.useEffect(() => {
    setSelectedLaneIds((current) => {
      if (
        current.length === selectedLanesFromUrl.length &&
        current.every((value, index) => value === selectedLanesFromUrl[index])
      ) {
        return current
      }

      return selectedLanesFromUrl
    })
  }, [selectedLanesFromUrl])

  React.useEffect(() => {
    setSpeed(speedFromUrl)
  }, [speedFromUrl])

  React.useEffect(() => {
    if (timelineStartNs >= timelineEndNs) {
      return
    }

    if (currentTimestampNs === null) {
      const initialTimestamp = timestampFromUrl ?? timelineStartNs
      seekTo(initialTimestamp, { updateUrl: timestampFromUrl === null })
      return
    }

    if (
      currentTimestampNs < timelineStartNs ||
      currentTimestampNs > timelineEndNs
    ) {
      seekTo(currentTimestampNs, { updateUrl: true })
    }
  }, [
    currentTimestampNs,
    seekTo,
    timelineEndNs,
    timelineStartNs,
    timestampFromUrl,
  ])

  React.useEffect(() => {
    if (!isPlaying || currentTimestampNs === null) {
      return
    }

    let lastTick = performance.now()
    const intervalId = window.setInterval(() => {
      const now = performance.now()
      const deltaMs = now - lastTick
      lastTick = now

      setCurrentTimestampNs((current) => {
        if (current === null) {
          return current
        }

        const next = clamp(
          Math.round(current + deltaMs * 1_000_000 * speed),
          timelineStartNs,
          timelineEndNs
        )
        if (next >= timelineEndNs) {
          setIsPlaying(false)
        }

        return next
      })
    }, 100)

    return () => window.clearInterval(intervalId)
  }, [currentTimestampNs, isPlaying, speed, timelineEndNs, timelineStartNs])

  React.useEffect(() => {
    if (isScrubberDragging || currentTimestampNs === null) {
      return
    }

    if (searchParams.get("timestamp_ns") === String(currentTimestampNs)) {
      return
    }

    updateVisualizeState({ timestamp_ns: String(currentTimestampNs) })
  }, [
    currentTimestampNs,
    isScrubberDragging,
    searchParams,
    updateVisualizeState,
  ])

  if (!assetId) {
    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <Alert variant="destructive">
          <AlertTitle>Missing asset</AlertTitle>
          <AlertDescription>
            Open replay from inventory or asset detail so an asset ID is
            provided.
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  if (assetResponse.isLoading || episodesResponse.isLoading) {
    return <VisualizationShellSkeleton />
  }

  if (assetResponse.error || episodesResponse.error) {
    const error = assetResponse.error ?? episodesResponse.error
    const isNotFound = error instanceof BackendApiError && error.status === 404

    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <Alert variant="destructive">
          <AlertTitle>
            {isNotFound ? "Replay data not found" : "Could not load replay"}
          </AlertTitle>
          <AlertDescription>{getErrorMessage(error)}</AlertDescription>
        </Alert>
      </div>
    )
  }

  const assetDetail = assetResponse.data
  if (!assetDetail) {
    return null
  }

  if (episodes.length === 0) {
    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <Alert>
          <AlertTitle>No episodes available</AlertTitle>
          <AlertDescription>
            This asset does not expose replay episode data yet. Run indexing or
            replay-preparation jobs and try again.
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  const effectiveTimestampNs = currentTimestampNs ?? timelineStartNs
  const cursorOffsetNs = Math.max(0, effectiveTimestampNs - timelineStartNs)
  const confirmedSamplesResponse =
    replay.samples ?? fallbackSamplesResponse.data ?? null
  const confirmedResponseTimestampNs =
    confirmedSamplesResponse?.requested_timestamp_ns ?? null
  const isRealtimePayloadPending =
    replay.connectionStatus === "connected" &&
    replay.lastRequestedRevision > replay.lastPayloadRevision
  const isPayloadLoading =
    Boolean(resolvedEpisodeId) &&
    (replay.connectionStatus === "connecting" ||
      isRealtimePayloadPending ||
      (shouldUseRestSamples && fallbackSamplesResponse.isLoading) ||
      confirmedResponseTimestampNs !== effectiveTimestampNs)
  const replayTransportLabel =
    replay.connectionStatus === "connected"
      ? "Realtime replay"
      : replay.connectionStatus === "connecting"
        ? "Realtime connecting"
        : "REST fallback"
  const selectedSamples = (() => {
    const data = confirmedSamplesResponse
    if (!data) {
      return [] as Array<{
        message_type: string
        modality: string
        payload: unknown
        selection_strategy?: "latest_at_or_before" | "window"
        stream_id: string
        timestamp_ns: number
        topic_name: string
      }>
    }

    if (Array.isArray(data.streams) && data.streams.length > 0) {
      return data.streams
        .filter(
          (stream) =>
            selectedLaneIdSet.has(stream.stream_id) ||
            (stream.source_topic
              ? selectedLaneTopicSet.has(stream.source_topic)
              : false) ||
            (stream.stream_key
              ? selectedLaneKeySet.has(stream.stream_key)
              : false)
        )
        .flatMap((stream) =>
          (stream.samples ?? []).map((sample) => ({
            message_type: stream.stream_key,
            modality: stream.modality,
            payload: sample.payload,
            selection_strategy: stream.selection_strategy,
            stream_id: stream.stream_id,
            timestamp_ns: sample.timestamp_ns,
            topic_name: stream.source_topic,
          }))
        )
    }

    return (data.samples ?? [])
      .filter(
        (sample) =>
          selectedLaneIdSet.has(sample.stream_id) ||
          (sample.topic_name
            ? selectedLaneTopicSet.has(sample.topic_name)
            : false) ||
          (sample.message_type
            ? selectedLaneKeySet.has(sample.message_type)
            : false)
      )
      .map((sample) => ({
        message_type: sample.message_type ?? "Unknown",
        modality: sample.modality,
        payload: sample.payload,
        selection_strategy: sample.selection_strategy,
        stream_id: sample.stream_id,
        timestamp_ns: sample.timestamp_ns,
        topic_name: sample.topic_name ?? sample.stream_id,
      }))
  })()
  const payloadsByStreamId = selectedSamples.reduce<
    Record<string, Array<{ payload: unknown; timestamp_ns: number }>>
  >((accumulator, sample) => {
    const existingSamples = accumulator[sample.stream_id] ?? []
    existingSamples.push({
      payload: sample.payload,
      timestamp_ns: sample.timestamp_ns,
    })
    accumulator[sample.stream_id] = existingSamples
    return accumulator
  }, {})

  return (
    <div className="space-y-6">
      <Button asChild size="sm" variant="ghost">
        <Link href={returnHref}>
          <ArrowLeft className="size-4" />
          Back
        </Link>
      </Button>

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <CardTitle className="text-xl">Replay</CardTitle>
            <CardDescription>{assetDetail.asset.file_name}</CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">Asset {assetId}</Badge>
            {selectedEpisode ? (
              <Badge variant="secondary">Episode {selectedEpisode.label}</Badge>
            ) : null}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                Duration
              </dt>
              <dd className="text-sm font-medium">
                {formatDuration(selectedEpisode?.duration)}
              </dd>
            </div>
            <div>
              <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                Start
              </dt>
              <dd className="text-sm font-medium">
                {formatDateTime(selectedEpisode?.start_time)}
              </dd>
            </div>
            <div>
              <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                End
              </dt>
              <dd className="text-sm font-medium">
                {formatDateTime(selectedEpisode?.end_time)}
              </dd>
            </div>
            <div>
              <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                Lane count
              </dt>
              <dd className="text-sm font-medium">
                {selectedEpisode?.default_lane_count ?? "Not available"}
              </dd>
            </div>
          </dl>

          {episodes.length > 1 && !selectedEpisode ? (
            <Alert>
              <AlertTitle>Select an episode</AlertTitle>
              <AlertDescription>
                This asset has multiple episodes. Choose one to load replay
                playback data.
              </AlertDescription>
            </Alert>
          ) : null}

          {episodes.length > 1 ? (
            <div className="max-w-sm space-y-2">
              <label
                className="text-xs tracking-wide text-muted-foreground uppercase"
                htmlFor="episode-picker"
              >
                Episode
              </label>
              <NativeSelect
                id="episode-picker"
                onChange={(event) => onSelectEpisode(event.target.value)}
                value={resolvedEpisodeId}
              >
                <option value="">Select episode</option>
                {episodes.map((episode) => (
                  <option key={episode.episode_id} value={episode.episode_id}>
                    {episode.label}
                  </option>
                ))}
              </NativeSelect>
            </div>
          ) : null}

          {!hasVisualizableData ? (
            <Alert>
              <AlertTitle>Episode has no supported replay data</AlertTitle>
              <AlertDescription>
                This episode is available but does not currently expose streams
                supported by the replay workflow.
              </AlertDescription>
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-5">
          <VisualizationControls
            cursorOffsetNs={cursorOffsetNs}
            effectiveTimestampNs={effectiveTimestampNs}
            isPlaying={isPlaying}
            onPause={() => setIsPlaying(false)}
            onPlay={() => setIsPlaying(true)}
            onSeekTo={(timestampNs) => seekTo(timestampNs)}
            onSetSpeed={setPlaybackSpeed}
            replayTransportLabel={replayTransportLabel}
            replayConnectionStatus={replay.connectionStatus}
            samplesWindowNs={samplesWindowNs}
            speed={speed}
            stepSizeNs={stepSizeNs}
            timelineEndNs={timelineEndNs}
            timelineStartNs={timelineStartNs}
          />

          {replay.error ? (
            <Alert>
              <AlertTitle>Realtime replay unavailable</AlertTitle>
              <AlertDescription>
                {getErrorMessage(replay.error)}
              </AlertDescription>
            </Alert>
          ) : null}

          {resolvedEpisodeId && timelineResponse.isLoading ? (
            <Skeleton className="h-56 rounded-xl" />
          ) : timelineResponse.error ? (
            <Alert variant="destructive">
              <AlertTitle>Could not load timeline</AlertTitle>
              <AlertDescription>
                {getErrorMessage(timelineResponse.error)}
              </AlertDescription>
            </Alert>
          ) : timelineLanes.length > 0 ? (
            <VisualizationScrubber
              currentTimestampNs={effectiveTimestampNs}
              endNs={timelineEndNs}
              lanes={timelineLanes.map((lane) => ({
                ...lane,
                label:
                  lane.label ||
                  lane.source_topic ||
                  lane.stream_key ||
                  lane.stream_id,
              }))}
              onDragStateChange={setIsScrubberDragging}
              onSeek={(timestampNs) => {
                setIsPlaying(false)
                seekTo(timestampNs, { updateUrl: !isScrubberDragging })
              }}
              onToggleLane={onToggleLane}
              isPayloadLoading={isPayloadLoading}
              payloadByStreamId={payloadsByStreamId}
              selectedLaneIds={normalizedSelectedLaneIds}
              startNs={timelineStartNs}
            />
          ) : (
            <Alert>
              <AlertTitle>No timeline lanes available</AlertTitle>
              <AlertDescription>
                This episode has not returned scrubber lane metadata yet. Check
                backend timeline payloads and try again.
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
