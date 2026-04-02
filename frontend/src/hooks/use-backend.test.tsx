import { act, cleanup, render, screen, waitFor } from "@testing-library/react"
import { SWRConfig } from "swr"
import type { ReactNode } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { useJobs } from "@/hooks/use-backend"
import { BackendApiError, listJobs } from "@/lib/api"
import {
  resetWorkspaceStore,
  setWorkspaceStoreSnapshot,
} from "@/lib/workspace-store"

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>(
    "@/lib/api"
  )

  return {
    ...actual,
    listJobs: vi.fn(),
  }
})

function JobsProbe() {
  const jobsResponse = useJobs()

  if (jobsResponse.error) {
    return <div>{jobsResponse.error.message}</div>
  }

  if (!jobsResponse.data) {
    return <div>loading</div>
  }

  return <div>loaded {jobsResponse.data.length}</div>
}

function buildWorkspaceSummary(id: string) {
  return {
    created_at: "2026-04-01T00:00:00Z",
    database_path: `/tmp/${id}/.hephaes/workspace.sqlite3`,
    id,
    last_opened_at: "2026-04-01T00:05:00Z",
    name: `Workspace ${id}`,
    root_path: `/tmp/${id}`,
    status: "ready" as const,
    status_reason: null,
    updated_at: "2026-04-01T00:10:00Z",
    workspace_dir: `/tmp/${id}/.hephaes`,
  }
}

function setReadyWorkspace(workspaceId: string) {
  setWorkspaceStoreSnapshot({
    activeWorkspaceId: workspaceId,
    error: null,
    status: "ready",
    workspaces: [buildWorkspaceSummary(workspaceId)],
  })
}

function renderWithSWR(children: ReactNode) {
  return render(
    <SWRConfig
      value={{
        provider: () => new Map(),
        revalidateOnFocus: false,
        revalidateOnReconnect: false,
        shouldRetryOnError: false,
      }}
    >
      {children}
    </SWRConfig>
  )
}

describe("useJobs", () => {
  afterEach(() => {
    cleanup()
    resetWorkspaceStore()
    vi.clearAllMocks()
  })

  it("retries transient load failures automatically", async () => {
    setReadyWorkspace("ws_alpha")
    vi.mocked(listJobs)
      .mockRejectedValueOnce(new TypeError("Load failed"))
      .mockResolvedValueOnce([])

    renderWithSWR(<JobsProbe />)

    await waitFor(() => {
      expect(vi.mocked(listJobs)).toHaveBeenCalledTimes(2)
    }, { timeout: 2_000 })

    await waitFor(() => {
      expect(screen.getByText("loaded 0")).toBeInTheDocument()
    })
  })

  it("does not retry client errors", async () => {
    setReadyWorkspace("ws_alpha")
    vi.mocked(listJobs).mockRejectedValue(
      new BackendApiError("jobs route missing", 404)
    )

    renderWithSWR(<JobsProbe />)

    await waitFor(() => {
      expect(screen.getByText("jobs route missing")).toBeInTheDocument()
    })

    await new Promise((resolve) => window.setTimeout(resolve, 900))

    expect(vi.mocked(listJobs)).toHaveBeenCalledTimes(1)
  })

  it("refetches jobs when the active workspace changes", async () => {
    setReadyWorkspace("ws_alpha")
    vi.mocked(listJobs)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{ id: "job-1" }] as never[])

    renderWithSWR(<JobsProbe />)

    await waitFor(() => {
      expect(screen.getByText("loaded 0")).toBeInTheDocument()
    })

    await act(async () => {
      setReadyWorkspace("ws_beta")
    })

    await waitFor(() => {
      expect(vi.mocked(listJobs)).toHaveBeenCalledTimes(2)
    })

    await waitFor(() => {
      expect(screen.getByText("loaded 1")).toBeInTheDocument()
    })
  })
})
