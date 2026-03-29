import { afterEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, render, screen, waitFor } from "@testing-library/react"

import { BootstrapApp } from "@/bootstrap-app"
import {
  createWebFrontendRuntime,
  normalizeFrontendRuntime,
  setFrontendRuntime,
  type FrontendRuntimeSnapshot,
} from "@/lib/backend-runtime"

describe("BootstrapApp", () => {
  afterEach(() => {
    cleanup()
    setFrontendRuntime(undefined)
  })

  it("renders the app once a ready runtime is returned", async () => {
    const loadRuntime = vi
      .fn<() => Promise<FrontendRuntimeSnapshot | undefined>>()
      .mockResolvedValue(
        normalizeFrontendRuntime({
          baseUrl: "http://127.0.0.1:8123",
          error: null,
          mode: "desktop-sidecar",
          status: "ready",
        })
      )

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
      .fn<() => Promise<FrontendRuntimeSnapshot | undefined>>()
      .mockResolvedValue(
        normalizeFrontendRuntime({
          backendLogDir: "/tmp/hephaes/backend-logs",
          baseUrl: "http://127.0.0.1:65094",
          desktopLogDir: "/tmp/hephaes/desktop-logs",
          error: "sidecar binary was not found",
          mode: "desktop-sidecar",
          status: "failed",
        })
      )

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

  it("still renders the app when the Vite app is running in web mode", async () => {
    const loadRuntime = vi
      .fn<() => Promise<FrontendRuntimeSnapshot | undefined>>()
      .mockResolvedValue(createWebFrontendRuntime("http://localhost:3000"))

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

  it("keeps the startup screen visible until a loading runtime becomes ready", async () => {
    let resolveRuntime: (
      value: FrontendRuntimeSnapshot | undefined
    ) => void = () => undefined
    const loadRuntime = vi
      .fn<() => Promise<FrontendRuntimeSnapshot | undefined>>()
      .mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveRuntime = resolve
          })
      )

    render(
      <BootstrapApp
        loadRuntime={loadRuntime}
        readyFallback={<div>ready app</div>}
      />
    )

    expect(screen.getByText("Launching Hephaes")).toBeInTheDocument()
    expect(screen.queryByText("ready app")).not.toBeInTheDocument()

    await act(async () => {
      resolveRuntime(
        normalizeFrontendRuntime({
          baseUrl: "http://127.0.0.1:8123",
          error: null,
          mode: "desktop-sidecar",
          status: "loading",
        })
      )
    })

    await act(async () => {
      setFrontendRuntime(
        normalizeFrontendRuntime({
          baseUrl: "http://127.0.0.1:8123",
          error: null,
          mode: "desktop-sidecar",
          status: "ready",
        })
      )
    })

    await waitFor(() => {
      expect(screen.getByText("ready app")).toBeInTheDocument()
    })
  })

  it("renders the startup failure screen when the sidecar stops during startup", async () => {
    let resolveRuntime: (
      value: FrontendRuntimeSnapshot | undefined
    ) => void = () => undefined
    const loadRuntime = vi
      .fn<() => Promise<FrontendRuntimeSnapshot | undefined>>()
      .mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveRuntime = resolve
          })
      )

    render(
      <BootstrapApp
        loadRuntime={loadRuntime}
        readyFallback={<div>ready app</div>}
      />
    )

    await act(async () => {
      resolveRuntime(
        normalizeFrontendRuntime({
          baseUrl: "http://127.0.0.1:8123",
          error: null,
          mode: "desktop-sidecar",
          status: "loading",
        })
      )
    })

    await act(async () => {
      setFrontendRuntime(
        normalizeFrontendRuntime({
          backendLogDir: "/tmp/hephaes/backend-logs",
          baseUrl: "http://127.0.0.1:8123",
          desktopLogDir: "/tmp/hephaes/desktop-logs",
          error: "backend sidecar exited with status code 1",
          mode: "desktop-sidecar",
          status: "stopped",
        })
      )
    })

    await waitFor(() => {
      expect(screen.getByText("Backend startup failed")).toBeInTheDocument()
    })
    expect(
      screen.getByText(/backend sidecar exited with status code 1/i)
    ).toBeInTheDocument()
  })
})
