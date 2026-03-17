"use client";

import * as React from "react";

import type { EpisodeTimelineLane } from "@/lib/api";
import { cn } from "@/lib/utils";

import { Button } from "@/components/ui/button";

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function timestampToPercent(timestampNs: number, startNs: number, endNs: number) {
  if (endNs <= startNs) {
    return 0;
  }

  return clamp(((timestampNs - startNs) / (endNs - startNs)) * 100, 0, 100);
}

function percentToTimestamp(percent: number, startNs: number, endNs: number) {
  if (endNs <= startNs) {
    return startNs;
  }

  const ratio = clamp(percent, 0, 100) / 100;
  return Math.round(startNs + (endNs - startNs) * ratio);
}

function getModalityClassName(modality: string) {
  if (modality === "image") {
    return "bg-sky-500/70";
  }

  if (modality === "points") {
    return "bg-emerald-500/70";
  }

  if (modality === "scalar_series") {
    return "bg-amber-500/70";
  }

  return "bg-muted-foreground/60";
}

interface VisualizationScrubberProps {
  currentTimestampNs: number;
  endNs: number;
  lanes: EpisodeTimelineLane[];
  onDragStateChange?: (isDragging: boolean) => void;
  onSeek: (timestampNs: number) => void;
  onToggleLane: (streamId: string) => void;
  selectedLaneIds: string[];
  startNs: number;
}

export function VisualizationScrubber({
  currentTimestampNs,
  endNs,
  lanes,
  onDragStateChange,
  onSeek,
  onToggleLane,
  selectedLaneIds,
  startNs,
}: VisualizationScrubberProps) {
  const selectedSet = React.useMemo(() => new Set(selectedLaneIds), [selectedLaneIds]);
  const rangeValue = timestampToPercent(currentTimestampNs, startNs, endNs);

  function onRangeChange(event: React.ChangeEvent<HTMLInputElement>) {
    const nextTimestamp = percentToTimestamp(Number(event.target.value), startNs, endNs);
    onSeek(nextTimestamp);
  }

  function onLaneSeek(event: React.MouseEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    if (bounds.width <= 0) {
      return;
    }

    const percent = ((event.clientX - bounds.left) / bounds.width) * 100;
    onSeek(percentToTimestamp(percent, startNs, endNs));
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Timeline cursor</span>
          <span>{rangeValue.toFixed(1)}%</span>
        </div>
        <input
          className="w-full accent-primary"
          max={100}
          min={0}
          onChange={onRangeChange}
          onMouseDown={() => onDragStateChange?.(true)}
          onMouseUp={() => onDragStateChange?.(false)}
          onTouchEnd={() => onDragStateChange?.(false)}
          onTouchStart={() => onDragStateChange?.(true)}
          step={0.1}
          type="range"
          value={rangeValue}
        />
      </div>

      <div className="space-y-3">
        {lanes.map((lane) => {
          const laneEvents = Array.isArray(lane.events) ? lane.events : [];
          const laneBuckets = Array.isArray(lane.buckets) ? lane.buckets : [];
          const bucketEvents = laneBuckets
            .filter((bucket) => bucket.event_count > 0)
            .map((bucket) => ({
              count: bucket.event_count,
              timestamp_ns: startNs + bucket.start_offset_ns,
            }));
          const markers = laneEvents.length > 0 ? laneEvents : bucketEvents;
          const isSelected = selectedSet.has(lane.stream_id);
          const cursorPercent = timestampToPercent(currentTimestampNs, startNs, endNs);

          return (
            <div key={lane.stream_id} className={cn("rounded-lg border p-3", !isSelected && "opacity-60")}>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">{lane.label || lane.stream_id}</p>
                  <p className="text-xs text-muted-foreground">{lane.modality.replace(/_/g, " ")}</p>
                </div>
                <Button onClick={() => onToggleLane(lane.stream_id)} size="xs" type="button" variant="outline">
                  {isSelected ? "Hide lane" : "Show lane"}
                </Button>
              </div>

              <div
                className="relative h-10 cursor-pointer rounded-md border bg-muted/30"
                onClick={onLaneSeek}
                role="button"
                tabIndex={0}
              >
                {markers.map((event, index) => {
                  const eventPercent = timestampToPercent(event.timestamp_ns, startNs, endNs);

                  return (
                    <div
                      className={cn(
                        "absolute top-1/2 h-4 w-1.5 -translate-y-1/2 rounded-sm",
                        getModalityClassName(lane.modality),
                      )}
                      key={`${lane.stream_id}-${index}-${event.timestamp_ns}`}
                      style={{ left: `${eventPercent}%` }}
                      title={`${event.timestamp_ns}`}
                    />
                  );
                })}

                <div
                  className="pointer-events-none absolute top-0 h-full w-0.5 bg-primary"
                  style={{ left: `${cursorPercent}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
