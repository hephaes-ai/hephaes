import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

import { BackendConnectionNotice } from "@/components/backend-connection-notice"
import { setDesktopBackendRuntime } from "@/lib/backend-runtime"

const mockUseHealth = vi.fn<
  () => {
    error: Error | null
    isLoading: boolean
  }
>(() => ({
  error: null,
  isLoading: false,
}))

vi.mock("@/hooks/use-backend", () => ({
  useHealth: () => mockUseHealth(),
}))

describe("BackendConnectionNotice", () => {
  afterEach(() => {
    cleanup()
    setDesktopBackendRuntime(undefined)
    mockUseHealth.mockClear()
  })

  it("shows a bundled backend stop notice as soon as the sidecar terminates", () => {
    setDesktopBackendRuntime({
      backendLogDir: "/tmp/hephaes/backend-logs",
      baseUrl: "http://127.0.0.1:65123",
      desktopLogDir: "/tmp/hephaes/desktop-logs",
      error: "backend sidecar exited with status code 1",
      mode: "sidecar",
      status: "stopped",
    })
    mockUseHealth.mockReturnValue({
      error: null,
      isLoading: false,
    })

    render(<BackendConnectionNotice />)

    expect(screen.getByText("Bundled backend stopped")).toBeInTheDocument()
    expect(
      screen.getByText(/backend sidecar exited with status code 1/i)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/backend logs: \/tmp\/hephaes\/backend-logs/i)
    ).toBeInTheDocument()
  })

  it("shows the configured backend error when the health check fails", () => {
    setDesktopBackendRuntime({
      baseUrl: "http://127.0.0.1:8000",
      error: null,
      mode: "external",
      status: "ready",
    })
    mockUseHealth.mockReturnValue({
      error: new Error("connection refused"),
      isLoading: false,
    })

    render(<BackendConnectionNotice />)

    expect(
      screen.getByText("Configured backend unavailable")
    ).toBeInTheDocument()
    expect(
      screen.getByText(/target url: http:\/\/127\.0\.0\.1:8000/i)
    ).toBeInTheDocument()
  })
})
