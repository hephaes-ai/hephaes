import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { WorkspaceSwitcher } from "@/components/workspace-switcher"
import { normalizeFrontendRuntime } from "@/lib/backend-runtime"
import type { WorkspaceRegistrySummary } from "@/lib/api"

const {
  mockNotify,
  mockOpenDirectoryDialog,
  mockUseFrontendRuntime,
  mockUseWorkspace,
} = vi.hoisted(() => ({
  mockNotify: vi.fn(),
  mockOpenDirectoryDialog: vi.fn(),
  mockUseFrontendRuntime: vi.fn(),
  mockUseWorkspace: vi.fn(),
}))

vi.mock("@/components/feedback-provider", () => ({
  useFeedback: () => ({
    notify: mockNotify,
  }),
}))

vi.mock("@/components/workspace-provider", () => ({
  useWorkspace: () => mockUseWorkspace(),
}))

vi.mock("@/hooks/use-desktop-backend-runtime", () => ({
  useFrontendRuntime: () => mockUseFrontendRuntime(),
}))

vi.mock("@/lib/native-dialogs", () => ({
  openDirectoryDialog: () => mockOpenDirectoryDialog(),
}))

function buildWorkspace(
  id: string,
  name: string,
  rootPath = `/tmp/${id}`
): WorkspaceRegistrySummary {
  return {
    created_at: "2026-04-01T00:00:00Z",
    database_path: `${rootPath}/.hephaes/workspace.sqlite3`,
    id,
    last_opened_at: "2026-04-01T00:10:00Z",
    name,
    root_path: rootPath,
    status: "ready",
    status_reason: null,
    updated_at: "2026-04-01T00:15:00Z",
    workspace_dir: `${rootPath}/.hephaes`,
  }
}

const ALPHA_WORKSPACE = buildWorkspace("ws_alpha", "Alpha Workspace")
const BETA_WORKSPACE = buildWorkspace("ws_beta", "Beta Workspace")

function buildWorkspaceHookValue(
  overrides: Partial<ReturnType<typeof mockUseWorkspace>> = {}
) {
  return {
    activatingWorkspaceId: null,
    activeWorkspace: ALPHA_WORKSPACE,
    activeWorkspaceId: ALPHA_WORKSPACE.id,
    createWorkspace: vi.fn(),
    deleteWorkspace: vi.fn(),
    deletingWorkspaceId: null,
    error: null,
    isCreatingWorkspace: false,
    isRefreshingWorkspaces: false,
    refreshWorkspaces: vi.fn(),
    setActiveWorkspace: vi.fn(),
    status: "ready" as const,
    workspaces: [ALPHA_WORKSPACE, BETA_WORKSPACE],
    ...overrides,
  }
}

function openSwitcherMenu() {
  fireEvent.pointerDown(
    screen.getByRole("button", { name: "Select workspace" })
  )
}

describe("WorkspaceSwitcher", () => {
  beforeEach(() => {
    mockNotify.mockReset()
    mockOpenDirectoryDialog.mockReset()
    mockUseWorkspace.mockReset()
    mockUseFrontendRuntime.mockReset()

    mockUseFrontendRuntime.mockReturnValue(
      normalizeFrontendRuntime({
        baseUrl: "http://127.0.0.1:8123",
        error: null,
        mode: "desktop-sidecar",
        status: "ready",
      })
    )
  })

  afterEach(() => {
    cleanup()
  })

  it("shows registered workspaces in the navbar dropdown and opens the management dialog", async () => {
    mockUseWorkspace.mockReturnValue(buildWorkspaceHookValue())

    render(<WorkspaceSwitcher />)

    expect(screen.getByText("Alpha Workspace")).toBeInTheDocument()

    openSwitcherMenu()

    expect(screen.getByText("Beta Workspace")).toBeInTheDocument()
    expect(screen.getByText("Create workspace...")).toBeInTheDocument()

    fireEvent.click(screen.getByText("Manage workspaces..."))

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Manage workspaces" })
      ).toBeInTheDocument()
    })

    expect(screen.getAllByText("Alpha Workspace")[0]).toBeInTheDocument()
    expect(screen.getByText(ALPHA_WORKSPACE.root_path)).toBeInTheDocument()
  })

  it("activates another workspace from the navbar dropdown", async () => {
    const setActiveWorkspace = vi.fn().mockResolvedValue(BETA_WORKSPACE)
    mockUseWorkspace.mockReturnValue(
      buildWorkspaceHookValue({
        setActiveWorkspace,
      })
    )

    render(<WorkspaceSwitcher />)

    openSwitcherMenu()
    fireEvent.click(screen.getByText("Beta Workspace"))

    await waitFor(() => {
      expect(setActiveWorkspace).toHaveBeenCalledWith(BETA_WORKSPACE.id)
    })
  })

  it("opens the create workspace dialog after selecting a directory", async () => {
    mockOpenDirectoryDialog.mockResolvedValue({
      directoryPath: "/tmp/demo-workspace",
      status: "selected",
    })
    mockUseWorkspace.mockReturnValue(buildWorkspaceHookValue())

    render(<WorkspaceSwitcher />)

    openSwitcherMenu()
    fireEvent.click(screen.getByText("Create workspace..."))

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Create workspace" })
      ).toBeInTheDocument()
    })

    expect(screen.getByText("/tmp/demo-workspace")).toBeInTheDocument()
    expect(screen.getByDisplayValue("demo-workspace")).toBeInTheDocument()
  })

  it("registers an existing workspace root through the create flow", async () => {
    const createWorkspace = vi
      .fn()
      .mockResolvedValue(
        buildWorkspace(
          "ws_existing",
          "existing-project",
          "/tmp/existing-project"
        )
      )
    mockOpenDirectoryDialog.mockResolvedValue({
      directoryPath: "/tmp/existing-project",
      status: "selected",
    })
    mockUseWorkspace.mockReturnValue(
      buildWorkspaceHookValue({
        createWorkspace,
      })
    )

    render(<WorkspaceSwitcher />)

    openSwitcherMenu()
    fireEvent.click(screen.getByText("Create workspace..."))

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Create workspace" })
      ).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole("button", { name: "Create workspace" }))

    await waitFor(() => {
      expect(createWorkspace).toHaveBeenCalledWith({
        activate: true,
        name: "existing-project",
        root_path: "/tmp/existing-project",
      })
    })
  })
})
