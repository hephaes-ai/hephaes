"use client"

import * as React from "react"
import { Pause, Play, SkipBack, SkipForward } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { NativeSelect } from "@/components/ui/native-select"

function formatDurationNs(durationNs: number) {
  const normalizedDurationNs = Math.max(0, durationNs)
  const seconds = normalizedDurationNs / 1_000_000_000
  if (seconds < 60) {
    return `${seconds.toFixed(2)} s`
  }

  const totalSeconds = Math.floor(seconds)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor(totalSeconds / 60)
  const remainingMinutes = minutes % 60
  const remainingSeconds = totalSeconds % 60

  if (hours > 0) {
    return `${hours}h ${remainingMinutes}m ${remainingSeconds}s`
  }

  return `${minutes}m ${remainingSeconds}s`
}

export function VisualizationControls({
  cursorOffsetNs,
  effectiveTimestampNs,
  isPlaying,
  onPause,
  onPlay,
  onSeekTo,
  onSetSpeed,
  replayTransportLabel,
  replayConnectionStatus,
  samplesWindowNs,
  speed,
  stepSizeNs,
  timelineEndNs,
  timelineStartNs,
}: {
  cursorOffsetNs: number
  effectiveTimestampNs: number
  isPlaying: boolean
  onPause: () => void
  onPlay: () => void
  onSeekTo: (timestampNs: number) => void
  onSetSpeed: (speed: number) => void
  replayTransportLabel: string
  replayConnectionStatus: string
  samplesWindowNs: number
  speed: number
  stepSizeNs: number
  timelineEndNs: number
  timelineStartNs: number
}) {
  const stepBackwardDisabled = effectiveTimestampNs <= timelineStartNs
  const stepForwardDisabled = effectiveTimestampNs >= timelineEndNs

  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          onClick={() => {
            onPause()
            onSeekTo(timelineStartNs)
          }}
          size="sm"
          type="button"
          variant="outline"
        >
          <SkipBack className="size-3.5" />
          Start
        </Button>
        {isPlaying ? (
          <Button
            onClick={onPause}
            size="sm"
            type="button"
            variant="secondary"
          >
            <Pause className="size-3.5" />
            Pause
          </Button>
        ) : (
          <Button
            onClick={() => {
              if (effectiveTimestampNs >= timelineEndNs) {
                onSeekTo(timelineStartNs)
              }

              onPlay()
            }}
            size="sm"
            type="button"
            variant="secondary"
          >
            <Play className="size-3.5" />
            Play
          </Button>
        )}
        <Button
          disabled={stepBackwardDisabled}
          onClick={() => {
            onPause()
            onSeekTo(effectiveTimestampNs - stepSizeNs)
          }}
          size="sm"
          type="button"
          variant="outline"
        >
          Step -
        </Button>
        <Button
          disabled={stepForwardDisabled}
          onClick={() => {
            onPause()
            onSeekTo(effectiveTimestampNs + stepSizeNs)
          }}
          size="sm"
          type="button"
          variant="outline"
        >
          Step +
        </Button>
        <Button
          onClick={() => {
            onPause()
            onSeekTo(timelineEndNs)
          }}
          size="sm"
          type="button"
          variant="outline"
        >
          <SkipForward className="size-3.5" />
          End
        </Button>
      </div>

      <div className="flex flex-wrap items-end gap-3 lg:justify-end">
        <div className="flex flex-wrap items-center gap-2 lg:justify-end">
          <Badge variant="outline">
            Cursor +{formatDurationNs(cursorOffsetNs)}
          </Badge>
          <Badge variant="outline">
            Window ±{formatDurationNs(samplesWindowNs)}
          </Badge>
          <Badge
            variant={
              replayConnectionStatus === "connected"
                ? "secondary"
                : "outline"
            }
          >
            {replayTransportLabel}
          </Badge>
        </div>

        <div className="max-w-[140px] space-y-1">
          <label
            className="text-xs tracking-wide text-muted-foreground uppercase"
            htmlFor="playback-speed"
          >
            Speed
          </label>
          <NativeSelect
            id="playback-speed"
            onChange={(event) =>
              onSetSpeed(Number(event.target.value))
            }
            value={String(speed)}
          >
            <option value="0.5">0.5x</option>
            <option value="1">1x</option>
            <option value="1.5">1.5x</option>
            <option value="2">2x</option>
          </NativeSelect>
        </div>
      </div>
    </div>
  )
}
