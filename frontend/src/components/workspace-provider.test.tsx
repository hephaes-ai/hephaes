import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { SWRConfig } from "swr"
import { afterEach, describe, expect, it, vi } from "vitest"

import { WorkspaceProvider, useWorkspace } from "@/components/workspace-provider"
import { useFrontendRuntime } from "@/hooks/use-desktop-backend-runtime"
import {
  activateWorkspace,
  getActiveWorkspaceRequestId,
  listWorkspaces,
} from "@/lib/api"
import { normalizeFrontendRuntime } from "@/lib/backend-runtime"
import { resetWorkspaceStore } from "@/lib/workspace-store"

vi.mock("@/hooks/use-desktop-backend-runtime", () => ({
  useFrontendRuntime: vi.fn(),
}))

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>(
    "@/lib/api"
  )

  return {
    ...actual,
    activateWorkspace: vi.fn(),
    createWorkspace: vi.fn(),
    deleteWorkspace: vi.fn(),
    listWorkspaces: vi.fn(),
  }
})

const READY_RUNTIME = normalizeFrontendRuntime({
  baseUrl: "http://127.0.0.1:8123",
  error: null,
  mode: "desktop-sidecar",
  status: "ready",
})

const LOADING_RUNTIME = normalizeFrontendRuntime({
  baseUrl: "http://127.0.0.1:8123",
  error: null,
  mode: "desktop-sidecar",
  status: "loading",
})

function buildWorkspaceSummary(id: string, name: string) {
  return {
    created_at: "2026-04-01T00:00:00Z",
    database_path: `/tmp/${id}/.hephaes/workspace.sqlite3`,
    id,
    last_opened_at: "2026-04-01T00:05:00Z",
    name,
    root_path: `/tmp/${id}`,
    status: "ready" as const,
    status_reason: null,
    updated_at: "2026-04-01T00:10:00Z",
    workspace_dir: `/tmp/${id}/.hephaes`,
  }
}

const ALPHA_WORKSPACE = buildWorkspaceSummary("ws_alpha", "Alpha Workspace")
const BETA_WORKSPACE = buildWorkspaceSummary("ws_beta", "Beta Workspace")

function WorkspaceProbe() {
  const workspace = useWorkspace()

  return (
    <div>
      <div>{`status:${workspace.status}`}</div>
      <div>{`active:${workspace.activeWorkspaceId ?? "none"}`}</div>
      <div>{`active-name:${workspace.activeWorkspace?.name ?? "none"}`}</div>
      <div>{`count:${workspace.workspaces.length}`}</div>
      <button onClick={() => void workspace.setActiveWorkspace("ws_beta")} type="button">
        Activate Beta
      </button>
    </div>
  )
}

function renderWithWorkspaceProvider() {
  return render(
    <SWRConfig
      value={{
        provider: () => new Map(),
        revalidateOnFocus: false,
        revalidateOnReconnect: false,
        shouldRetryOnError: false,
      }}
    >
      <WorkspaceProvider>
        <WorkspaceProbe />
      </WorkspaceProvider>
    </SWRConfig>
  )
}

describe("WorkspaceProvider", () => {
  afterEach(() => {
    cleanup()
    resetWorkspaceStore()
    vi.clearAllMocks()
  })

  it("does not fetch the workspace registry until the backend runtime is ready", async () => {
    vi.mocked(useFrontendRuntime).mockReturnValue(LOADING_RUNTIME)

    renderWithWorkspaceProvider()

    await waitFor(() => {
      expect(screen.getByText("status:idle")).toBeInTheDocument()
    })

    expect(vi.mocked(listWorkspaces)).not.toHaveBeenCalled()
    expect(getActiveWorkspaceRequestId()).toBeUndefined()
  })

  it("loads the registry and syncs the active workspace into the shared store", async () => {
    vi.mocked(useFrontendRuntime).mockReturnValue(READY_RUNTIME)
    vi.mocked(listWorkspaces).mockResolvedValue({
      active_workspace_id: ALPHA_WORKSPACE.id,
      workspaces: [ALPHA_WORKSPACE, BETA_WORKSPACE],
    })

    renderWithWorkspaceProvider()

    await waitFor(() => {
      expect(screen.getByText("status:ready")).toBeInTheDocument()
    })

    expect(screen.getByText(`active:${ALPHA_WORKSPACE.id}`)).toBeInTheDocument()
    expect(screen.getByText("active-name:Alpha Workspace")).toBeInTheDocument()
    expect(screen.getByText("count:2")).toBeInTheDocument()
    expect(getActiveWorkspaceRequestId()).toBe(ALPHA_WORKSPACE.id)
  })

  it("revalidates the registry after activation and updates the active workspace", async () => {
    vi.mocked(useFrontendRuntime).mockReturnValue(READY_RUNTIME)
    vi.mocked(listWorkspaces)
      .mockResolvedValueOnce({
        active_workspace_id: ALPHA_WORKSPACE.id,
        workspaces: [ALPHA_WORKSPACE, BETA_WORKSPACE],
      })
      .mockResolvedValueOnce({
        active_workspace_id: BETA_WORKSPACE.id,
        workspaces: [ALPHA_WORKSPACE, BETA_WORKSPACE],
      })
    vi.mocked(activateWorkspace).mockResolvedValue(BETA_WORKSPACE)

    renderWithWorkspaceProvider()

    await waitFor(() => {
      expect(screen.getByText(`active:${ALPHA_WORKSPACE.id}`)).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole("button", { name: "Activate Beta" }))

    await waitFor(() => {
      expect(vi.mocked(activateWorkspace)).toHaveBeenCalledWith(BETA_WORKSPACE.id)
    })

    await waitFor(() => {
      expect(screen.getByText(`active:${BETA_WORKSPACE.id}`)).toBeInTheDocument()
    })

    expect(screen.getByText("active-name:Beta Workspace")).toBeInTheDocument()
    expect(getActiveWorkspaceRequestId()).toBe(BETA_WORKSPACE.id)
    expect(vi.mocked(listWorkspaces)).toHaveBeenCalledTimes(2)
  })
})
