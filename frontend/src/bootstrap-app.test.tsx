import { render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { BootstrapApp } from "@/bootstrap-app"
import type { DesktopBackendRuntime } from "@/lib/backend-runtime"

describe("BootstrapApp", () => {
  it("renders the app once a ready runtime is returned", async () => {
    const loadRuntime = vi.fn<
      () => Promise<DesktopBackendRuntime | undefined>
    >().mockResolvedValue({
      baseUrl: "http://127.0.0.1:8123",
      error: null,
      mode: "sidecar",
      status: "ready",
    })

    render(
      <BootstrapApp
        loadRuntime={loadRuntime}
        readyFallback={<div>ready app</div>}
      />,
    )

    expect(screen.getByText("Launching Hephaes")).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText("ready app")).toBeInTheDocument()
    })
  })

  it("renders the startup failure screen when the runtime fails", async () => {
    const loadRuntime = vi.fn<
      () => Promise<DesktopBackendRuntime | undefined>
    >().mockResolvedValue({
      baseUrl: "http://127.0.0.1:65094",
      error: "sidecar binary was not found",
      mode: "sidecar",
      status: "failed",
    })

    render(
      <BootstrapApp
        loadRuntime={loadRuntime}
        readyFallback={<div>ready app</div>}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText("Backend startup failed")).toBeInTheDocument()
    })

    expect(
      screen.getByText(/could not finish starting the bundled backend/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/127\.0\.0\.1:65094/)).toBeInTheDocument()
    expect(screen.getByText(/sidecar binary was not found/i)).toBeInTheDocument()
  })
})
