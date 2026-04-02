"use client"

import * as React from "react"

import { useBackendCache, useWorkspaceRegistry } from "@/hooks/use-backend"
import { useFrontendRuntime } from "@/hooks/use-desktop-backend-runtime"
import {
  activateWorkspace as activateWorkspaceRequest,
  createWorkspace as createWorkspaceRequest,
  deleteWorkspace as deleteWorkspaceRequest,
  getErrorMessage,
  type WorkspaceCreateRequest,
  type WorkspaceRegistryListResponse,
  type WorkspaceRegistrySummary,
} from "@/lib/api"
import {
  getWorkspaceStoreSnapshot,
  resetWorkspaceStore,
  setWorkspaceStoreSnapshot,
  useWorkspaceStoreSnapshot,
  type WorkspaceStoreSnapshot,
} from "@/lib/workspace-store"

interface WorkspaceContextValue extends WorkspaceStoreSnapshot {
  activeWorkspace: WorkspaceRegistrySummary | null
  activatingWorkspaceId: string | null
  createWorkspace: (
    payload: WorkspaceCreateRequest
  ) => Promise<WorkspaceRegistrySummary>
  deleteWorkspace: (workspaceId: string) => Promise<void>
  deletingWorkspaceId: string | null
  isCreatingWorkspace: boolean
  isRefreshingWorkspaces: boolean
  refreshWorkspaces: () => Promise<WorkspaceRegistryListResponse | undefined>
  setActiveWorkspace: (workspaceId: string) => Promise<WorkspaceRegistrySummary>
}

const WorkspaceContext = React.createContext<WorkspaceContextValue | null>(null)

function resolveActiveWorkspace(snapshot: WorkspaceStoreSnapshot) {
  if (!snapshot.activeWorkspaceId) {
    return null
  }

  return (
    snapshot.workspaces.find(
      (workspace) => workspace.id === snapshot.activeWorkspaceId
    ) ?? null
  )
}

export function WorkspaceProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const runtime = useFrontendRuntime()
  const snapshot = useWorkspaceStoreSnapshot()
  const registryResponse = useWorkspaceRegistry(runtime?.status === "ready")
  const { clearWorkspaceScopedCaches, revalidateWorkspaces } = useBackendCache()
  const [isCreatingWorkspace, setIsCreatingWorkspace] = React.useState(false)
  const [activatingWorkspaceId, setActivatingWorkspaceId] = React.useState<
    string | null
  >(null)
  const [deletingWorkspaceId, setDeletingWorkspaceId] = React.useState<
    string | null
  >(null)
  const previousActiveWorkspaceIdRef = React.useRef<string | null>(
    snapshot.activeWorkspaceId
  )

  React.useEffect(() => {
    if (runtime?.status === "ready") {
      return
    }

    const currentSnapshot = getWorkspaceStoreSnapshot()
    previousActiveWorkspaceIdRef.current = null

    if (
      currentSnapshot.activeWorkspaceId !== null ||
      currentSnapshot.workspaces.length > 0
    ) {
      void clearWorkspaceScopedCaches()
    }

    resetWorkspaceStore()
  }, [clearWorkspaceScopedCaches, runtime?.status])

  React.useEffect(() => {
    if (runtime?.status !== "ready") {
      return
    }

    if (registryResponse.data) {
      const nextActiveWorkspaceId =
        registryResponse.data.active_workspace_id?.trim() || null

      if (previousActiveWorkspaceIdRef.current !== nextActiveWorkspaceId) {
        void clearWorkspaceScopedCaches()
      }

      previousActiveWorkspaceIdRef.current = nextActiveWorkspaceId
      setWorkspaceStoreSnapshot({
        activeWorkspaceId: nextActiveWorkspaceId,
        error: null,
        status: "ready",
        workspaces: registryResponse.data.workspaces,
      })
      return
    }

    if (registryResponse.error) {
      const currentSnapshot = getWorkspaceStoreSnapshot()
      setWorkspaceStoreSnapshot({
        activeWorkspaceId: currentSnapshot.activeWorkspaceId,
        error: getErrorMessage(registryResponse.error),
        status: "error",
        workspaces: currentSnapshot.workspaces,
      })
      return
    }

    if (registryResponse.isLoading || registryResponse.isValidating) {
      const currentSnapshot = getWorkspaceStoreSnapshot()
      setWorkspaceStoreSnapshot({
        activeWorkspaceId: currentSnapshot.activeWorkspaceId,
        error: null,
        status: currentSnapshot.status === "ready" ? "ready" : "loading",
        workspaces: currentSnapshot.workspaces,
      })
    }
  }, [
    clearWorkspaceScopedCaches,
    registryResponse.data,
    registryResponse.error,
    registryResponse.isLoading,
    registryResponse.isValidating,
    runtime?.status,
  ])

  async function refreshWorkspaces() {
    if (runtime?.status !== "ready") {
      return undefined
    }

    return registryResponse.mutate()
  }

  async function createWorkspace(payload: WorkspaceCreateRequest) {
    setIsCreatingWorkspace(true)

    try {
      const workspace = await createWorkspaceRequest(payload)
      await revalidateWorkspaces()
      return workspace
    } finally {
      setIsCreatingWorkspace(false)
    }
  }

  async function setActiveWorkspace(workspaceId: string) {
    setActivatingWorkspaceId(workspaceId)

    try {
      const workspace = await activateWorkspaceRequest(workspaceId)
      await revalidateWorkspaces()
      return workspace
    } finally {
      setActivatingWorkspaceId(null)
    }
  }

  async function deleteWorkspace(workspaceId: string) {
    setDeletingWorkspaceId(workspaceId)

    try {
      await deleteWorkspaceRequest(workspaceId)
      await revalidateWorkspaces()
    } finally {
      setDeletingWorkspaceId(null)
    }
  }

  return (
    <WorkspaceContext.Provider
      value={{
        ...snapshot,
        activeWorkspace: resolveActiveWorkspace(snapshot),
        activatingWorkspaceId,
        createWorkspace,
        deleteWorkspace,
        deletingWorkspaceId,
        isCreatingWorkspace,
        isRefreshingWorkspaces: registryResponse.isValidating,
        refreshWorkspaces,
        setActiveWorkspace,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace() {
  const context = React.useContext(WorkspaceContext)

  if (!context) {
    throw new Error("useWorkspace must be used inside WorkspaceProvider.")
  }

  return context
}
