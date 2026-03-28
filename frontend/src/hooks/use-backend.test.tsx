import { render, screen, waitFor } from "@testing-library/react"
import { SWRConfig } from "swr"
import type { ReactNode } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { useJobs } from "@/hooks/use-backend"
import { BackendApiError, listJobs } from "@/lib/api"

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
    vi.clearAllMocks()
  })

  it("retries transient load failures automatically", async () => {
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
})
