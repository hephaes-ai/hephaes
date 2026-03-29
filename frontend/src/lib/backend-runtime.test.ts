import { afterEach, describe, expect, it, vi } from "vitest"

import {
  getFrontendRuntime,
  normalizeFrontendRuntime,
  setFrontendRuntime,
  subscribeToFrontendRuntime,
} from "@/lib/backend-runtime"

describe("backend runtime", () => {
  afterEach(() => {
    setFrontendRuntime(undefined)
  })

  it("normalizes legacy desktop modes and injects desktop capabilities", () => {
    const runtime = normalizeFrontendRuntime({
      baseUrl: "http://127.0.0.1:8000/",
      error: null,
      mode: "sidecar",
      status: "ready",
    })

    expect(runtime).toEqual({
      baseUrl: "http://127.0.0.1:8000",
      capabilities: {
        browserUpload: false,
        nativeDirectoryDialog: true,
        nativeFileDialog: true,
        pathAssetRegistration: true,
      },
      error: null,
      mode: "desktop-sidecar",
      status: "ready",
    })
  })

  it("publishes normalized runtime snapshots to subscribers", () => {
    const onChange = vi.fn()
    const unsubscribe = subscribeToFrontendRuntime(onChange)

    setFrontendRuntime({
      baseUrl: "http://localhost:3000/",
      error: null,
      mode: "web",
      status: "ready",
    })

    expect(onChange).toHaveBeenCalledTimes(1)
    expect(getFrontendRuntime()).toEqual({
      baseUrl: "http://localhost:3000",
      capabilities: {
        browserUpload: true,
        nativeDirectoryDialog: false,
        nativeFileDialog: false,
        pathAssetRegistration: false,
      },
      error: null,
      mode: "web",
      status: "ready",
    })

    unsubscribe()
    setFrontendRuntime(undefined)
    expect(onChange).toHaveBeenCalledTimes(1)
  })
})
