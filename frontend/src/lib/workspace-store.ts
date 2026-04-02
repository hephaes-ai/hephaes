"use client"

import * as React from "react"

import {
  setActiveWorkspaceRequestId,
  type WorkspaceRegistrySummary,
} from "@/lib/api"

export type WorkspaceStoreStatus = "error" | "idle" | "loading" | "ready"

export interface WorkspaceStoreSnapshot {
  activeWorkspaceId: string | null
  error: string | null
  status: WorkspaceStoreStatus
  workspaces: WorkspaceRegistrySummary[]
}

declare global {
  var __HEPHAES_WORKSPACE_STORE__: WorkspaceStoreSnapshot | undefined
}

const DEFAULT_WORKSPACE_STORE_SNAPSHOT: WorkspaceStoreSnapshot = {
  activeWorkspaceId: null,
  error: null,
  status: "idle",
  workspaces: [],
}

const workspaceStoreListeners = new Set<() => void>()

function workspacesAreEqual(
  left: WorkspaceRegistrySummary[],
  right: WorkspaceRegistrySummary[]
) {
  if (left.length !== right.length) {
    return false
  }

  return left.every((workspace, index) => {
    const other = right[index]
    return (
      workspace.id === other.id &&
      workspace.updated_at === other.updated_at &&
      workspace.last_opened_at === other.last_opened_at &&
      workspace.status === other.status &&
      workspace.status_reason === other.status_reason &&
      workspace.name === other.name
    )
  })
}

function snapshotsAreEqual(
  left: WorkspaceStoreSnapshot,
  right: WorkspaceStoreSnapshot
) {
  return (
    left.activeWorkspaceId === right.activeWorkspaceId &&
    left.error === right.error &&
    left.status === right.status &&
    workspacesAreEqual(left.workspaces, right.workspaces)
  )
}

function notifyWorkspaceStoreListeners() {
  for (const listener of workspaceStoreListeners) {
    listener()
  }
}

export function getWorkspaceStoreSnapshot(): WorkspaceStoreSnapshot {
  if (typeof globalThis === "undefined") {
    return DEFAULT_WORKSPACE_STORE_SNAPSHOT
  }

  return (
    globalThis.__HEPHAES_WORKSPACE_STORE__ ?? DEFAULT_WORKSPACE_STORE_SNAPSHOT
  )
}

export function setWorkspaceStoreSnapshot(snapshot: WorkspaceStoreSnapshot) {
  const normalizedSnapshot: WorkspaceStoreSnapshot = {
    activeWorkspaceId: snapshot.activeWorkspaceId?.trim() || null,
    error: snapshot.error?.trim() || null,
    status: snapshot.status,
    workspaces: snapshot.workspaces,
  }
  const currentSnapshot = getWorkspaceStoreSnapshot()

  if (snapshotsAreEqual(currentSnapshot, normalizedSnapshot)) {
    return
  }

  if (typeof globalThis !== "undefined") {
    globalThis.__HEPHAES_WORKSPACE_STORE__ = normalizedSnapshot
  }

  setActiveWorkspaceRequestId(normalizedSnapshot.activeWorkspaceId)
  notifyWorkspaceStoreListeners()
}

export function resetWorkspaceStore() {
  setWorkspaceStoreSnapshot(DEFAULT_WORKSPACE_STORE_SNAPSHOT)
}

export function subscribeToWorkspaceStore(onChange: () => void) {
  workspaceStoreListeners.add(onChange)
  return () => {
    workspaceStoreListeners.delete(onChange)
  }
}

export function useWorkspaceStoreSnapshot() {
  return React.useSyncExternalStore(
    subscribeToWorkspaceStore,
    getWorkspaceStoreSnapshot,
    getWorkspaceStoreSnapshot
  )
}

export function useActiveWorkspaceId() {
  return useWorkspaceStoreSnapshot().activeWorkspaceId
}
