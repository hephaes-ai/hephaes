import { afterEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"

import { BootstrapApp } from "@/bootstrap-app"
import { setDesktopBackendRuntime } from "@/lib/backend-runtime"
import type { DesktopBackendRuntime } from "@/lib/backend-runtime"

describe("BootstrapApp", () => {
  afterEach(() => {
    setDesktopBackendRuntime(undefined)
  })

  it("renders the app once a ready runtime is returned", async () => {
    const loadRuntime = vi
      .fn<() => Promise<DesktopBackendRuntime | undefined>>()
      .mockResolvedValue({
        baseUrl: "http://127.0.0.1:8123",
        error: null,
        mode: "sidecar",
        status: "ready",
      })

    render(
      <BootstrapApp
        loadRuntime={loadRuntime}
        readyFallback={<div>ready app</div>}
      />
    )

    expect(screen.getByText("Launching Hephaes")).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText("ready app")).toBeInTheDocument()
    })
  })

  it("renders the startup failure screen when the runtime fails", async () => {
    const loadRuntime = vi
      .fn<() => Promise<DesktopBackendRuntime | undefined>>()
      .mockResolvedValue({
        backendLogDir: "/tmp/hephaes/backend-logs",
        baseUrl: "http://127.0.0.1:65094",
        desktopLogDir: "/tmp/hephaes/desktop-logs",
        error: "sidecar binary was not found",
        mode: "sidecar",
        status: "failed",
      })

    render(
      <BootstrapApp
        loadRuntime={loadRuntime}
        readyFallback={<div>ready app</div>}
      />
    )

    await waitFor(() => {
      expect(screen.getByText("Backend startup failed")).toBeInTheDocument()
    })

    expect(
      screen.getByText(/could not finish starting the bundled backend/i)
    ).toBeInTheDocument()
    expect(screen.getByText(/127\.0\.0\.1:65094/)).toBeInTheDocument()
    expect(
      screen.getByText(/sidecar binary was not found/i)
    ).toBeInTheDocument()
    expect(screen.getByText(/backend-logs/i)).toBeInTheDocument()
  })

  it("still renders the app when no desktop runtime is required", async () => {
    const loadRuntime = vi
      .fn<() => Promise<DesktopBackendRuntime | undefined>>()
      .mockResolvedValue(undefined)

    render(
      <BootstrapApp
        loadRuntime={loadRuntime}
        readyFallback={<div>ready app</div>}
      />
    )

    await waitFor(() => {
      expect(screen.getByText("ready app")).toBeInTheDocument()
    })
  })
})
