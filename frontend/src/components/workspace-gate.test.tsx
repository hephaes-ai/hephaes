import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { WorkspaceGate } from "@/components/workspace-gate"
import type { WorkspaceRegistrySummary } from "@/lib/api"

const {
  mockRequestOpenCreateWorkspace,
  mockRequestOpenManageWorkspaces,
  mockUseWorkspace,
} = vi.hoisted(() => ({
  mockRequestOpenCreateWorkspace: vi.fn(),
  mockRequestOpenManageWorkspaces: vi.fn(),
  mockUseWorkspace: vi.fn(),
}))

vi.mock("@/components/workspace-provider", () => ({
  useWorkspace: () => mockUseWorkspace(),
}))

vi.mock("@/lib/workspace-ui-events", () => ({
  requestOpenCreateWorkspace: (intent?: "create" | "open") =>
    mockRequestOpenCreateWorkspace(intent),
  requestOpenManageWorkspaces: () => mockRequestOpenManageWorkspaces(),
}))

function buildWorkspace(
  id: string,
  status: WorkspaceRegistrySummary["status"]
): WorkspaceRegistrySummary {
  return {
    active_job_count: 0,
    created_at: "2026-04-01T00:00:00Z",
    database_path: `/tmp/${id}/.hephaes/workspace.sqlite3`,
    id,
    last_opened_at: "2026-04-01T00:10:00Z",
    name: `Workspace ${id}`,
    root_path: `/tmp/${id}`,
    status,
    status_reason:
      status === "missing"
        ? "workspace directory does not exist"
        : status === "invalid"
          ? "workspace database is unreadable"
          : null,
    updated_at: "2026-04-01T00:15:00Z",
    workspace_dir: `/tmp/${id}/.hephaes`,
  }
}

function buildWorkspaceHookValue(
  overrides: Partial<ReturnType<typeof mockUseWorkspace>> = {}
) {
  return {
    activatingWorkspaceId: null,
    activeWorkspace: null,
    activeWorkspaceId: null,
    createWorkspace: vi.fn(),
    deleteWorkspace: vi.fn(),
    deletingWorkspaceId: null,
    error: null,
    isCreatingWorkspace: false,
    isRefreshingWorkspaces: false,
    refreshWorkspaces: vi.fn(),
    setActiveWorkspace: vi.fn(),
    status: "ready" as const,
    workspaces: [],
    ...overrides,
  }
}

describe("WorkspaceGate", () => {
  beforeEach(() => {
    mockRequestOpenCreateWorkspace.mockReset()
    mockRequestOpenManageWorkspaces.mockReset()
    mockUseWorkspace.mockReset()
  })

  afterEach(() => {
    cleanup()
  })

  it("blocks the app and prompts creation when the registry is empty", () => {
    mockUseWorkspace.mockReturnValue(buildWorkspaceHookValue())

    render(
      <WorkspaceGate>
        <div>app content</div>
      </WorkspaceGate>
    )

    expect(screen.getByText("Create your first workspace")).toBeInTheDocument()
    expect(screen.queryByText("app content")).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Create workspace" }))
    fireEvent.click(
      screen.getByRole("button", { name: "Open existing workspace" })
    )

    expect(mockRequestOpenCreateWorkspace).toHaveBeenNthCalledWith(1, "create")
    expect(mockRequestOpenCreateWorkspace).toHaveBeenNthCalledWith(2, "open")
  })

  it("shows a recovery state when registered workspaces exist but none are ready", () => {
    mockUseWorkspace.mockReturnValue(
      buildWorkspaceHookValue({
        workspaces: [
          buildWorkspace("ws_missing", "missing"),
          buildWorkspace("ws_invalid", "invalid"),
        ],
      })
    )

    render(
      <WorkspaceGate>
        <div>app content</div>
      </WorkspaceGate>
    )

    expect(screen.getByText("Workspace recovery needed")).toBeInTheDocument()
    expect(
      screen.getByText("workspace directory does not exist")
    ).toBeInTheDocument()
    expect(
      screen.getByText("workspace database is unreadable")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Manage workspaces" }))

    expect(mockRequestOpenManageWorkspaces).toHaveBeenCalledTimes(1)
  })

  it("renders app content once a ready active workspace is available", () => {
    const readyWorkspace = buildWorkspace("ws_ready", "ready")
    mockUseWorkspace.mockReturnValue(
      buildWorkspaceHookValue({
        activeWorkspace: readyWorkspace,
        activeWorkspaceId: readyWorkspace.id,
        workspaces: [readyWorkspace],
      })
    )

    render(
      <WorkspaceGate>
        <div>app content</div>
      </WorkspaceGate>
    )

    expect(screen.getByText("app content")).toBeInTheDocument()
    expect(
      screen.queryByText("Create your first workspace")
    ).not.toBeInTheDocument()
  })
})
