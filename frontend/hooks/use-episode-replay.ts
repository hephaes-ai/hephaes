"use client"

import * as React from "react"

import {
  resolveBackendWebSocketUrl,
  type EpisodeReplayClientMessage,
  type EpisodeReplayReadyMessage,
  type EpisodeReplayServerMessage,
  type EpisodeSamplesResponse,
  type ReplayConnectionStatus,
} from "@/lib/api"

type ReplayInteractionMode = "idle" | "playing" | "dragging"

interface ReplayOptionsSnapshot {
  cursorNs: number | null
  isPlaying: boolean
  speed: number
  streamIds: string[]
  windowAfterNs: number
  windowBeforeNs: number
}

interface UseEpisodeReplayOptions extends ReplayOptionsSnapshot {
  assetId: string
  enabled: boolean
  episodeId: string
  interactionMode: ReplayInteractionMode
}

export interface ReplayPlaybackState {
  isPlaying: boolean
  revision: number
  speed: number
}

export interface UseEpisodeReplayResult {
  connectionStatus: ReplayConnectionStatus
  error: Error | null
  lastAckedRevision: number
  lastPayloadRevision: number
  lastRequestedRevision: number
  playbackState: ReplayPlaybackState | null
  ready: EpisodeReplayReadyMessage | null
  samples: EpisodeSamplesResponse | null
}

function serializeStreamIds(streamIds: string[]) {
  return streamIds.join("|")
}

function parseReplayMessage(rawMessage: string): EpisodeReplayServerMessage {
  const parsed = JSON.parse(rawMessage) as unknown
  if (
    !parsed ||
    typeof parsed !== "object" ||
    !("type" in parsed) ||
    typeof parsed.type !== "string"
  ) {
    throw new Error("Replay websocket returned an invalid message payload.")
  }

  return parsed as EpisodeReplayServerMessage
}

export function useEpisodeReplay({
  assetId,
  cursorNs,
  enabled,
  episodeId,
  interactionMode,
  isPlaying,
  speed,
  streamIds,
  windowAfterNs,
  windowBeforeNs,
}: UseEpisodeReplayOptions): UseEpisodeReplayResult {
  const [connectionStatus, setConnectionStatus] =
    React.useState<ReplayConnectionStatus>(enabled ? "connecting" : "idle")
  const [error, setError] = React.useState<Error | null>(null)
  const [ready, setReady] = React.useState<EpisodeReplayReadyMessage | null>(
    null
  )
  const [samples, setSamples] = React.useState<EpisodeSamplesResponse | null>(
    null
  )
  const [playbackState, setPlaybackState] =
    React.useState<ReplayPlaybackState | null>(null)
  const [lastAckedRevision, setLastAckedRevision] = React.useState(-1)
  const [lastPayloadRevision, setLastPayloadRevision] = React.useState(-1)
  const [lastRequestedRevision, setLastRequestedRevision] = React.useState(-1)

  const socketRef = React.useRef<WebSocket | null>(null)
  const readyRef = React.useRef(false)
  const nextRevisionRef = React.useRef(1)
  const pendingSeekTimerRef = React.useRef<number | null>(null)
  const pendingSeekCursorRef = React.useRef<number | null>(null)
  const lastPayloadRevisionRef = React.useRef(-1)
  const lastSentCursorRef = React.useRef<number | null>(null)
  const lastSentStreamKeyRef = React.useRef("")
  const lastSentWindowKeyRef = React.useRef("")
  const lastSentPlaybackRef = React.useRef<{
    isPlaying: boolean
    speed: number
  } | null>(null)
  const latestOptionsRef = React.useRef<ReplayOptionsSnapshot>({
    cursorNs,
    isPlaying,
    speed,
    streamIds,
    windowAfterNs,
    windowBeforeNs,
  })

  React.useEffect(() => {
    latestOptionsRef.current = {
      cursorNs,
      isPlaying,
      speed,
      streamIds,
      windowAfterNs,
      windowBeforeNs,
    }
  }, [cursorNs, isPlaying, speed, streamIds, windowAfterNs, windowBeforeNs])

  const clearPendingSeek = React.useCallback(() => {
    if (pendingSeekTimerRef.current !== null) {
      window.clearTimeout(pendingSeekTimerRef.current)
      pendingSeekTimerRef.current = null
    }
  }, [])

  const sendMessage = React.useCallback(
    (
      message: EpisodeReplayClientMessage,
      options?: { affectsSamples?: boolean }
    ) => {
      const socket = socketRef.current
      if (
        !socket ||
        socket.readyState !== WebSocket.OPEN ||
        !readyRef.current
      ) {
        return null
      }

      const revision = nextRevisionRef.current
      nextRevisionRef.current += 1
      socket.send(JSON.stringify({ ...message, revision }))

      if (options?.affectsSamples) {
        setLastRequestedRevision(revision)
      }

      return revision
    },
    []
  )

  const flushPendingSeek = React.useCallback(() => {
    clearPendingSeek()

    const pendingCursor = pendingSeekCursorRef.current
    if (pendingCursor === null) {
      return
    }

    pendingSeekCursorRef.current = null
    const revision = sendMessage(
      {
        type: "seek",
        cursor_ns: pendingCursor,
      },
      { affectsSamples: true }
    )

    if (revision !== null) {
      lastSentCursorRef.current = pendingCursor
    }
  }, [clearPendingSeek, sendMessage])

  const scheduleSeek = React.useCallback(
    (nextCursorNs: number, nextInteractionMode: ReplayInteractionMode) => {
      pendingSeekCursorRef.current = nextCursorNs

      if (nextInteractionMode === "idle") {
        flushPendingSeek()
        return
      }

      clearPendingSeek()
      pendingSeekTimerRef.current = window.setTimeout(() => {
        flushPendingSeek()
      }, 75)
    },
    [clearPendingSeek, flushPendingSeek]
  )

  React.useEffect(() => {
    if (!enabled || !assetId || !episodeId) {
      clearPendingSeek()
      socketRef.current?.close()
      socketRef.current = null
      readyRef.current = false
      pendingSeekCursorRef.current = null
      lastSentCursorRef.current = null
      lastSentStreamKeyRef.current = ""
      lastSentWindowKeyRef.current = ""
      lastSentPlaybackRef.current = null
      nextRevisionRef.current = 1
      lastPayloadRevisionRef.current = -1
      setConnectionStatus("idle")
      setError(null)
      setReady(null)
      setSamples(null)
      setPlaybackState(null)
      setLastAckedRevision(-1)
      setLastPayloadRevision(-1)
      setLastRequestedRevision(-1)
      return
    }

    let isDisposed = false
    const websocket = new WebSocket(
      resolveBackendWebSocketUrl(
        `/assets/${assetId}/episodes/${episodeId}/replay`
      )
    )

    socketRef.current = websocket
    readyRef.current = false
    pendingSeekCursorRef.current = null
    lastSentCursorRef.current = null
    lastSentStreamKeyRef.current = ""
    lastSentWindowKeyRef.current = ""
    lastSentPlaybackRef.current = null
    nextRevisionRef.current = 1
    lastPayloadRevisionRef.current = -1

    setConnectionStatus("connecting")
    setError(null)
    setReady(null)
    setSamples(null)
    setPlaybackState(null)
    setLastAckedRevision(-1)
    setLastPayloadRevision(-1)
    setLastRequestedRevision(-1)

    websocket.addEventListener("message", (event) => {
      if (isDisposed) {
        return
      }

      let message: EpisodeReplayServerMessage
      try {
        message = parseReplayMessage(event.data)
      } catch (nextError) {
        setConnectionStatus("error")
        setError(
          nextError instanceof Error
            ? nextError
            : new Error("Replay websocket returned invalid data.")
        )
        return
      }

      if (message.type === "ready") {
        readyRef.current = true
        setConnectionStatus("connected")
        setReady(message)

        const snapshot = latestOptionsRef.current
        const revision = sendMessage(
          {
            type: "hello",
            cursor_ns: snapshot.cursorNs ?? undefined,
            is_playing: snapshot.isPlaying,
            speed: snapshot.speed,
            stream_ids: snapshot.streamIds,
            window_after_ns: snapshot.windowAfterNs,
            window_before_ns: snapshot.windowBeforeNs,
          },
          { affectsSamples: snapshot.cursorNs !== null }
        )

        if (revision !== null) {
          lastSentCursorRef.current = snapshot.cursorNs
          lastSentStreamKeyRef.current = serializeStreamIds(snapshot.streamIds)
          lastSentWindowKeyRef.current = `${snapshot.windowBeforeNs}:${snapshot.windowAfterNs}`
          lastSentPlaybackRef.current = {
            isPlaying: snapshot.isPlaying,
            speed: snapshot.speed,
          }
        }
        return
      }

      if (message.type === "cursor_ack") {
        setLastAckedRevision((current) => Math.max(current, message.revision))
        return
      }

      if (message.type === "samples") {
        if (message.revision < lastPayloadRevisionRef.current) {
          return
        }

        lastPayloadRevisionRef.current = message.revision
        setLastPayloadRevision(message.revision)
        setSamples(message.data)
        return
      }

      if (message.type === "playback_state") {
        setPlaybackState({
          isPlaying: message.is_playing,
          revision: message.revision,
          speed: message.speed,
        })
        return
      }

      if (message.type === "error") {
        const nextError =
          message.detail.trim().length > 0
            ? new Error(message.detail)
            : new Error("Replay websocket returned an unknown error.")
        setConnectionStatus("error")
        setError(nextError)
      }
    })

    websocket.addEventListener("error", () => {
      if (isDisposed) {
        return
      }

      setConnectionStatus("error")
      setError(
        new Error(
          "Could not connect to realtime replay. Falling back to REST samples."
        )
      )
    })

    websocket.addEventListener("close", () => {
      if (isDisposed) {
        return
      }

      readyRef.current = false
      clearPendingSeek()
      setConnectionStatus((current) =>
        current === "error" ? "error" : "closed"
      )
    })

    return () => {
      isDisposed = true
      readyRef.current = false
      clearPendingSeek()
      websocket.close()
      if (socketRef.current === websocket) {
        socketRef.current = null
      }
    }
  }, [assetId, clearPendingSeek, enabled, episodeId, sendMessage])

  React.useEffect(() => {
    if (!readyRef.current) {
      return
    }

    const nextStreamKey = serializeStreamIds(streamIds)
    if (nextStreamKey === lastSentStreamKeyRef.current) {
      return
    }

    const revision = sendMessage(
      {
        type: "set_streams",
        stream_ids: streamIds,
      },
      { affectsSamples: cursorNs !== null }
    )

    if (revision !== null) {
      lastSentStreamKeyRef.current = nextStreamKey
    }
  }, [cursorNs, sendMessage, streamIds])

  React.useEffect(() => {
    if (!readyRef.current) {
      return
    }

    const nextWindowKey = `${windowBeforeNs}:${windowAfterNs}`
    if (nextWindowKey === lastSentWindowKeyRef.current) {
      return
    }

    const revision = sendMessage(
      {
        type: "set_scalar_window",
        window_after_ns: windowAfterNs,
        window_before_ns: windowBeforeNs,
      },
      { affectsSamples: cursorNs !== null }
    )

    if (revision !== null) {
      lastSentWindowKeyRef.current = nextWindowKey
    }
  }, [cursorNs, sendMessage, windowAfterNs, windowBeforeNs])

  React.useEffect(() => {
    if (!readyRef.current) {
      return
    }

    const previousPlayback = lastSentPlaybackRef.current
    if (
      previousPlayback &&
      previousPlayback.isPlaying === isPlaying &&
      previousPlayback.speed === speed
    ) {
      return
    }

    let revision: number | null = null
    if (previousPlayback && previousPlayback.isPlaying !== isPlaying) {
      revision = sendMessage(
        isPlaying
          ? {
              type: "play",
              speed,
            }
          : {
              type: "pause",
            }
      )
    } else if (!previousPlayback || previousPlayback.speed !== speed) {
      revision = sendMessage({
        type: "set_speed",
        speed,
      })
    }

    if (revision !== null) {
      lastSentPlaybackRef.current = { isPlaying, speed }
    }
  }, [isPlaying, sendMessage, speed])

  React.useEffect(() => {
    if (!readyRef.current || cursorNs === null) {
      return
    }

    if (
      pendingSeekCursorRef.current === null &&
      lastSentCursorRef.current === cursorNs
    ) {
      return
    }

    scheduleSeek(cursorNs, interactionMode)
  }, [cursorNs, interactionMode, scheduleSeek])

  return {
    connectionStatus,
    error,
    lastAckedRevision,
    lastPayloadRevision,
    lastRequestedRevision,
    playbackState,
    ready,
    samples,
  }
}
